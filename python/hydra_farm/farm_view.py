"""View and Control The Farm"""
import os
import sys
import fnmatch
import datetime
import webbrowser
from typing import List, Union, Collection
from operator import attrgetter
from collections import defaultdict

from PyQt5 import QtGui, QtCore, QtWidgets, uic

from hydra_farm.qt_dialogs import message_boxes
from hydra_farm.qt_dialogs.node_editor_dialog import NodeEditorDialog
from hydra_farm.qt_dialogs.record_view_dialog import RecordViewDialog
from hydra_farm.qt_widgets.farm_view_widgets import *

from hydra_farm.utils import yaml_cache
from hydra_farm.utils import resource_resolver
from hydra_farm.database import enums
from hydra_farm.database import hydra_db as sql
import hydra_farm.utils.long_strings as longstr
from hydra_farm.utils.logging_setup import logger
import hydra_farm.utils.hydra_utils as hydra_utils

config = yaml_cache.get_hydra_cfg()
UPDATE_TIMER_INTERVAL = 5000  # TODO: Move to cfg


class FarmView(QtWidgets.QMainWindow):
    """FarmView is the queue manager. Used for managing jobs, tasks, and nodes.

    """
    # Type hinting
    # Job Tab
    job_tree: QtWidgets.QTreeWidget
    task_tree: QtWidgets.QTreeWidget
    node_tree: QtWidgets.QTreeWidget
    tab_widget: QtWidgets.QTabWidget
    job_filter_input: QtWidgets.QLineEdit
    archived_cbx: QtWidgets.QCheckBox
    user_filter_cbx: QtWidgets.QCheckBox
    task_tree_job_label: QtWidgets.QLabel
    node_filter_input: QtWidgets.QLineEdit
    refresh_button: QtWidgets.QPushButton
    auto_update_cbx: QtWidgets.QCheckBox
    online_this_node_button: QtWidgets.QPushButton
    offline_this_node_button: QtWidgets.QPushButton
    get_off_this_node_button: QtWidgets.QPushButton

    # This Node Tab
    node_name_label: QtWidgets.QLabel
    node_status_label: QtWidgets.QLabel
    task_id_label: QtWidgets.QLabel
    node_version_label: QtWidgets.QLabel
    min_priority_label: QtWidgets.QLabel
    capabilities_label: QtWidgets.QLabel
    pulse_label: QtWidgets.QLabel
    edit_this_node_button: QtWidgets.QPushButton

    def __init__(self):
        """Load up some basic data, setup the UI, etc.

        """
        super(FarmView, self).__init__()
        uic.loadUi(resource_resolver.get_resource('resources', 'ui', 'farm_view.ui'), self)

        # Variables
        self.this_node_name = hydra_utils.my_host_name()
        self.username = config['database']['username']
        self.user_filter = False
        self.show_archived_filter = False
        self.status_msg = "None"
        self.current_selected_job = None
        logger.debug("User is %s", self.username)
        logger.debug("This host is %s", self.this_node_name)

        # Hide broken elements
        self.job_filter_input.setHidden(True)
        self.node_filter_input.setHidden(True)

        # Load CSS
        css = resource_resolver.get_resource('resources', 'css', 'hydra_styles.css')
        with open(str(css), "r") as myStyles:
            self.setStyleSheet(myStyles.read())

        # Setup UI
        self._setup_tree_widgets()
        self._setup_signals()
        self._setup_hotkeys()
        ico = resource_resolver.get_resource('resources', 'icons', 'FarmView.png')
        self.setWindowIcon(QtGui.QIcon(str(ico)))

        # Check for This Node
        self.this_node = self.find_this_node()
        self.this_node_exists = bool(self.this_node)
        self.set_this_node_buttons_enabled(self.this_node_exists)

        # Fetch initial data from the DB
        self.update_timer = QtCore.QTimer(self)
        self.update_timer.timeout.connect(self.do_refresh)
        self.update_timer.start(UPDATE_TIMER_INTERVAL)
        self.do_refresh()

    def show_data_list_dialog(self, records: List[sql.AbstractHydraTable]):
        """Create and show a dialog with all columns for the given list of records.

        Args:
            records (Collection[sql.AbstractHydraTable]): Collection of HydraRender* instances.

        """
        RecordViewDialog(self, records)

    # --------------------------------------------------------------------------#
    # ---------------------------UI SETUP METHODS-------------------------------#
    # --------------------------------------------------------------------------#

    def _setup_tree_widgets(self):
        """Setup the job_tree, task_tree, and node_tree as well as their splitters.

        """
        # job_tree header and column widths
        h_items = ["ID", "Name", "Status", "Progress", "Owner", "Priority", "MPF", "Errors"]
        self.job_tree.setHeaderItem(QtWidgets.QTreeWidgetItem(h_items))
        # Must set widths AFTER setting header, same order as header
        for i, width in enumerate([50, 300, 60, 80, 100, 50, 100]):
            self.job_tree.setColumnWidth(i, width)

        # task_tree header and column widths
        h_items = ["ID", "Status", "Host", "Start", "End", "start_time", "end_time", "Duration", "exit_code"]
        self.task_tree.setHeaderItem(QtWidgets.QTreeWidgetItem(h_items))
        for i, width in enumerate([50, 60, 125, 50, 50, 50, 110, 120, 75]):
            self.task_tree.setColumnWidth(i, width)

        # node_tree column widths
        h_items = ["Host", "Status", "TaskID", "Version", "IP Address", "Pulse", "Capabilities"]
        self.node_tree.setHeaderItem(QtWidgets.QTreeWidgetItem(h_items))
        for i, width in enumerate([200, 70, 70, 85, 100, 175, 110]):
            self.node_tree.setColumnWidth(i, width)

        # Job List splitter size
        self.splitter_job_list.setSizes([10500, 10000])

    def _setup_signals(self):
        """Setup signals for user interaction.

        """
        # Connect tab switch data update
        self.tab_widget.currentChanged.connect(self.do_refresh)

        # Connect buttons in This Node tab
        self.refresh_button.clicked.connect(self.do_refresh)
        self.auto_update_cbx.stateChanged.connect(self.auto_update_cbx_callback)
        self.online_this_node_button.clicked.connect(self.online_this_node_callback)
        self.offline_this_node_button.clicked.connect(self.offline_this_node_callback)
        self.get_off_this_node_button.clicked.connect(self.get_off_this_node_callback)
        self.edit_this_node_button.clicked.connect(self.node_editor_callback)

        # job_tree itemClicked
        self.job_tree.itemClicked.connect(self.job_tree_clicked_callback)

        # Connect basic filter checkboxKeys
        self.archived_cbx.stateChanged.connect(self.archived_filter_callback)
        self.user_filter_cbx.stateChanged.connect(self.user_filter_callback)

        # Connect Context Menus
        self.central_widget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.central_widget.customContextMenuRequested.connect(self.central_context_menu_callback)

        self.job_tree.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.job_tree.customContextMenuRequested.connect(self.job_context_menu_callback)

        self.task_tree.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.task_tree.customContextMenuRequested.connect(self.task_context_menu_callback)

        self.node_tree.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.node_tree.customContextMenuRequested.connect(self.node_context_menu_callback)

    def _setup_hotkeys(self):
        """Setup Hotkeys for most common user interactions as QKeySequences.

        """
        #                   # This node hotkeys
        self.all_hotkeys = {self.online_this_node_callback: "Ctrl+O",
                            self.offline_this_node_callback: "Ctrl+Shift+O",
                            self.get_off_this_node_callback: "Ctrl+G",
                            self.do_refresh: "Ctrl+U",
                            # Node Table hotkeys
                            self.online_render_nodes_callback: "Ctrl+Alt+O",
                            self.offline_render_nodes_callback: "Ctrl+Alt+Shift+O",
                            self.get_off_render_nodes_callback: "Ctrl+Alt+G",
                            self.node_detailed_data_callback: "Ctrl+Alt+D",
                            self.node_editor_table_callback: "Ctrl+Alt+E",
                            # Job Tree hotkeys
                            self.start_job_callback: "Ctrl+S",
                            self.start_test_tasks_callback: "Ctrl+T",
                            self.pause_job_callback: "Ctrl+P",
                            self.kill_job_callback: "Ctrl+K",
                            self.reset_nodes_job_callback: "Ctrl+N",
                            self.reset_job_callback: "Ctrl+R",
                            self.archive_job_callback: "Del",
                            self.unarchive_job_callback: "Shift+Del",
                            self.job_detailed_data_callback: "Ctrl+D",
                            self.prioritize_job_callback: "Ctrl+Q",
                            # Task Tree hotkeys
                            self.start_task_callback: "Ctrl+Shift+S",
                            self.pause_task_callback: "Ctrl+Shift+P",
                            self.kill_task_callback: "Ctrl+Shift+K",
                            self.reset_task_callback: "Ctrl+Shift+R",
                            self.task_detailed_data_callback: "Ctrl+Shift+D",
                            self.open_task_log_callback: "Ctrl+Shift+L",
                            self.tail_task_log_callback: "Ctrl+Shift+T"}

        for callback, hotkey in self.all_hotkeys.items():
            QtWidgets.QShortcut(QtGui.QKeySequence(hotkey), self, callback)

    # --------------------------------------------------------------------------#
    # ----------------------------CONTEXT MENUS---------------------------------#
    # --------------------------------------------------------------------------#

    def central_context_menu_callback(self):
        """Creates and shows the QMenu for the main window.

        """
        central_menu = FarmViewMenu(self)
        central_menu.add_action("Update", self.do_refresh, "Update with the latest information from the Database")
        if self.this_node_exists:
            central_menu.addSection("This Node")
            central_menu.add_action("Online This Node", self.online_this_node_callback, "Online This Node")
            central_menu.add_action("Offline This Node", self.offline_this_node_callback,
                                    "Wait for the current job to finish then offline this node")
            central_menu.add_action("Get Off This Node!", self.get_off_this_node_callback,
                                    "Kill the current task and offline this node immediately")

        central_menu.popup(QtGui.QCursor.pos())

    def job_context_menu_callback(self):
        """Creates and shows the job_tree QMenu context menu.

        """
        job_menu = FarmViewMenu(self)
        job_menu.add_action("Start Jobs", self.start_job_callback,
                            "Mark job(s) as Ready so new subtasks can be created")
        job_menu.add_action("Pause Jobs", self.pause_job_callback,
                            "Don't make any new subtasks but don't kill existing ones")
        job_menu.add_action("Kill Jobs", self.kill_job_callback,
                            "Kill all subtasks and don't create anymore until job is Started again")
        job_menu.add_action('Reset Failed Nodes', self.reset_nodes_job_callback,
                            'Reset failed nodes on the selected jobs')
        job_menu.add_action("Reset Jobs", self.reset_job_callback,
                            "Kill all subtasks and reset each Render Layer to be rendered again")
        # -----------------
        job_menu.addSeparator()
        job_menu.add_action("Start Test Tasks", self.start_test_tasks_callback,
                            "Mark the first x tasks as Ready and give them a higher priority")
        # ---- Archive ----
        job_menu.addSection("Archive")
        job_menu.add_action("Archive Jobs", self.archive_job_callback,
                            "Archive Job(s) and hide them from the job_tree")
        job_menu.add_action("Unarchive Jobs", self.unarchive_job_callback,
                            "Unarchive Job(s) and show them from the job_tree")
        # ---- Advanced ----
        job_menu.addSection("Advanced")
        job_menu.add_action("Set Job Priority...", self.prioritize_job_callback,
                            "Set priority on each job selected in the Job List")
        job_menu.add_action("Show Detailed Data...", self.job_detailed_data_callback,
                            "Opens a dialog window the detailed data for the selected job(s)")
        job_menu.popup(QtGui.QCursor.pos())

    def task_context_menu_callback(self):
        """Creates and shows the job_tree QMenu context menu.

        """
        task_menu = FarmViewMenu(self)
        task_menu.add_action("Start Tasks", self.start_task_callback, "Start all tasks selected in the Task Table")
        task_menu.add_action("Pause Tasks", self.pause_task_callback, "Pause all tasks selected in the Task Table")
        task_menu.add_action("Kill Tasks", self.kill_task_callback, "Kill all tasks selected in the Task Table")
        task_menu.add_action("Reset Tasks", self.reset_task_callback, "Reset all tasks selected in the Task Table")
        # ---- Advanced ----
        task_menu.addSection("Advanced")
        task_menu.add_action("Show Detailed Data", self.task_detailed_data_callback,
                             "Opens a dialog window the detailed data for the selected tasks.")
        task_menu.add_action("Tail Log File...", self.tail_task_log_callback,
                             "Tail the log file for the first task selected in the Task Tree")
        task_menu.add_action("Open Log File...", self.open_task_log_callback,
                             "Open the log file for all tasks selected in the Task Tree")
        task_menu.popup(QtGui.QCursor.pos())

    def node_context_menu_callback(self):
        """Creates and shows the node_tree QMenu context menu.

        """
        node_menu = FarmViewMenu(self)
        node_menu.add_action("Online Nodes", self.online_render_nodes_callback, "Online all selected nodes", )
        node_menu.add_action("Offline Nodes", self.offline_render_nodes_callback,
                             "Offline all selected nodes without killing their current task")
        node_menu.add_action("Get Off Nodes", self.get_off_render_nodes_callback,
                             "Kill task then offline all selected nodes")
        # ---- Advanced ----
        node_menu.addSection("Advanced")
        node_menu.add_action("Select by Host Name...", self.select_by_host_callback,
                             "Open a dialog to check nodes based on their host name")
        node_menu.add_action("Show Detailed Data...", self.node_detailed_data_callback,
                             "Opens a dialog window the detailed data for the selected nodes.")
        node_menu.add_action("Edit Node...", self.node_editor_table_callback,
                             "Open a dialog to edit selected node's attributes.")
        node_menu.popup(QtGui.QCursor.pos())

    # --------------------------------------------------------------------------#
    # ----------------------------UPDATE METHODS--------------------------------#
    # --------------------------------------------------------------------------#

    def find_this_node(self) -> Union[sql.HydraRenderNode, None]:
        """Return this node as a HydraRenderNode object if it exists, None if not.

        Returns:
            sql.HydraRenderNode: HydraRenderNode object for this node if it exists, None if not.

        """
        this_node = sql.HydraRenderNode.get_this_node()
        if this_node:
            return this_node

        message_boxes.warning_box(self, title="Notice", msg=longstr.does_not_exist_str)
        return None

    def get_this_node(self) -> Union[sql.HydraRenderNode, None]:
        """Refresh and return this node if it exists, None if not.

        Returns:
            sql.HydraRenderNode: HydraRenderNode object for this node if it exists, None if not.

        """
        if isinstance(self.this_node, sql.HydraRenderNode):
            self.this_node.refresh()
        return self.this_node

    def fetch_jobs(self) -> List[sql.HydraRenderJob]:
        """Return all jobs given the current filter checkboxes enabled.

        Returns:
            list[sql.HydraRenderJob]: List of HydraRenderJob records.

        """
        # Build query
        args = tuple()
        query = "WHERE"
        query += " owner = %s" if self.user_filter else ""
        query += " AND" if query != "WHERE" and not self.show_archived_filter else ""
        query += " archived = 0" if not self.show_archived_filter else ""
        if query == "WHERE":
            query = ""
        else:
            if self.user_filter:
                args = (self.username,)

        # Fetch the Jobs
        return sql.HydraRenderJob.fetch(query, args)

    def do_refresh(self):
        """Fetch the latest data and update widgets for the current view and current selections.

        """
        cur_tab = self.tab_widget.currentIndex()
        t = hydra_utils.Timer(f'do_refresh tab {cur_tab}', logger)

        # Update status bar on every view
        this_node = self.get_this_node()
        self.update_status_bar(this_node)

        # Main View:
        if cur_tab == 0:
            self.populate_job_tree()
            if self.current_selected_job:
                self.load_task_tree(self.current_selected_job)
            self.populate_node_tree()
        # This Node
        elif cur_tab == 1:
            if self.this_node:
                self.update_this_node_info(this_node)
        t.log()

    def auto_update_cbx_callback(self):
        """Start and stop the Auto Update Timer depending on the auto update checkbox state.

        """
        if self.auto_update_cbx.isChecked():
            self.update_timer.start(UPDATE_TIMER_INTERVAL)
        else:
            self.update_timer.stop()

    def update_this_node_info(self, this_node: sql.HydraRenderNode):
        """Updates widgets on the "This Node" tab with the most recent information available.

        Args:
            this_node (sql.HydraRenderNode): This node as a Hydra Render Node object.

        """
        self.node_name_label.setText(str(this_node.host))
        self.node_status_label.setText(str(this_node.status_enum.nice_name))
        self.task_id_label.setText(str(this_node.task_id))
        self.node_version_label.setText(str(this_node.software_version))
        self.min_priority_label.setText(str(this_node.min_priority))
        self.capabilities_label.setText(str(this_node.capabilities))
        self.pulse_label.setText(str(this_node.pulse))

    def update_status_bar(self, this_node: sql.HydraRenderNode = None):
        """Fetches the latest status data and updates the status bar.

        Args:
            this_node (sql.HydraRenderNode): This node record.

        """
        counts = sql.HydraRenderNode.get_node_status_count(nice_name=True)
        cs = ', '.join([f'{c[0]} {c[1]}' for c in counts])
        if this_node:
            cs += f', {this_node.host} {this_node.status_enum.nice_name}'
        now_time = datetime.datetime.now().strftime("%H:%M:%S")
        self.status_msg = f"{cs} as of {now_time}"
        self.statusbar.showMessage(self.status_msg)

    def reset_status_bar(self):
        """Resets the status to the last set status. Used to reset after a tooltip is displayed.

        """
        self.statusbar.showMessage(self.status_msg)

    def set_this_node_buttons_enabled(self, choice):
        """Enables or disables buttons on This Node tab. These buttons should be disabled if this node does not exist.

        """
        self.online_this_node_button.setEnabled(choice)
        self.offline_this_node_button.setEnabled(choice)
        self.get_off_this_node_button.setEnabled(choice)
        self.this_node_exists = choice

    # --------------------------------------------------------------------------#
    # -----------------------------JOB METHODS----------------------------------#
    # --------------------------------------------------------------------------#

    def user_filter_callback(self):
        """Toggle user filter and repopulate tree.

        """
        self.user_filter = not self.user_filter
        self.populate_job_tree(clear=True)

    def archived_filter_callback(self):
        """Toggle archive filter and repopulate tree.

        """
        self.show_archived_filter = not self.show_archived_filter
        self.populate_job_tree(clear=True)

    def add_job_to_tree(self, job: sql.HydraRenderJob):
        """Add or update a job on the job_tree.

        Args:
            job (sql.HydraRenderJob): HydraRenderJob record to add or update on the tree.

        """
        # noinspection PyTypeChecker
        job_search: List[JobTreeItem] = self.job_tree.findItems(str(job.id), QtCore.Qt.MatchExactly, 0)
        if job_search:
            job_item = job_search[0]
            job_item.job = job
            job_item.update()
        else:
            JobTreeItem(self.job_tree, job)

    def populate_job_tree(self, clear: bool = False):
        """Fetch jobs and populate the job_tree.

        Args:
            clear (bool): If True will clear the tree rather than updating it. Default False.

        """
        jobs = self.fetch_jobs()
        if not jobs:
            if clear:
                self.job_tree.clear()
            return

        top_level_open_list = []
        for i in range(0, self.job_tree.topLevelItemCount()):
            if self.job_tree.topLevelItem(i).isExpanded():
                top_level_open_list.append(str(self.job_tree.topLevelItem(i).text(0)))

        if clear:
            self.job_tree.clear()

        for job in jobs:
            self.add_job_to_tree(job)

        for i in range(0, self.job_tree.topLevelItemCount()):
            if str(self.job_tree.topLevelItem(i).text(0)) in top_level_open_list:
                self.job_tree.topLevelItem(i).setExpanded(True)

    def get_job_tree_sel(self) -> List[sql.HydraRenderJob]:
        """Returns current job tree selection

        Returns:
            List[sql.HydraRenderJob]: List of HydraRenderJob records.

        """
        self.reset_status_bar()
        # noinspection PyTypeChecker
        my_sel: List[JobTreeItem] = self.job_tree.selectedItems()
        if not my_sel:
            message_boxes.warning_box(self, "Selection Error",
                                      "Please select something from the Job Tree and try again.")

        return [item.job for item in my_sel]  # TODO: Do we need to update these?

    def _set_archive(self, selected_jobs: List[sql.HydraRenderJob], arch_mode: bool):
        """Set a job to be archived/unarchived.

        Args:
            selected_jobs List[sql.HydraRenderJob]: List of jobs
            arch_mode (bool): 1 or 0 where 1 is Archive and 0 is Unarchive.

        """
        arch_mode = 1 if arch_mode else 0
        mode_str = 'archive' if arch_mode else 'unarchive'
        choice = message_boxes.yes_no_box(self, "Confirm", f"Really {mode_str} the selected jobs?")
        if choice == QtWidgets.QMessageBox.No:
            return None

        responses = [job.archive(arch_mode) for job in selected_jobs]

        if not all(responses):
            failure_idxs = [i for i, x in enumerate(responses) if not x]
            failure_ids = [selected_jobs[i].id for i in failure_idxs]
            logger.error("Job Archiver failed on %s", failure_ids)

        self.populate_job_tree(clear=True)

    def start_job_callback(self):
        """Start the selected jobs.

        """
        selected_jobs = self.get_job_tree_sel()
        if selected_jobs:
            _ = [job.start() for job in selected_jobs]
            self.do_refresh()

    def start_test_tasks_callback(self):
        """Start X number of test tasks for the selected jobs.
        """
        selected_jobs = self.get_job_tree_sel()
        if not selected_jobs:
            return

        for job in selected_jobs:
            s = f'How many test tasks to start for "{job.name}"?'
            reply = message_boxes.int_box(self, "Start Test Tasks", s, 10)
            if all(reply):
                num_to_start = int(reply[0])
                tasks = job.get_tasks()
                start_tasks = tasks[:num_to_start]
                task_check = any([ta.status in [sql.HydraStatus.FINISHED, sql.HydraStatus.STARTED] for ta in tasks])
                if task_check:
                    s = f"Skipping {job.name} because one or more of the tasks is already started or done."
                    message_boxes.warning_box(self, "Error!", s)
                else:
                    with sql.Transaction() as t:
                        job.status = sql.HydraStatus.READY
                        job.update(t)
                        for task in start_tasks:
                            task.priority = int(job.priority * 1.25)
                            task.status = sql.HydraStatus.READY
                            task.update(t)

        self.do_refresh()

    def pause_job_callback(self):
        """Pause the selcted jobs.

        """
        selected_jobs = self.get_job_tree_sel()
        if selected_jobs:
            _ = [job.pause() for job in selected_jobs]
            self.do_refresh()

    def job_detailed_data_callback(self):
        """Open a Detailed Data dialog for the selected job(s).

        """
        selected_jobs = self.get_job_tree_sel()
        if selected_jobs:
            self.show_data_list_dialog(selected_jobs)

    def kill_job_callback(self):
        """Kill the selected jobs, after confirming with the user.

        """
        selected_jobs = self.get_job_tree_sel()
        if not selected_jobs:
            return

        choice = message_boxes.yes_no_box(self, "Confirm", "Really kill the selected jobs?")
        if choice == QtWidgets.QMessageBox.No:
            return None

        raw_responses = [job.kill() for job in selected_jobs]
        responses = [all(r) for r in raw_responses]

        if not all(responses):
            resp_string = "Job Kill returned the following errors:\n"
            failure_idxs = [i for i, x in enumerate(responses) if not x]
            for idx in failure_idxs:
                task_string = "\t"
                task_failures = [i for i, x in enumerate(raw_responses[idx]) if not x]
                status_success = task_failures[-1]
                task_success = task_failures[:-1]
                task_string += f"Jobs '{[j.id for j in selected_jobs]}' had "
                if not status_success:
                    task_string += "an error changing its status and "
                task_string += f"{len(task_success)} errors killing subtasks.\n"
                resp_string += task_string

            logger.error(resp_string)
            message_boxes.warning_box(self, "Job Kill Errors!", resp_string)

        self.do_refresh()

    def reset_nodes_job_callback(self):
        """Reset the failed nodes list for the selected jobs.

        """
        selected_jobs = self.get_job_tree_sel()
        if not selected_jobs:
            return

        job_names = '\n'.join([j.name for j in selected_jobs])
        s = f"Really reset failed nodes on the following jobs?\n{job_names}"
        choice = message_boxes.yes_no_box(self, "Confirm", s)
        if choice == QtWidgets.QMessageBox.No:
            return
        else:
            _ = [job.reset_failed_nodes() for job in selected_jobs]

        self.do_refresh()

    def reset_job_callback(self):
        """Reset all statuses for the selected jobs.

        """
        selected_jobs = self.get_job_tree_sel()
        if not selected_jobs:
            return

        job_names = '\n'.join([j.name for j in selected_jobs])
        s = f"Really reset the following jobs?\n{job_names}"
        choice = message_boxes.yes_no_box(self, "Confirm", s)
        if choice == QtWidgets.QMessageBox.No:
            return
        else:
            _ = [job.reset() for job in selected_jobs]

        self.do_refresh()

    def archive_job_callback(self):
        """Archive the selected jobs.

        """
        selected_jobs = self.get_job_tree_sel()
        if not selected_jobs:
            return
        self._set_archive(selected_jobs, True)

    def unarchive_job_callback(self):
        """Unarchive the selected jobs.

        """
        selected_jobs = self.get_job_tree_sel()
        if not selected_jobs:
            return
        self._set_archive(selected_jobs, False)

    def prioritize_job_callback(self):
        """Update the priority of the selected jobs.

        """
        selected_jobs = self.get_job_tree_sel()
        if not selected_jobs:
            return

        for job in selected_jobs:
            msg_string = f"Priority for job {job.name}:"
            reply = message_boxes.int_box(self, "Set Job Priority", msg_string, job.priority)
            if reply[1]:
                job.prioritize(reply[0])
                self.populate_job_tree()
            else:
                logger.debug("PrioritizeJob skipped on %s", job.name)
        self.do_refresh()

    # --------------------------------------------------------------------------#
    # -----------------------------TASK METHODS---------------------------------#
    # --------------------------------------------------------------------------#

    def job_tree_clicked_callback(self, item: JobTreeItem):
        """Handles clicks on the job tree triggering updates on the task tree.

        """
        # noinspection PyTypeChecker
        self.load_task_tree(item.job, clear=True)
        self.current_selected_job = item.job
        self.task_tree_job_label.setText(f"Job ID: [{item.job.id}]")

    def load_task_tree(self, job: sql.HydraRenderJob, clear: bool = False):
        """Load the tasks into the task tree for the selected job.

        """
        if clear:
            self.task_tree.clear()

        task_list = job.get_tasks()

        for task in task_list:
            # noinspection PyTypeChecker
            task_search: List[TaskTreeItem] = self.task_tree.findItems(str(task.id), QtCore.Qt.MatchExactly, 0)
            if task_search:
                task_item = task_search[0]
                task_item.task = task
                task_item.update()
            else:
                TaskTreeItem(self.task_tree, task)

        # Set node colors
        # Reset colors
        color = enums.Color["R"].q_color
        for i in range(self.node_tree.topLevelItemCount()):
            self.node_tree.topLevelItem(i).setBackground(0, color)

        # Set Job Colors
        failed_nodes = [x.strip() for x in job.failed_nodes.split(",")]
        for node in failed_nodes:
            node_search = self.node_tree.findItems(node, QtCore.Qt.MatchExactly, 0)
            if node_search:
                node_item = node_search[0]
                node_item.setBackground(0, enums.Color["E"].q_color)

        # Set Task Colors
        if not task_list:
            return
        task_groups = defaultdict(list)
        for t in task_list:
            task_groups[str(t.host)].append(t)
        task_groups = {k: sorted(v, key=attrgetter("id"), reverse=True)[0].status for k, v in task_groups.items()}
        for node, status in task_groups.items():
            if node not in failed_nodes:
                node_search = self.node_tree.findItems(str(node), QtCore.Qt.MatchExactly, 0)
                if node_search:
                    node_item = node_search[0]
                    node_item.setBackground(0, enums.Color[status].q_color)

    def get_task_tree_sel(self) -> List[sql.HydraRenderTask]:
        """Returns list of tasks selected in the task tree.

        Returns:
            List[sql.HydraRenderTask]: List of selected tasks.

        """
        self.reset_status_bar()
        # noinspection PyTypeChecker
        my_sel: List[TaskTreeItem] = self.task_tree.selectedItems()
        if not my_sel:
            message_boxes.warning_box(self, "Selection Error",
                                      "Please select something from the Task Tree and try again.")
            return []

        return [item.task for item in my_sel]

    def start_task_callback(self):
        """Start all selected tasks.

        """
        tasks = self.get_task_tree_sel()
        if tasks:
            _ = [task.start() for task in tasks]
            self.do_refresh()

    def pause_task_callback(self):
        """Pause all selected tasks.

        """
        tasks = self.get_task_tree_sel()
        if tasks:
            _ = [task.pause() for task in tasks]
            self.do_refresh()

    def reset_task_callback(self):
        """Reset all selected tasks.

        """
        tasks = self.get_task_tree_sel()
        if not tasks:
            return

        s = "Are you sure you want to reset the following tasks?\n{}"
        response = message_boxes.yes_no_box(self, "Confirm", s.format([t.id for t in tasks]))
        if response == QtWidgets.QMessageBox.No:
            return
        _ = [task.reset() for task in tasks]
        self.do_refresh()

    def kill_task_callback(self):
        """Kill all selected tasks.

        """
        tasks = self.get_task_tree_sel()
        if not tasks:
            return

        s = "Are you sure you want to kill these tasks?\n{}"
        response = message_boxes.yes_no_box(self, "Confirm", s.format(str([t.id for t in tasks])))
        if response == QtWidgets.QMessageBox.No:
            return None

        responses = [task.kill() for task in tasks]
        if not all(responses):
            failure_idxs = [i for i, x in enumerate(responses) if not x]
            failure_ids = [tasks[i].id for i in failure_idxs]
            err = f"Task Kill failed on task(s) with IDs {failure_ids}"
            logger.error(err)
            message_boxes.warning_box(self, "Task Kill Error!", err)

        self.do_refresh()

    def tail_task_log_callback(self):
        """Tail logs for the first selected task.

        """
        tasks = self.get_task_tree_sel()
        if not tasks:
            return

        try:
            task = [t for t in tasks if t.get_log_path()][0]
        except IndexError:
            message_boxes.warning_box(self, msg='No tasks with logs selected')
            return

        self._tail_log(task)

    def open_task_log_callback(self):
        """Open logs for all selected tasks.

        """
        tasks = self.get_task_tree_sel()
        if not tasks:
            return

        if len(tasks) > 1:
            s = "You have {0} tasks selected. Are you sure you want to open {0} logs?"
            choice = message_boxes.yes_no_box(self, "Confirm", s.format(len(tasks)))
            if choice == QtWidgets.QMessageBox.No:
                return
        _ = [self._open_log(task) for task in tasks]

    def task_detailed_data_callback(self):
        """Opens a Detailed Data dialog for all selected tasks.

        """
        tasks = self.get_task_tree_sel()
        if tasks:
            self.show_data_list_dialog(tasks)

    def _open_log(self, task: sql.HydraRenderTask):
        """Opens the default text editor with the log for the given task object.

        Args:
            task (sql.HydraRenderTask): Task object to open the log from.

        """
        log_path = task.get_log_path()
        if log_path and log_path.is_file():
            webbrowser.open(str(log_path.resolve()))
        else:
            err = f"Log could not be found for Task {int(task.id)}"
            logger.warning(err)
            message_boxes.warning_box(self, "Log Not Found", err)

    def _tail_log(self, task: sql.HydraRenderTask):
        """Tails the log for the given task object.

        Args:
            task (sql.HydraRenderTask): Task object to tail the log from.

        """
        _ = self.width()  # Get rid of static method inspection
        log_path = task.get_log_path()
        if log_path and log_path.is_file():
            path = str(log_path.resolve())
            if sys.platform.startswith('win'):
                os.system(f'start powershell Get-Content {path} -Wait')
            else:
                os.system(f'start bash tail -f {path}')

    # --------------------------------------------------------------------------#
    # -----------------------------NODE METHODS---------------------------------#
    # --------------------------------------------------------------------------#
    def populate_node_tree(self, clear: bool = False):
        """Populate the node tree with the latest data from the database.

        Args:
            clear (bool): If True will clear the view, False will update items in place.

        """
        if clear:
            self.node_tree.clear()

        render_nodes = sql.HydraRenderNode.fetch("ORDER BY host ASC")

        for node in render_nodes:
            self.add_node_to_tree(node)

    def add_node_to_tree(self, node: sql.HydraRenderNode):
        """Add a single node to the node tree.

        Args:
            node (sql.HydraRenderNode): Node to add to the tree.

        """
        # noinspection PyTypeChecker
        node_search: List[NodeTreeItem] = self.node_tree.findItems(str(node.host), QtCore.Qt.MatchExactly, 0)
        if node_search:
            # If the node was found, update it's information
            node_item = node_search[0]
            node_item.node = node
            node_item.update()
        else:
            # If not add it as a new item
            NodeTreeItem(self.node_tree, node)

    def get_node_tree_sel(self) -> List[sql.HydraRenderNode]:
        """Returns the selected nodes from the node tree.

        Returns:
            List[sql.HydraRenderNode]: List of nodes selected in the node tree.

        """
        self.reset_status_bar()
        # noinspection PyTypeChecker
        my_sel: List[NodeTreeItem] = self.node_tree.selectedItems()

        if not my_sel:
            message_boxes.warning_box(self, "Selection Error",
                                      "Please select something from the Render Node Table and try again.")
            return []

        return [item.node for item in my_sel]

    def online_render_nodes_callback(self):
        """Online the selected nodes.

        """
        nodes = self.get_node_tree_sel()
        if not nodes:
            return

        choice = message_boxes.yes_no_box(self, "Confirm", "Are you sure you want to online"
                                                           " these nodes?\n" + str([n.host for n in nodes]))

        if choice == QtWidgets.QMessageBox.No:
            return

        for node in nodes:
            node.online()
        self.populate_node_tree()

    def offline_render_nodes_callback(self):
        """Offline the selected nodes.

        """
        nodes = self.get_node_tree_sel()
        if not nodes:
            return

        choice = message_boxes.yes_no_box(self, "Confirm", "Are you sure you want to offline"
                                                           " these nodes?\n" + str([n.host for n in nodes]))

        if choice == QtWidgets.QMessageBox.No:
            return

        for node in nodes:
            node.offline()
        self.populate_node_tree()

    def get_off_render_nodes_callback(self):
        """Kill the current task and offline the selected nodes.

        """
        nodes = self.get_node_tree_sel()
        if not nodes:
            return

        choice = message_boxes.yes_no_box(self, "Confirm", longstr.get_off_string + str([n.host for n in nodes]))
        if choice == QtWidgets.QMessageBox.No:
            return

        responses = [node.get_off() for node in nodes]
        if not all(responses):
            failure_idxs = [i for i, x in enumerate(responses) if not x]
            failure_nodes = [nodes[i] for i in failure_idxs]
            logger.error("Could not get off %s", failure_nodes)
            message_boxes.warning_box(self, "GetOff Error!",
                                      f"Could not get off the following nodes: {failure_nodes}")

        self.populate_node_tree()

    def node_editor_table_callback(self):
        """Opens the node editor for the selected nodes.


        """
        nodes = self.get_node_tree_sel()
        if not nodes:
            return None
        elif len(nodes) > 1:
            choice = message_boxes.yes_no_box(self, "Confirm", longstr.multi_node_edit_string)
            if choice == QtWidgets.QMessageBox.Yes:
                for node in nodes:
                    self._open_node_editor(node)
        else:
            self._open_node_editor(nodes[0])

        self.do_refresh()

    def _open_node_editor(self, node: sql.HydraRenderNode):
        """Opens the node editor for a single node.

        Args:
            node (sql.HydraRenderNode): Node to edit.

        """
        comps = node.capabilities.split(" ")
        defaults = {"host": node.host,
                    "priority": node.min_priority,
                    "comps": comps,
                    "is_render_node": bool(node.is_render_node),
                    "ip_addr": node.ip_addr}

        edits: dict = NodeEditorDialog.create(defaults)

        if edits:  # TODO: This should be done with host.update()
            query = "UPDATE hydra.render_nodes SET min_priority = %s"
            query += ", capabilities = %s"
            query += ", is_render_node = %s, ip_addr = %s"
            query += " WHERE id = %s"
            edits_tuple = (edits["priority"], edits["comps"],
                           edits["is_render_node"], edits["ip_addr"], node.id)
            with sql.Transaction() as t:
                t.cur.execute(query, edits_tuple)
            self.populate_node_tree()

    def node_detailed_data_callback(self):
        """Opens Detailed Data Dialogs for the selected nodes.

        """
        node_list = self.get_node_tree_sel()
        if node_list:
            self.show_data_list_dialog(node_list)

    def select_by_host_callback(self):
        """Opens a dialog for the user to select nodes by host name.

        """
        s = "Select nodes via name, case insensitive with * as wildcard:"
        reply = message_boxes.str_box(self, "Select By Host Name", s)
        if reply[1]:
            self.node_tree.clearSelection()
            search_string = str(reply[0]).lower()
            iterator = QtWidgets.QTreeWidgetItemIterator(self.node_tree)
            while iterator.value():
                # noinspection PyTypeChecker
                item: sql.HydraRenderNode = iterator.value()
                if fnmatch.fnmatch(item.node.host.lower(), search_string):
                    item.setSelected(True)
                    logger.debug("Selecting %s matched with %s", item, search_string)
                iterator += 1

    # --------------------------------------------------------------------------#
    # ---------------------------THIS NODE METHODS------------------------------#
    # --------------------------------------------------------------------------#

    def online_this_node_callback(self):
        """Online this node.

        """
        this_node = sql.HydraRenderNode.get_this_node()
        if this_node:
            this_node.online()
            self.update_status_bar(this_node)
            self.populate_node_tree()

    def offline_this_node_callback(self):
        """Offline this node

        """
        # Get the most current info from the database
        this_node = sql.HydraRenderNode.get_this_node()
        if this_node:
            this_node.offline()
            self.update_status_bar(this_node)
            self.populate_node_tree()

    def get_off_this_node_callback(self):
        """Offline this node and kill it's current task.

        """
        this_node = sql.HydraRenderNode.get_this_node()
        if not this_node:
            return

        choice = message_boxes.yes_no_box(self, "Confirm", longstr.get_off_local_string)
        if choice == QtWidgets.QMessageBox.Yes:
            response = this_node.get_off()
            if not response:
                logger.error("Could not GetOff this node!")
                message_boxes.warning_box(self, "GetOff Error", "Could not GetOff this node!")
            self.populate_node_tree()
            self.update_status_bar(this_node)

    def node_editor_callback(self):
        """Opens a dialog to edit this node.

        """
        if self.this_node:
            self._open_node_editor(self.this_node)


def main():
    """Setup QT App and show this window."""
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle('Fusion')
    window = FarmView()
    window.show()
    retcode = app.exec_()
    sys.exit(retcode)


if __name__ == '__main__':
    main()
