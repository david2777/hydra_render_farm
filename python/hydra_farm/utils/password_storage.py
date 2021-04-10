"""Store and Retrieve Login Info"""
import sys
from getpass import getpass

import MySQLdb
import keyring
from PyQt5 import QtWidgets

from hydra_farm.utils import yaml_cache
from hydra_farm.utils.logging_setup import logger
from hydra_farm.qt_dialogs.login_widget import DatabaseLogin

config = yaml_cache.get_hydra_cfg()


def store_credentials(username: str, password: str):
    """Store login credentials using keyring.

    Args:
        username (str): Username
        password (str): Password

    Returns:
        None

    """
    keyring.set_password("hydra_farm", username, password)
    logger.info("Password Stored in Credentials Vault")


def load_credentials(username: str) -> str:
    """Returns the password from the keyring given a username.

    Args:
        username (str): Username

    Returns:
        str: Password

    """
    logger.info("Fetching login for %s", username)
    return keyring.get_password("hydra_farm", username)


def update_autologin_user(new_username: str):
    """Update the autologin user in the hydra cfg.

    Args:
        new_username (str): New username to store in the hydra cfg.

    Returns:
        None

    """
    if config['database']['username'] != new_username:
        config['database']['username'] = new_username
        config.write_yaml()


def console_prompt():
    """Console prompt to store login information.

    Returns:
        None

    """
    print("\n\nStore Auto Login information?")
    # Get login info from the user
    username = input("Username: ")
    password = getpass("Password: ")
    
    # Get db server info
    host = config['database']['host']
    domain = config['networking']['dns_domain_ext']
    if domain and host not in ["localhost", "::1"] and not host.startswith("127."):
        host += f".{domain}"
    database_name = config['database']['db']
    port = int(config['database']['port'])

    # Make sure the login is valid and then store it in the keyring
    try:
        MySQLdb.connect(host=host, user=username, passwd=password, db=database_name, port=port)
        store_credentials(username, password)
        update_autologin_user(username)
    except MySQLdb.Error:
        print("Login information was invalid, please again.")
        console_prompt()


def qt_prompt() -> tuple:
    """QT prompt to get login infromation from the user.

    Returns:
        tuple: (Username, Password) tuple.

    """
    app = QtWidgets.QApplication(sys.argv)
    login_win = DatabaseLogin()
    login_win.show()
    app.exec_()
    username, password = login_win.get_values()
    auto_login = config['database']['autologin']
    if username and auto_login:
        update_autologin_user(username)
        store_credentials(username, password)
    return username, password
