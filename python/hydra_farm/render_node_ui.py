# Standard
import sys
import os
import logging

# Third Party
from PyQt5 import QtGui, QtCore

# Hydra Qt
from hydra_farm.compiled_qt.UI_RenderNodeMain import Ui_RenderNodeMainWindow
from hydra_farm.qt_dialogs.node_editor_dialog import NodeEditorDialog
from hydra_farm.qt_dialogs.message_boxes import about_box, yes_no_box

# Hydra
import hydra_farm.hydra.hydra_sql as sql
from hydra_farm.utils import hydra_threading
from hydra_farm.utils.long_strings import render_node_error_string
from hydra_farm.utils.logging_setup import logger, output_window_formatter
from hydra_farm.utils.single_instance import InstanceLock
import hydra_farm.utils.hydra_utils as hydra_utils


# Move threads to idle loops???

class EmittingStream(QtCore.QObject):
    """For writing text to the console output"""
    textWritten = QtCore.pyqtSignal(str)

    def write(self, text):
        self.textWritten.emit(str(text))


class RenderNodeMainUI(QtGui.QMainWindow, Ui_RenderNodeMainWindow):
    def __init__(self):
        QtGui.QMainWindow.__init__(self)
        self.setupUi(self)

        with open(hydra_utils.find_resource("assets/styleSheet.css"), "r") as myStyles:
            self.setStyleSheet(myStyles.read())

        self.thisNode = sql.HydraRenderNode.get_this_node()
        self.isVisible = True

        self.renderServerStatus = False

        if not self.thisNode or not self.thisNode.is_render_node or not self.thisNode.ip_addr:
            logger.critical("This is not a render node! A render node must be marked as such and have an IP address "
                            "assigned to it in the database.")
            about_box(self, "Error", render_node_error_string)
            sys.exit(1)

        self.build_ui()
        self.connect_buttons()
        self.update_thisnode()
        self.startup_servers()

        logger.info("Render Node Main is live! Waiting for tasks...")

        try:
            autoHide = True if str(sys.argv[1]).lower() == "true" else False
        except IndexError:
            autoHide = False

        if autoHide and self.trayIconBool:
            logger.info("Autohide is enabled!")
            self.hide_window()
        else:
            self.show()

    def write_to_window_logger(self, text):
        """Append text to the QTextEdit."""
        cursor = self.outputTextEdit.textCursor()
        cursor.movePosition(QtGui.QTextCursor.End)
        cursor.insertText(text)
        self.outputTextEdit.setTextCursor(cursor)
        self.outputTextEdit.ensureCursorVisible()

    def clear_window_logger(self):
        choice = yes_no_box(self, "Confirm", "Really clear output?")
        if choice == QtGui.QMessageBox.Yes:
            self.outputTextEdit.clear()
            logger.info("Output cleared")

    def build_ui(self):
        def addItem(name, handler, statusTip, menu):
            action = QtWidgets.QAction(name, self)
            action.setStatusTip(statusTip)
            action.triggered.connect(handler)
            menu.addAction(action)

        # Add Logging handlers for output field
        emStream = EmittingStream(textWritten=self.write_to_window_logger)
        handler = logging.StreamHandler(emStream)
        handler.setLevel(logging.INFO)
        handler.setFormatter(output_window_formatter)
        logger.addHandler(handler)

        sys.stdout = EmittingStream(textWritten=self.write_to_window_logger)
        sys.stderr = EmittingStream(textWritten=self.write_to_window_logger)

        # Get Pixmaps and Icon
        self.donePixmap = QtGui.QPixmap(hydra_utils.find_resource("assets/status/green.png"))
        self.inProgPixmap = QtGui.QPixmap(hydra_utils.find_resource("assets/status/yellow.png"))
        self.needsAttentionPixmap = QtGui.QPixmap(hydra_utils.find_resource("assets/status/red.png"))
        self.nonePixmap = QtGui.QPixmap(hydra_utils.find_resource("assets/status/none.png"))
        self.notStartedPixmap = QtGui.QPixmap(hydra_utils.find_resource("assets/status/gray.png"))
        self.refreshPixmap = QtGui.QPixmap(hydra_utils.find_resource("assets/refresh.png"))
        self.refreshIcon = QtGui.QIcon()
        self.refreshIcon.addPixmap(self.refreshPixmap)
        self.RIcon = QtGui.QIcon(hydra_utils.find_resource("assets/RenderNodeMain.png"))

        self.isVisible = True

        self.refreshButton.setIcon(self.refreshIcon)

        self.renderServerPixmap.setPixmap(self.notStartedPixmap)
        self.scheduleThreadPixmap.setPixmap(self.notStartedPixmap)
        self.pulseThreadPixmap.setPixmap(self.notStartedPixmap)
        self.setWindowIcon(self.RIcon)

        # Setup tray icon
        self.trayIcon = QtGui.QSystemTrayIcon()
        self.trayIconBool = self.trayIcon.isSystemTrayAvailable()
        if self.trayIconBool:
            self.trayIcon.setIcon(self.RIcon)
            self.trayIcon.show()
            self.trayIcon.setVisible(True)
            self.trayIcon.activated.connect(self.activate)
            self.trayIcon.messageClicked.connect(self.activate)

            # Tray Icon Context Menu
            self.taskIconMenu = QtWidgets.QMenu(self)

            addItem("Open", self.show_window,
                    "Show the RenderNodeMain Window", self.taskIconMenu)
            self.taskIconMenu.addSeparator()
            addItem("Update", self.update_thisnode,
                    "Fetch the latest information from the Database", self.taskIconMenu)
            self.taskIconMenu.addSeparator()
            addItem("Online", self.online_thisnode,
                    "Online this node", self.taskIconMenu)
            addItem("Offline", self.offline_thisnode,
                    "Offline this node", self.taskIconMenu)
            addItem("GetOff!", self.get_off_thisnode,
                    "Kill the current task and offline this node", self.taskIconMenu)

            self.trayIcon.setContextMenu(self.taskIconMenu)
        else:
            logger.error("Tray Icon Error! Could not create tray icon.")
            about_box(self, "Tray Icon Error",
                      "Could not create tray icon. Minimizing to tray has been disabled.")
            self.trayButton.setEnabled(False)

    def connect_buttons(self):
        self.trayButton.clicked.connect(self.hide_window)
        self.onlineButton.clicked.connect(self.online_thisnode)
        self.offlineButton.clicked.connect(self.offline_thisnode)
        self.getoffButton.clicked.connect(self.get_off_thisnode)
        self.clearButton.clicked.connect(self.clear_window_logger)
        self.refreshButton.clicked.connect(self.update_thisnode)
        self.edit_this_node_button.clicked.connect(self.open_node_editor)
        self.auto_update_cbx.stateChanged.connect(self.auto_update_handler)
        if not self.trayIconBool:
            self.trayButton.setEnabled(False)

    # DO NOT RENAME THIS FUNCTION
    def closeEvent(self, event):
        choice = yes_no_box(self, "Confirm", "Really exit the RenderNodeMain server?")
        if choice == QtGui.QMessageBox.Yes:
            self.exit()
        else:
            event.ignore()

    def exit(self):
        self.shutdown()
        self.trayIcon.hide()
        event.accept()
        sys.exit(0)

    def shutdown(self):
        logger.info("Shutting down...")
        if self.pulseThread.status:
            self.pulseThread.terminate()
        if self.schedThread.status:
            self.schedThread.terminate()
        if self.autoUpdateThread.status:
            self.autoUpdateThread.terminate()
        if self.renderServerStatus:
            self.renderServer.shutdown()
        logger.debug("All servers Shutdown")

    def reboot(self):
        # TODO: Make a timeout box so the user can stop a reboot
        logger.info("Rebooting Node...")
        self.shutdown()
        self.renderServer.reboot()

    def auto_update_handler(self):
        """Toggles Auto Updater
        Note that this is run AFTER the CheckState is changed so when we do
        .isChecked() it's looking for the state after it has been checked."""
        if not self.auto_update_cbx.isChecked():
            self.autoUpdateThread.terminate()
        else:
            self.autoUpdateThread.start()

    def show_window(self):
        self.isVisible = True
        self.show()
        self.update_thisnode()

    def hide_window(self):
        self.isVisible = False
        self.trayIcon.show()
        self.hide()

    def activate(self, reason):
        if reason == 2:
            self.show_window()

    def __icon_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.show_window()

    def online_thisnode(self):
        response = self.thisNode.online()
        self.update_thisnode()
        if response:
            logger.info("Node Onlined")
        else:
            logger.error("Node could not be Onlined!")

    def offline_thisnode(self):
        response = self.thisNode.offline()
        self.update_thisnode()
        if response:
            logger.info("Node Offlined")
        else:
            logger.error("Node could not be Offlined!")

    def get_off_thisnode(self):
        response = self.thisNode.get_off()
        self.update_thisnode()
        if response:
            logger.info("Node Offlined and Task Killed")
        else:
            logger.error("Node could not be Onlined or the Task could not be killed!")

    def startup_servers(self):
        logger.debug("Firing up main threads")
        # Start Render Server
        self.renderServer = RenderNode.RenderTCPServer()
        self.renderServerStatus = True
        self.renderServerPixmap.setPixmap(self.donePixmap)
        logger.info("Render Server Started!")

        # Start Pulse Thread
        self.pulseThread = hydra_threading.StoppableThread(pulse, 60, "Pulse_Thread")
        self.pulseThread.start()
        self.pulseThreadPixmap.setPixmap(self.donePixmap)
        logger.info("Pulse Thread started!")

        # Start Auto Update Thread
        QtCore.pyqtSignal("update_thisnode")
        QtCore.QObject.connect(self, QtCore.pyqtSignal("update_thisnode"), self.update_thisnode)

        self.autoUpdateThread = hydra_threading.StoppableThread(self.update_thisnode_signaler, 1,
                                                        "AutoUpdate_Thread")
        self.autoUpdateThread.start()
        self.start_schedule_thread()

    def start_schedule_thread(self):
        """This is in it's own function because it starts and stops often"""
        if bool(self.currentScheduleEnabled) and self.currentSchedule:
            self.schedThread = schedulerThread(self.scheduler_main,
                                               "Schedule_Thread", None)
            self.schedThread.start()
            self.scheduleThreadPixmap.setPixmap(self.donePixmap)
            logger.info("Schedule Thread started!")
        else:
            logger.info("Schedule disabled. Running in manual control mode.")
            self.scheduleThreadPixmap.setPixmap(self.nonePixmap)

    def open_node_editor(self):
        response = self.node_editor()
        if response:
            logger.info("Updating this node...")
            logger.info("Node updated!")
        else:
            logger.info("No changes detected. Nothing was changed.")

    def node_editor(self):
        comps = self.thisNode.capabilities.split(" ")
        defaults = {"host": self.thisNode.host,
                    "priority": self.thisNode.min_priority,
                    "comps": comps,
                    "schedule_enabled": int(self.thisNode.schedule_enabled),
                    "week_schedule": self.thisNode.week_schedule,
                    "is_render_node": bool(self.thisNode.is_render_node),
                    "ip_addr": self.thisNode.ip_addr}
        edits = NodeEditorDialog.create(defaults)
        # logger.debug(edits)
        if edits:
            schedEnabled = bool(edits["schedule_enabled"])
            query = "UPDATE HydraRenderNode SET min_priority = %s"
            query += ", schedule_enabled = %s, capabilities = %s"
            query += ", is_render_node = %s, ip_addr = %s"
            query += " WHERE id = %s"
            editsTuple = (edits["priority"], schedEnabled, edits["comps"],
                          edits["is_render_node"], edits["ip_addr"], self.thisNode.id)
            with sql.Transaction() as t:
                t.cur.execute(query, editsTuple)
            self.update_thisnode()
            return True

    def update_thisnode_signaler(self):
        self.emit(QtCore.pyqtSignal("update_thisnode"))

    def update_thisnode(self):
        self.thisNode = sql.HydraRenderNode.fetch("WHERE id = %s", (self.thisNode.id,))

        # Check for changes in schedule
        if self.thisNode.week_schedule != self.currentSchedule or self.thisNode.schedule_enabled != self.currentScheduleEnabled:
            self.currentSchedule = self.thisNode.week_schedule
            self.currentScheduleEnabled = self.thisNode.schedule_enabled
            if self.schedThread.status:
                self.schedThread.terminate()
                app.processEvents()
            self.start_schedule_thread()

        self.node_name_label.setText(self.thisNode.host)
        self.node_status_label.setText(self.thisNode.status_enum.nice_name)
        taskText = str(self.thisNode.task_id)
        self.task_id_label.setText(taskText)
        self.node_version_label.setText(str(self.thisNode.software_version))
        self.min_priority_label.setText(str(self.thisNode.min_priority))
        self.capabilities_label.setText(self.thisNode.capabilities)
        self.pulse_label.setText(str(self.thisNode.pulse))

        if self.trayIconBool:
            niceStatus = self.thisNode.status_enum.nice_name
            iconStatus = "Hydra RenderNodeMain\nNode: {0}\nStatus: {1}\nTask: {2}"
            self.trayIcon.setToolTip(iconStatus.format(self.thisNode.host,
                                                       niceStatus,
                                                       taskText))

    def hidden_about_box(self, title="", msg=""):
        """Creates a window that has been minimzied to the tray"""
        if self.isVisible:
            about_box(self, title, msg)
        else:
            self.trayIcon.showMessage(title, msg)

    def scheduler_main(self):
        if not self.thisNode:
            self.scheduleThreadPixmap.setPixmap(self.needsAttentionPixmap)
            logger.error("Node OBJ not found by scheduler_main! Checking again in 24 hours.")
            # Sleep for 24 hours
            return 86400

        self.update_thisnode()

        sleepTime, nowStatus = node_scheduling.calculate_sleep_time_from_node(self.thisNode.id)
        if not sleepTime or not nowStatus:
            logger.error("Could not find schdule! Checking again in 24 hours.")
            return 86400

        if nowStatus == sql.READY:
            self.startup_event()
        else:
            self.shutdown_event()

        # Add an extra minute just in case
        return sleepTime + 60

    def startup_event(self):
        logger.info("Triggering Startup Event")
        self.online_thisnode()

    def shutdown_event(self):
        logger.info("Triggering Shutdown Event")
        self.offline_thisnode()


class schedulerThread(hydra_threading.StoppableThread):
    """Modified version of the StoppableThread"""

    def tgt(self):
        while not self.stop_event.is_set():
            # target = scheduler_main from the RenderNodeMainUI class
            self.interval = self.target_func()
            hours = int(self.interval / 60 / 60)
            minutes = int(self.interval / 60 % 60)
            logger.info("Scheduler Sleeping for %d hours and %d minutes", hours, minutes)
            self.stop_event.wait(self.interval)


def pulse():
    host = hydra_utils.my_host_name()
    with sql.Transaction() as t:
        t.cur.execute("UPDATE HydraRenderNode SET pulse = NOW() "
                      "WHERE host = '{0}'".format(host))


if __name__ == "__main__":
    logger.info("Starting in %s", os.getcwd())
    logger.info("arglist is %s", sys.argv)

    app = QtGui.QApplication(sys.argv)
    app.quitOnLastWindowClosed = False

    lockFile = InstanceLock("HydraRenderNode")
    lockStatus = lockFile.is_locked()
    logger.debug("Lock File Status: %s", lockStatus)
    if not lockStatus:
        logger.critical("Only one RenderNode is allowed to run at a time! Exiting...")
        about_box(None, "ERROR", "Only one RenderNode is allowed to run at a time! Exiting...")
        sys.exit(-1)

    window = RenderNodeMainUI()
    retcode = app.exec_()
    lockFile.remove()
    sys.exit(retcode)
