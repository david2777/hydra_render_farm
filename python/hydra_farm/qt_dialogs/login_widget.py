"""Login Window"""
import sys

import MySQLdb as sql
from PyQt5 import QtWidgets, uic

from hydra_farm.utils import yaml_cache
from hydra_farm.utils import resource_resolver
from hydra_farm.utils.logging_setup import logger
from hydra_farm.qt_dialogs.message_boxes import about_box

config = yaml_cache.get_hydra_cfg()


class DatabaseLogin(QtWidgets.QWidget):
    def __init__(self):
        super(DatabaseLogin, self).__init__()
        uic.loadUi(resource_resolver.get_resource('resources', 'ui', 'login.ui'), self)

        self.host = config["database"]["host"]
        self.database_name = config["database"]["db"]
        self.port = int(config["database"]["port"])

        self.db_username = None
        self.db_password = None

        self.login_button.clicked.connect(self.login_button_handler)

        self.login_success = False

    def get_values(self):
        if self.login_success:
            return self.db_username, self.db_password
        else:
            return None, None

    def close_event(self, event):
        """Make it so when the user presses the X in the window it exits
        rather than just closing the login window and opening FarmView"""
        event.accept()
        if not self.login_success:
            sys.exit(1)

    def login_button_handler(self):
        self.db_username = str(self.user.text())
        self.db_password = str(self.password.text())

        try:
            sql.connect(host=self.host, user=self.db_username, passwd=self.db_password,
                        db=self.database_name, port=self.port)
            self.login_success = True
            self.close()

        except sql.Error:
            logger.error("Could not login!")
            about_box(self, "Could Not Login", "Invalid username/password or server is down...")


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    window = DatabaseLogin()
    window.show()
    app.exec_()
