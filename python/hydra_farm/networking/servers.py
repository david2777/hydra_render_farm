import traceback
import socketserver
from typing import Generic

from hydra_farm.utils.logging_setup import logger
from hydra_farm.utils import hydra_threading as ht
from hydra_farm.networking.connections import HydraRequest, HydraResponse


class HydraTCPServerThread(ht.HydraThread):
    """TCP Server that runs inside of a HydraThread.

    """
    server: "_HydraSocketServer"
    handler: Generic = None

    def __init__(self, port: int):
        """Open the server and have it server forever inside of a new thread.

        Args:
            port (int): Port to open the server on.

        """
        self.server = _HydraSocketServer(("", port), _HydraTCPHandler)
        logger.debug('Starting HydraTCPServerThread on port {}'.format(port))
        super(HydraTCPServerThread, self).__init__('HydraTCPServer', self.server.serve_forever)

    def terminate(self) -> None:
        """Shutdown the socket server and then shut down the tread.

        """
        self.server.shutdown()
        super().terminate()


class _HydraSocketServer(socketserver.TCPServer):
    """Basic TCP Socket Server setup.

    """
    allow_reuse_address = True
    thread: HydraTCPServerThread


class _HydraTCPHandler(socketserver.StreamRequestHandler):
    """Custom TCP Handler that attempts to call a method called `handle_connection` from the handler attached to the
    socket server.

    """
    def handle(self) -> None:
        """Attempts to load the request into a HydraRequest, call the handle_connection method from the handler
        attached the server, formulate a response, and send that response.

        """
        # Get request
        request = self.rfile.readline().strip()
        logger.debug('HydraRequest from %s: "%s"', self.client_address[0], request)
        request = HydraRequest.from_bytes(request)

        handler = getattr(self.server, 'handler', None)

        if handler:
            try:
                response = handler.handle_connection(request)
            except Exception:
                logger.exception('Unhandled Exception in _HydraTCPHandler.handle')
                e = traceback.format_exc().splitlines()
                response = HydraResponse.from_args('Unhandled Exception: {}'.format(e[-1]))
        elif request.cmd == 'echo':
            try:
                res = request.args[0]
            except KeyError:
                res = 'echo'
            response = HydraResponse.from_args(res, False)
        else:
            err = '{} has no handler!'.format(self.server.__class__.__name__)
            logger.error(err)
            response = HydraResponse.from_args(err)

        # Respond
        result = response.as_json_bytes()
        logger.debug('Responding to %s: "%s"', self.client_address[0], result)
        self.wfile.write(result)


def start_server():
    from hydra_farm.utils import yaml_cache
    _cfg = yaml_cache.get_hydra_cfg()
    _port = _cfg['networking']['host_port']
    if not _port:
        raise ValueError('No host_port found in "{}"'.format(_cfg.yaml_path))
    server = HydraTCPServerThread(_port)
    ht.HydraThreadManager.add_thread(server)
    ht.HydraThreadManager.run_forever()
    return server


if __name__ == '__main__':
    start_server()
