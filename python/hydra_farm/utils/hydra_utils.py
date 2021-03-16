"""Misc utils"""
import re
import time
import socket
import logging

from hydra_farm.utils import yaml_cache

config = yaml_cache.get_hydra_cfg()


class Timer(object):
    def __init__(self, name: str = None, logger: logging.Logger = None, log_level: str = 'debug'):
        self.name = name if name is not None else 'Process'
        self.logger = logger
        self.log_level = log_level
        self.start = time.perf_counter()

    def log(self, name: str = None, log_level: str = None, precision: int = 3) -> str:
        name = name if name is not None else self.name
        log_level = log_level if log_level is not None else self.log_level
        elapsed = self.end(precision)
        log = '{0} took {1} seconds'.format(name, elapsed)
        if self.logger:
            getattr(self.logger, log_level)(log)
        else:
            print(log)
        return log

    def end(self, precision: int = 3) -> str:
        return '%.{}f'.format(precision) % (time.perf_counter() - self.start)


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
