"""Threading Setup"""
import threading
from typing import Callable, Iterable, Mapping

from hydra_farm.utils.logging_setup import logger


class HydraThread(threading.Thread):
    """Stoppable thread class with conveniences such as interval, delay, and single shot (run once and exit).

    """
    stopped: bool = False
    # Type hinting for threading.Thread
    _target: Callable
    _args: tuple
    _kwargs: Mapping

    def __init__(self, name: str, target: Callable, interval: int = None, delay: int = None,
                 single_shot: bool = False, args: Iterable = None, kwargs: Mapping = None):
        """Initialize the HydraThread, does not start the thread.

        Args:
            name (str): Name of the thread object for display.
            target (Callable): Function or Method to call.
            interval (int): Optional interval in seconds.
            delay (int): Optional start delay in seconds.
            single_shot (bool): Optional flag to have the thread run once and then exit.
            args (Iterable): Args to pass to the target.
            kwargs (Mapping): Kwargs to pass to the target.

        """
        if args is None:
            args = tuple()
        if kwargs is None:
            kwargs = {}

        self.interval = interval
        self.delay = delay
        self.single_shot = single_shot
        self.stop_event = threading.Event()

        super(HydraThread, self).__init__(target=target, name=name, args=args, kwargs=kwargs, daemon=True)

    def __repr__(self) -> str:
        return f"HydraThread [{self.name}]"

    def run(self) -> None:
        """Run the thread until the stop event is set.

        """
        if self.delay:
            self.stop_event.wait(self.delay)
        try:
            while not self.stop_event.is_set():
                self._target(*self._args, **self._kwargs)
                if self.interval:
                    self.stop_event.wait(self.interval)
                if self.single_shot:
                    self.stop_event.set()
        finally:
            del self._target, self._args, self._kwargs
            self.stopped = True

    def terminate(self) -> None:
        """Terminate the thread.

        """
        self.stop_event.set()


class HydraThreadManager(object):
    """Thread manager class, not to mean to be instantiated but rather used as a container for managing HydraTreads.

    """
    all_threads: set[HydraThread] = set()

    def __new__(cls, *args, **kwargs):
        raise TypeError("Cannot Instance HydraThreadManager")

    @classmethod
    def create_idle_loop(cls, thread_name: str, target: Callable, interval: int = None) -> HydraThread:
        """Convenience to add a simple thread to the manager and return that thread.

        Args:
            thread_name (str): Name of the thread object for display.
            target (Callable): Function or Method to call.
            interval (int): Optional interval in seconds.

        Returns:
            HydraThread: Thread object that was created.

        """
        thread = HydraThread(thread_name, target, interval=interval)
        logger.debug('Adding thread %s @ %s to HydraThreadManger', thread_name, id(thread))
        cls.all_threads.add(thread)
        thread.start()
        return thread

    @classmethod
    def add_thread(cls, thread: HydraThread) -> None:
        """Convenience to add a thread to the manager.

        Args:
            thread (HydraThread): HydraThread object.

        """
        logger.debug('Adding thread %s @ %s to HydraThreadManger', thread.name, id(thread))
        cls.all_threads.add(thread)
        thread.start()

    @classmethod
    def shutdown(cls) -> None:
        """Shutdown all threads.

        """
        for thread in cls.all_threads:
            logger.debug("Killing %s Thread...", thread.name)
            thread.terminate()

    @classmethod
    def run_forever(cls) -> None:
        """Block and run all threads until they're all stopped.

        """
        logger.debug('HydraThreadManager running forever...')
        while any([not t.stopped for t in cls.all_threads]):
            pass
