"""Qt Widgets used in Farm View"""
import socket
import datetime
from typing import Callable

from PyQt5 import QtGui, QtWidgets

from hydra_farm.utils import yaml_cache
from hydra_farm.database import enums
from hydra_farm.database import hydra_db as sql

config = yaml_cache.get_hydra_cfg()
THIS_USER = config['database']['username']  # TODO: What happens if the user logs in after launching?
THIS_USER = THIS_USER if THIS_USER else 'HydraUser'
THIS_HOST = socket.gethostname()

__all__ = ['FarmViewMenu', 'JobTreeItem', 'TaskTreeItem', 'NodeTreeItem']


class FarmViewMenu(QtWidgets.QMenu):
    """Simple QMenu that fetches data from the main Farm View window"""

    def __init__(self, main_window: QtWidgets.QMainWindow):
        """Simple QMenu that fetches data from the main Farm View window

        Args:
            main_window (QtWidgets.QMainWindow): Main Farm View Window Instance

        """
        super(FarmViewMenu, self).__init__(main_window)
        self.main_window = main_window
        self.aboutToHide.connect(self.main_window.reset_status_bar)

    def add_action(self, name: str, callback: Callable = None, status_tip: str = None) -> QtWidgets.QAction:
        """Add and return an action to the menu.

        Args:
            name (str): Name of the action to display in the menu.
            callback (Callable): Optional callback to run when the action is triggered.
            status_tip (str): Optional status tip to show in the status bar.

        Returns:
            QtWidgets.QAction: Created QAction.

        """
        action = QtWidgets.QAction(name, self)
        if status_tip:
            action.setStatusTip(status_tip)
        if callback:
            action.triggered.connect(callback)
            hotkey = self.main_window.all_hotkeys.get(callback, None)
            if hotkey:
                action.setShortcut(QtGui.QKeySequence(hotkey))
        self.addAction(action)
        return action


class JobTreeItem(QtWidgets.QTreeWidgetItem):
    """QTreeWidgetItem for representing Jobs in the Job Tree"""
    tree_widget: QtWidgets.QTreeWidget
    job: sql.HydraRenderJob

    def __init__(self, tree_widget: QtWidgets.QTreeWidget, job: sql.HydraRenderJob):
        """QTreeWidgetItem for representing Jobs in the Job Tree

        Args:
            tree_widget (QtWidgets.QTreeWidget): Tree widget that the item is being added to (Job Tree)
            job (sql.HydraRenderJob): HydraRenderJob Record

        """
        super(JobTreeItem, self).__init__(tree_widget)
        self.tree_widget = tree_widget
        self.job = job
        self.update()

    def update(self):
        """Update item data and colors from the Job record.

        """
        # Format Data
        percent = "{0:.0f}%".format(self.job.task_done / self.job.task_total * 100)
        task_string = "{0} ({1}/{2})".format(percent, self.job.task_done, self.job.task_total)
        job_data = (self.job.id, self.job.name, self.job.status_enum.nice_name, task_string,
                    self.job.owner, self.job.priority, self.job.mpf, self.job.attempts)
        job_data = tuple(map(str, job_data))
        
        # Update self
        for i, data in enumerate(job_data):
            self.setData(i, 0, str(data))
        
        # Set Archived Color
        if self.job.archived:
            for i in range(0, self.tree_widget.columnCount()):
                self.setBackground(i, QtGui.QColor(200, 200, 200))

        # Set Status Color
        self.setBackground(2, enums.Color[self.job.status].q_color)
        
        # User Name Bold
        if self.job.owner == THIS_USER:
            font = QtGui.QFont()
            font.setWeight(QtGui.QFont.DemiBold)
            self.setFont(4, font)

        # Set errors color
        if self.job.attempts:
            self.setBackground(7, QtGui.QColor('#ff9494'))


class TaskTreeItem(QtWidgets.QTreeWidgetItem):
    """QTreeWidgetItem for representing Tasks in the Task Tree"""
    tree_widget: QtWidgets.QTreeWidget
    task: sql.HydraRenderTask

    def __init__(self, tree_widget: QtWidgets.QTreeWidget, task: sql.HydraRenderTask):
        """QTreeWidgetItem for representing Tasks in the Task Tree

        Args:
            tree_widget (QtWidgets.QTreeWidget): Tree widget that the item is being added to (Task Tree)
            task (sql.HydraRenderTask): HydraRenderTask Record

        """
        super(TaskTreeItem, self).__init__(tree_widget)
        self.tree_widget = tree_widget
        self.task = task
        self.update()
    
    def update(self):
        """Update item data and colors from the Task record.

        """
        if self.task.end_time:
            duration = self.task.end_time - self.task.start_time
        elif self.task.start_time:
            duration = datetime.datetime.now().replace(microsecond=0) - self.task.start_time
        else:
            duration = "None"

        start_time = str(self.task.start_time)[5:] if self.task.start_time else "None"
        end_time = str(self.task.end_time)[5:] if self.task.end_time else "None"

        task_data = (self.task.id, self.task.status_enum.nice_name, self.task.host, self.task.start_frame,
                     self.task.end_frame, start_time, end_time, duration, self.task.exit_code)

        for i, data in enumerate(task_data):
            self.setData(i, 0, str(data))

        self.setBackground(2, enums.Color[self.task.status].q_color)
        if self.task.host == THIS_HOST and self.task.status != sql.HydraStatus.READY:
            font = QtGui.QFont()
            font.setWeight(QtGui.QFont.DemiBold)
            self.setFont(2, font)


class NodeTreeItem(QtWidgets.QTreeWidgetItem):
    """QTreeWidgetItem for representing Tasks in the Node Tree"""
    tree_widget: QtWidgets.QTreeWidget
    node: sql.HydraRenderNode

    def __init__(self, tree_widget: QtWidgets.QTreeWidget, node: sql.HydraRenderNode):
        """QTreeWidgetItem for representing Tasks in the Task Tree

        Args:
            tree_widget (QtWidgets.QTreeWidget): Tree widget that the item is being added to (Node Tree)
            node (sql.HydraRenderNode): HydraRenderNode Record

        """
        super(NodeTreeItem, self).__init__(tree_widget)
        self.tree_widget = tree_widget
        self.node = node
        self.update()
        
    def update(self):
        """Update item data and colors from the Node record.

        """
        time_string = "None"
        if self.node.pulse:
            total_seconds = (datetime.datetime.now().replace(microsecond=0) - self.node.pulse).total_seconds()
            days = int(total_seconds / 60 / 60 / 24)
            hours = int(total_seconds / 60 / 60 % 24)
            minutes = int(total_seconds / 60 % 60)
            time_string = "{0} Days, {1} Hours, {2} Mins ago".format(days, hours, minutes)

        node_data = (self.node.host, self.node.status_enum.nice_name, self.node.task_id,
                     self.node.software_version, self.node.ip_addr, time_string, self.node.capabilities)
        
        for i, data in enumerate(node_data):
            self.setData(i, 0, str(data))

        self.setBackground(1, enums.Color[self.node.status].q_color)
        if self.node.host == THIS_HOST:
            font = QtGui.QFont()
            font.setBold(True)
            self.setFont(0, font)
