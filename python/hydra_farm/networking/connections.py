"""A Connection allows a Client to ask a Server for an Answer to a Question."""
import json
import socket
import traceback

from hydra_farm import constants
from hydra_farm.utils import yaml_cache
from hydra_farm.utils.logging_setup import logger

config = yaml_cache.get_hydra_cfg()


def send_request(address: str, port: int, request: "HydraRequest") -> "HydraResponse":
    """Send a request to a given address across a given port and return the response if successful.

    Args:
        address (str): Address to send the request to.
        port (int): Port to send the request across.
        request (HydraRequest): HydraRequest instance of the request.

    Returns:
        HydraResponse: HydraResponse instance of the response from the server.

    """
    logger.debug("Opening TCP Connection to %s:%d", address, port)
    try:
        sock = socket.create_connection((address, port))
    except TimeoutError:
        logger.exception('Could not connect to %s:%d', address, port)
        response = HydraResponse.from_args('TimeoutError')
        return response

    try:
        sock.sendall(request.as_json_bytes())
        sock.shutdown(socket.SHUT_WR)
        answer_bytes = sock.recv(constants.MANYBYTES)
        try:
            response = HydraResponse.from_bytes(answer_bytes)
        except EOFError:
            logger.error("EOF Error: answer_bytes = %s", answer_bytes.decode())
            response = HydraResponse.from_args('EOF Error')
    except socket.error:
        logger.exception('SocketError')
        response = HydraResponse.from_args('Socket Error')
    except Exception:
        logger.exception('Unhandled Exception in send_request')
        e = traceback.format_exc().splitlines()
        response = HydraResponse.from_args(f'Unhandled Exception: {e[-1]}')
    finally:
        sock.close()
        logger.debug("TCP Connection to %s:%d was closed.", address, port)

    return response


class _HydraDataStream(object):
    """Base definition for a TCP request/response data stream wrapper.

    """
    _all: tuple

    def __repr__(self):
        return f'{self.__class__.__name__} {self.dict}'

    @property
    def dict(self) -> dict:
        """Return a dict of all keys from _all and their values from this instance, eg {key: getattr(self, key)}.

        Returns:
            dict: Dict of all keys from _all where {key: getattr(self, key)}

        """
        return {k: getattr(self, k) for k in self._all}

    def as_json_bytes(self) -> bytes:
        """Returns the instance data as JSON encoded bytes.

        Returns:
            bytes: JSON encoded bytes of the instance data as defined in _all.

        """
        return json.dumps(self.dict).encode()

    @classmethod
    def from_args(cls, *args, **kwargs):
        """Factory method to construct from arguments.

        """
        raise NotImplementedError('Must define in a subclass')

    @classmethod
    def from_bytes(cls, stream_data: bytes):
        """Factory method to construct from bytes.

        """
        raise NotImplementedError('Must define in a subclass')


class HydraRequest(_HydraDataStream):
    """Class to wrap a TCP request into an object with factory methods to create from bytes and a method to
    cast to JSON encoded bytes.

    """
    cmd: str
    args: tuple
    kwargs: dict
    _all = ('cmd', 'args', 'kwargs')

    @classmethod
    def from_args(cls, cmd: str = None, args: tuple = None, kwargs: dict = None) -> "HydraRequest":
        """Factory method to construct from arguments.

        Args:
            cmd (str): Command you want the server to preform.
            args (tuple): Tuple of args to pass to the cmd.
            kwargs (kwargs): Dict of kwargs to pass to the cmd.

        Returns:
            HydraRequest: Request instance constructed with the given args.

        """
        ins = cls()
        ins.cmd = cmd if cmd is not None else ""
        ins.args = args if args is not None else tuple()
        ins.kwargs = kwargs if kwargs is not None else {}
        return ins

    @classmethod
    def from_bytes(cls, stream_data: bytes) -> "HydraRequest":
        """Factory method to construct from bytes.

        Args:
            stream_data (bytes): JSON encoded bytes.

        Returns:
            HydraRequest: Request instance constructed by the given bytes.

        """
        data = json.loads(stream_data.decode())
        ins = cls()
        ins.cmd = data.get('cmd', '')
        ins.args = tuple(data.get('args', []))
        ins.kwargs = data.get('kwargs', {})
        return ins


class HydraResponse(_HydraDataStream):
    """Class to wrap a TCP response into an object with factory methods to create from bytes and a method to
    cast to bytes.

    """
    msg: str
    err: bool
    _all = ('msg', 'err')

    @classmethod
    def from_args(cls, msg: str = None, err: bool = None) -> "HydraResponse":
        """Factory method to construct from arguments.

        Args:
            msg (str): Response message.
            err (bool): Error status bool.

        Returns:
            HydraResponse: Response instanced constructed by the given args.

        """
        ins = cls()
        ins.msg = msg if msg is not None else ""
        ins.err = err if err is not None else True
        return ins

    @classmethod
    def from_bytes(cls, stream_data: bytes) -> "HydraResponse":
        """Factory method to construct from bytes.

        Args:
            stream_data (bytes): JSON encoded bytes.

        Returns:
            HydraResponse: Response instanced constructed by the given args.

        """
        data = json.loads(stream_data.decode())
        ins = cls()
        ins.msg = data.get('msg', '')
        ins.err = data.get('err', True)
        return ins
