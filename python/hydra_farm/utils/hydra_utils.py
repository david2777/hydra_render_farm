"""Misc utils"""
import re
import time
import socket
import inspect
import logging

from hydra_farm.utils import yaml_cache

config = yaml_cache.get_hydra_cfg()


class Timer(object):
    """Simple Timer"""
    def __init__(self, name: str = None, logger: logging.Logger = None, log_level: str = 'debug'):
        """Simple Timer

        Args:
            name (str): Name to log, default "Process".
            logger (logging.Logger): Logger to log results to. Default None will print instead.
            log_level (str): Log level as a string, eg "debug", "info", etc. Default "debug".

        """
        self.name = name if name is not None else 'Process'
        self.logger = logger
        self.log_level = log_level
        if self.logger and not hasattr(self.logger, self.log_level):
            raise ValueError(f'Logger {self.logger} has no level {self.log_level}')
        self.start = time.perf_counter()

    def log(self, name: str = None, log_level: str = None, precision: int = 3) -> str:
        """Log the result to the logger.

        Args:
            name (str): Name to log, default from self.name.
            log_level (str): Log level as a string, eg "debug", "info", etc. Default "debug".
            precision (int): Floating point precision for the timer, default 3.

        Returns:
            str: The log statement

        """
        log_level = log_level if log_level is not None else self.log_level
        if self.logger and not hasattr(self.logger, log_level):
            raise ValueError(f'Logger {self.logger} has no level {self.log_level}')
        elapsed = self.end(precision)
        log = f'{name if name is not None else self.name} took {elapsed} seconds'
        if self.logger:
            getattr(self.logger, log_level)(log)
        else:
            print(log)
        return log

    def end(self, precision: int = 3) -> str:
        """Return the timer value as a string.

        Args:
            precision (int): Floating point precision for the timer, default 3.

        Returns:
            str: The timer value as a string, truncated to the precision value

        """
        return '%.{}f'.format(precision) % (time.perf_counter() - self.start)


def hasattr_static(obj: object, name: str) -> bool:
    """hasattr without dynamic lookup via __getattr__ or __getattribute__.

    Args:
        obj (object): Object to check
        name (str): Attr to check for

    Returns:
        bool: True if the object has the attr, False if not.

    """
    try:
        inspect.getattr_static(obj, name)
        return True
    except AttributeError:
        return False


def my_host_name() -> str:
    """Returns the host name plus the DNS domain extension if enabled.

    Returns:
        str: Host name plus DNS domain extension if enabled.

    """
    host = socket.gethostname()
    domain = config['networking']['dns_domain_ext']
    if domain:
        return "{0}.{1}".format(host, domain)
    else:
        return host


def strip_sql_query(sql_query: str) -> str:
    """Strip whitespace and newlines from a SQL query for logging.

    Args:
        sql_query (str): SQL query

    Returns:
        str: SQL query with extra whitespace and all newlines stripped.

    """
    sql_query = re.sub(' +', ' ', sql_query)
    return re.sub('\\n', '', sql_query)
