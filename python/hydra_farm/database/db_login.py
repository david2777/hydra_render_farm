"""Fetch Database Login Info"""
import sys

from hydra_farm.utils import yaml_cache
from hydra_farm.utils import password_storage
from hydra_farm.utils.logging_setup import logger

config = yaml_cache.get_hydra_cfg()


def get_database_info() -> tuple:
    """Finds and returns database connection info.

    Returns:
        tuple: (host, username, password, db_name, port) all used to connect to the DB.

    """
    logger.debug("Getting database info...")

    # Database info
    host = config['database']['host']
    domain = config['networking']['dns_domain_ext']
    if domain and host not in ["localhost", "::1"] and not host.startswith("127."):
        host = "{0}.{1}".format(host, domain)
    database_name = config['database']['db']
    port = int(config['database']['port'])
    db_username = config['database']['username']

    # Login info
    autologin = config['database']['autologin']
    db_password = None
    if autologin:
        db_password = password_storage.load_credentials(db_username)
        if not db_password:
            autologin = False

    # Prompt for login
    if not autologin:
        return_values = password_storage.qt_prompt()
        if not all(return_values):
            logger.error("Could not login!")
            sys.exit(1)
        else:
            db_username, db_password = return_values

    return host, db_username, db_password, database_name, port