"""Render Node Server Software"""
import os
import sys
import datetime
import subprocess
import traceback

import psutil

from hydra_farm.utils.logging_setup import logger
from hydra_farm.database import hydra_db as sql
from hydra_farm.utils import single_instance
from hydra_farm.networking import servers
from hydra_farm.utils import yaml_cache
from hydra_farm.utils import hydra_threading as ht

config = yaml_cache.get_hydra_cfg()

OFFLINE_STATUS = {sql.HydraStatus.OFFLINE, sql.HydraStatus.PENDING, sql.HydraStatus.STARTED}


class RenderTCPServer(object):
    """RenderTCPServer waits for a TCP connection from the RenderManagerServer
    telling it to start a render task. The render task is processed and the results
    updated in the database."""

    def __init__(self):
        # Setup Class Variables
        self.server_thread = None
        self.render_thread = None
        self.pulse_thread = None

        self.child_process = None
        self.ps_util_proc = None
        self.child_killed = 0

        # Get this node data from the database and make sure it exists
        self.this_node = sql.HydraRenderNode.get_this_node()
        logger.debug(self.this_node)

        if self.this_node:
            if not self.this_node.is_render_node or not self.this_node.ip_addr:
                logger.critical("This is not a render node! A render node must be marked as such and have an IP "
                                "address assigned to it in the database.")
                sys.exit(-1)
        else:
            logger.critical("This node does not exist in the database! Please Register this node and try again.")
            sys.exit(-1)

        self.keep_all_logs = config['general']['keep_all_render_logs']

        # Create RenderLog Directory if it doesn't exit
        render_log_dir = config['logs']['render_log_path']
        if not os.path.isdir(render_log_dir):
            os.makedirs(render_log_dir)

        self.this_node.unstick_task()

        # Start TCP Server Thread
        port = int(config['networking']['host_port'])
        self.server_thread = servers.HydraTCPServerThread(port)
        self.server_thread.handler = self
        ht.HydraThreadManager.add_thread(self.server_thread)

        # Start Render Loop Thread
        self.render_thread = ht.HydraThreadManager.create_idle_loop('Render Loop', self.render_loop, 10)

        # Start Pulse Thread
        self.pulse_thread = ht.HydraThreadManager.create_idle_loop("Pulse Thread", self.heartbeat, 60)

        ht.HydraThreadManager.run_forever()

    @staticmethod
    def build_subprocess_args(include_stdout: bool = False) -> dict:
        """Build subprocess startup kwargs.

        Args:
            include_stdout (bool): If True will add a subprocess.PIPE to stdout.

        Returns:
            dict: kwargs for subprocess startup.

        """
        if hasattr(subprocess, 'STARTUPINFO'):
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            env = os.environ
        else:
            si = None
            env = None

        ret = {'stdin': subprocess.PIPE, 'startupinfo': si, 'env': env}

        if include_stdout:
            ret.update({'stdout:': subprocess.PIPE})

        return ret

    def heartbeat(self):
        """Update pulse for this node, signaling that the node is online and alive.

        """
        self.this_node.pulse = datetime.datetime.now()  # Probably better to use the server time than the host time
        self.this_node.update()

    def render_loop(self):
        """Main loop, updates this node's info and checks for a task if the node is online. If a task is found,
        start rendering that task.

        """
        self.this_node = sql.HydraRenderNode.get_this_node()

        if self.this_node.status in OFFLINE_STATUS:
            return

        job, task = self.this_node.find_render_task()

        if job and task:
            self.launch_render_task(job, task)

    def handle_connection(self, request: servers.HydraRequest) -> servers.HydraResponse:
        """Handle a TCP connection to do things like kill the current task or shutdown the server.

        Args:
            request (servers.HydraRequest): HydraRequest instance with a command and possibly some args.

        Returns:
            servers.HydraResponse: Response to the request.

        """
        logger.debug('Handing Connection')
        if request.cmd == 'kill_current_task':
            result = self.kill_current_task()
            response = servers.HydraResponse()
            if result:
                response.err = False
                response.msg = 'Task was successfully killed'
            else:
                response.msg = 'There was an error while trying to kill the task'

        elif request.cmd == 'shutdown':
            response = servers.HydraResponse.from_args('Shutting down...', False)
            # TODO: Test this out
            shutdown_thread = ht.HydraThread('Shutdown Thread', self.shutdown, delay=1, single_shot=True)
            ht.HydraThreadManager.add_thread(shutdown_thread)
            return response

        else:
            response = servers.HydraResponse()
            response.msg = 'No handler for cmd {} on {}'.format(request.cmd, self.__class__.__name__)

        return response

    def kill_current_task(self) -> int:
        """Attempt to kill the current render task.

        Returns:
            int: Status code, 1 = process killed, -1 = parent could not be killed, -9 = child could not be killed,
            -10 = child and parent could not be killed

        """
        self.child_killed = 1
        if not self.child_process or not self.ps_util_proc:
            logger.info("No task is running!")
            return self.child_killed

        # Gather subprocesses just in case
        if self.ps_util_proc.is_running():
            children_procs = self.ps_util_proc.children(recursive=True)
        else:
            logger.info("PID '%s' could not be found! Task is probably already dead.", self.child_process.pid)
            return self.child_killed

        # Try to kill the main process
        # terminate() = SIGTERM, kill() = SIGKILL
        logger.info("Killing main task with PID %s", self.ps_util_proc.pid)
        self.ps_util_proc.terminate()
        _, alive = psutil.wait_procs([self.ps_util_proc], timeout=15)
        if alive:
            self.ps_util_proc.kill()
            _, alive = psutil.wait_procs([self.ps_util_proc], timeout=15)
            if alive:
                logger.error("Could not kill PID %s", self.ps_util_proc.pid)
                self.child_killed = -1

        # Try to kill the children if they are still running
        _ = [proc.terminate() for proc in children_procs if proc.is_running()]
        _, alive = psutil.wait_procs(children_procs, timeout=15)
        if alive:
            _ = [proc.kill() for proc in alive]
            _, alive = psutil.wait_procs(alive, timeout=15)

        if alive:
            # ADD negative 10 to the return code
            self.child_killed += -10

        return self.child_killed

    def shutdown(self):
        """Set this node's status to offline and shutdown all servers and threads.

        """
        self.this_node = sql.HydraRenderNode.get_this_node()
        cs = self.this_node.status
        check_status = {sql.HydraStatus.IDLE, sql.HydraStatus.STARTED}
        new_status = sql.HydraStatus.IDLE if cs in check_status else sql.HydraStatus.OFFLINE
        if cs in [sql.HydraStatus.STARTED, sql.HydraStatus.PENDING] or self.child_process:
            self.this_node.get_off()
        else:
            self.this_node.offline()

        self.render_thread.terminate()

        if new_status == sql.HydraStatus.IDLE:
            self.this_node.online()
        else:
            self.this_node.offline()

        ht.HydraThreadManager.shutdown()
        logger.info("RenderNode servers Shutdown")

    def reboot(self):
        """Reboot the render node, useful for pushing out software updates.

        """
        self.shutdown()
        if sys.platform.startswith("win"):
            os.system("shutdown -r -f -t 60 -c \"HydraFarm: Rebooting...\"")
        else:
            os.system("reboot now")

    def launch_render_task(self, job: sql.HydraRenderJob, task: sql.HydraRenderTask):
        """Render the given task/job combo and update the status along the way.

        Args:
            job (sql.HydraRenderJob): Hydra Render Job
            task (sql.HydraRenderTask): Hydra Render Task

        """
        logger.info("Starting task with id %s on job with id %s", task.id, task.job_id)
        self.child_killed = 0
        self.child_process = None
        self.ps_util_proc = None

        render_task_cmd = task.create_task_cmd(job)
        log_path = task.get_log_path()
        logger.debug(render_task_cmd)

        try:
            log = open(log_path, 'w')
        except (IOError, OSError, WindowsError) as e:
            logger.error(e)
            self.this_node.offline()
            self.shutdown()
            return

        log.write('Hydra log file {0} on {1}\n'.format(log_path, self.this_node.host))
        log.write('RenderNode is {0}\n'.format(sys.argv))
        log.write('Command: {0}\n\n'.format(render_task_cmd))
        log.flush()
        os.fsync(log.fileno())

        try:
            # Run the job and keep track of the process
            kwargs = self.build_subprocess_args(False)
            self.child_process = subprocess.Popen(render_task_cmd, stdout=log, stderr=log, **kwargs)

            logger.info("Started PID %s to do Task %s", self.child_process.pid, task.id)

            self.ps_util_proc = psutil.Process(self.child_process.pid)
            # Wait for task to finish
            self.child_process.communicate()
        except Exception:
            # Cleanup a crash
            e = traceback.format_exc()
            logger.critical(e)
            log.write("\n\n-----------Job crashed on startup!-----------\n")
            log.write(e)

        # Done! Update the database with the results.
        if self.child_process:
            logger.info('PID %s has exited with exit code %s', self.child_process.pid, self.child_process.returncode)
        else:
            logger.info('Child process was not started, updating with exit code -1234')

        # Update Task
        logger.debug("child_killed = %s", self.child_killed)
        task.end_time = datetime.datetime.now().replace(microsecond=0)
        if self.child_process:
            if self.child_killed == 0:
                task.exit_code = self.child_process.returncode
            else:
                task.exit_code = -1
        else:
            task.exit_code = -1234

        if task.exit_code == 0:
            task.status = sql.HydraStatus.FINISHED
            task.mpf = (task.end_time - task.start_time)
        else:
            task.status = sql.HydraStatus.READY
        task.update()

        # Update Job
        failed_node = None
        if task.exit_code != 0 and self.child_killed == 0:
            failed_node = self.this_node.host

        mpf = None
        if task.exit_code == 0:
            mpf = task.mpf

        job.update_job_status(failed_node, mpf)

        # Update Node
        self.this_node = sql.HydraRenderNode.get_this_node()
        self.this_node.task_id = None

        if self.this_node.status == sql.HydraStatus.PENDING:
            new_status = sql.HydraStatus.OFFLINE
        else:
            new_status = sql.HydraStatus.IDLE

        self.this_node.status = new_status
        self.this_node.update()

        # Log and complete
        s = "\nProcess exited with code {0} at {1} on {2}\n"
        log.write(s.format(task.exit_code, task.end_time, self.this_node.host))
        self.child_process = None
        self.ps_util_proc = None

        log.close()
        if not self.keep_all_logs and task.exit_code == 0:
            try:
                os.remove(log_path)
            except Exception:
                logger.exception("Unable to remove log")

        logger.info("Done with render task %s", task.id)


if __name__ == "__main__":
    logger.info("Starting in %s", os.getcwd())
    logger.info("sys.argv %s", sys.argv)

    # Check for other RenderNode instances
    lockFile = single_instance.InstanceLock("HydraRenderNode")
    lockStatus = lockFile.is_locked()
    logger.debug("Lock File Status: %s", lockStatus)
    if not lockStatus:
        logger.critical("Only one RenderNode is allowed to run at a time! Exiting...")
        sys.exit(-1)

    # Start the render server
    RenderTCPServer()
