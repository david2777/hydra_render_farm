"""Submitter GUI"""
import os
import sys

from PyQt5 import QtGui, QtCore, QtWidgets, uic

from hydra_farm.utils import resource_resolver

from hydra_farm.database import hydra_db as sql
from hydra_farm.utils.logging_setup import logger
from hydra_farm.qt_dialogs.message_boxes import about_box

MAYA_FILES = 'Maya Files (*.ma *.mb)'
BATCH_FILES = 'Batch Files (*.bat)'
START_DIR = r'Z:/maya/master_proj'
WORKSPACE = "workspace.mel;;All Files(*)"


class SubmitterMain(QtWidgets.QMainWindow):
    """Main submitter window. Used to submit jobs/tasks to the database.

    """
    # Class
    req_checks: list[QtWidgets.QCheckBox] = []

    # Submit
    submit_btn: QtWidgets.QPushButton

    # Basic
    job_name_line: QtWidgets.QLineEdit
    job_type_combo: QtWidgets.QComboBox
    reqs_grid: QtWidgets.QGridLayout

    # Advanced
    args_line: QtWidgets.QLineEdit
    status_paused_button: QtWidgets.QRadioButton
    status_ready_button: QtWidgets.QRadioButton
    max_nodes_spinbox: QtWidgets.QSpinBox
    priority_spinbox: QtWidgets.QSpinBox
    max_failures_spinbox: QtWidgets.QSpinBox
    timeout_spinbox: QtWidgets.QSpinBox

    # Command
    command_grp: QtWidgets.QGroupBox
    command_line: QtWidgets.QLineEdit

    # Maya Render
    maya_render_grp: QtWidgets.QGroupBox
    maya_render_project_line: QtWidgets.QLineEdit
    maya_render_project_btn: QtWidgets.QPushButton
    maya_render_output_line: QtWidgets.QLineEdit
    maya_render_output_btn: QtWidgets.QPushButton
    maya_render_scene_line: QtWidgets.QLineEdit
    maya_render_scene_btn: QtWidgets.QPushButton
    maya_render_start_frame_spin: QtWidgets.QSpinBox
    maya_render_end_frame_spin: QtWidgets.QSpinBox
    maya_render_by_frame_spin: QtWidgets.QSpinBox
    maya_render_batch_info_label: QtWidgets.QLabel
    maya_render_rl_tree: QtWidgets.QTreeWidget
    add_rl_btn = QtWidgets.QPushButton
    remove_rl_btn = QtWidgets.QPushButton

    # MayaPy
    mayapy_grp: QtWidgets.QGroupBox
    mayapy_script_text: QtWidgets.QTextEdit

    def __init__(self):
        """Setup and show the main window. 

        """
        super(SubmitterMain, self).__init__()
        uic.loadUi(resource_resolver.get_resource('resources', 'ui', 'submitter.ui'), self)
        ico = resource_resolver.get_resource('resources', 'icons', 'SubmitterMain.png')
        self.setWindowIcon(QtGui.QIcon(str(ico)))

        self._group_layouts = {'Maya Render': self.maya_render_grp, 'MayaPy': self.mayapy_grp,
                               'Command': self.command_grp}

        self._setup_widgets()
        self._populate_reqs()
        self._signals()
        self.update_layout()
        self.show()

    def _add_rl_handler(self, name: str = None):
        """Add a new render layer to the render layer Tree. Immediately edit the item if no name is given. 
        
        Args:
            name (str): Optional render layer Name, default "New Layer"

        """
        logger.debug('Adding new render layer item')
        item = QtWidgets.QTreeWidgetItem()
        # noinspection PyTypeChecker
        item.setFlags(item.flags() | QtCore.Qt.ItemIsEditable)
        item.setText(0, name if name else 'New Layer')
        item.setCheckState(0, QtCore.Qt.Checked)
        self.maya_render_rl_tree.addTopLevelItem(item)
        if not name:
            self.maya_render_rl_tree.editItem(item, 0)

    def _remove_rl_handler(self):
        """Remove the selected Render Layers from the render layer Tree.

        """
        sel = self.maya_render_rl_tree.selectedItems()
        root = self.maya_render_rl_tree.invisibleRootItem()
        for item in sel:
            root.removeChild(item)

    def _browse_maya_render_scene(self):
        """Browse for a Maya scene to fill into the Maya Render Scene line edit.

        """
        logger.debug('entering _browse_maya_render_scene')
        result = QtWidgets.QFileDialog.getOpenFileName(self, 'Select Maya Scene', START_DIR, MAYA_FILES)
        if result and result[0]:
            self.maya_render_scene_line.setText(result[0])

    def _browse_maya_render_project(self):
        """Browse for a Maya Project workspace.mel file and set the base path into the Maya Render Project input.

        """
        logger.debug('entering _browse_maya_render_project')
        result = QtWidgets.QFileDialog.getOpenFileName(self, "Find maya workspace.mel in project directory...",
                                                       START_DIR, WORKSPACE)
        if result and result[0]:
            self.maya_render_project_line.setText(os.path.dirname(result[0]))

    def _browse_maya_output(self):
        """Browse for a Maya Output Directory and set it in the Maya Output Directory input.

        """
        logger.debug('entering _browse_maya_output')
        result = QtWidgets.QFileDialog.getExistingDirectory(self, 'Select Render Output Path', START_DIR)
        if result:
            self.maya_render_output_line.setText(result)

    def _get_render_layers(self) -> str:
        """Return all checked render layer names from the render layer tree as a comma separated list.
        
        Returns:
            str: All checked render layers as a comma separated list.

        """
        result = []
        for i in range(self.maya_render_rl_tree.topLevelItemCount()):
            item = self.maya_render_rl_tree.topLevelItem(i)
            if item.checkState(0):
                result.append(item.text(0))
        return ','.join(result)

    def _get_requirements(self) -> str:
        """Return all check requirements pre-formatted for submission into the database.

        Returns:
            str: Checked requirements pre-formatted for the database.

        """
        req_list = []
        for check in self.req_checks:
            if check.isChecked():
                req_list.append(str(check.text()))

        return "%{}%".format("%".join(sorted(req_list)))

    def _update_frames(self):
        """Update the "X Frames" label.

        """
        s = self.maya_render_start_frame_spin.value()
        e = self.maya_render_end_frame_spin.value()
        b = self.maya_render_by_frame_spin.value()
        all_frames = len(range(s, e)[::b])
        all_frames = 1 if not all_frames else all_frames
        s = '{} Frames'
        self.maya_render_batch_info_label.setText(s.format(all_frames))

    def update_layout(self):
        """Update the layout to reflect the users mode selection.

        """
        logger.debug('Updating Layout')
        layout = self.job_type_combo.currentText()
        for group_name, grp in self._group_layouts.items():
            if group_name == layout:
                grp.setEnabled(True)
                grp.setHidden(False)
            else:
                grp.setEnabled(False)
                grp.setHidden(True)

        self.centralWidget().adjustSize()
        self.adjustSize()

    def _rl_context_menu(self, pos: QtCore.QPoint):
        """Generate and show a context menu for the render layer tree.

        Args:
            pos (QtCore.QPoint): QPoint where the click occurred.

        """
        menu = QtWidgets.QMenu()
        act = menu.addAction('Add Layer')
        act.triggered.connect(self._add_rl_handler)

        act = menu.addAction('Remove Item')
        act.triggered.connect(self._remove_rl_handler)

        menu.exec_(self.maya_render_rl_tree.mapToGlobal(pos))

    def _populate_reqs(self):
        """Fetch requirements from the database and generate checkboxes for each.

        """
        requirements = sql.HydraCapabilities.fetch()
        col, row = 0, 0
        for req in [req.name for req in requirements]:
            c = QtWidgets.QCheckBox(req)
            self.reqs_grid.addWidget(c, row, col)
            if col == 2:  # End of row
                row += 1
                col = 0
            else:
                col += 1
            self.req_checks.append(c)

    def _setup_widgets(self):
        """Set basic widget settings.

        """
        self.status_ready_button.setChecked(True)
        self.job_type_combo.addItems(['Maya Render', 'MayaPy', 'Command'])
        self.maya_render_rl_tree.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)

    def _signals(self):
        """Setup Signals for user interaction.

        """
        # Main
        self.submit_btn.clicked.connect(self._submit)
        self.job_type_combo.currentIndexChanged.connect(self.update_layout)

        # Maya Render
        self.maya_render_scene_btn.clicked.connect(self._browse_maya_render_scene)
        self.maya_render_project_btn.clicked.connect(self._browse_maya_render_project)
        self.maya_render_output_btn.clicked.connect(self._browse_maya_output)
        self.add_rl_btn.clicked.connect(self._add_rl_handler)
        self.remove_rl_btn.clicked.connect(self._remove_rl_handler)
        self.maya_render_rl_tree.customContextMenuRequested.connect(self._rl_context_menu)

        self.maya_render_start_frame_spin.valueChanged.connect(self._update_frames)
        self.maya_render_end_frame_spin.valueChanged.connect(self._update_frames)
        self.maya_render_by_frame_spin.valueChanged.connect(self._update_frames)

    def _submit(self):
        """Submit a job and tasks with the current settings into the database.

        """
        logger.debug('entering _submit')
        mode = self.job_type_combo.currentText()

        status = 'R' if self.status_ready_button.isChecked() else 'U'

        job = sql.HydraRenderJob()

        job.name = self.job_name_line.text()
        job.mode = mode
        job.requirements = self._get_requirements()
        job.args = self.args_line.text()
        job.status = status
        job.priority = self.priority_spinbox.value()
        job.max_nodes = self.max_nodes_spinbox.value()
        job.timeout = self.timeout_spinbox.value()
        job.max_attempts = self.max_failures_spinbox.value()

        frame_list = [-1]

        if mode == 'Maya Render':
            start_frame = self.maya_render_start_frame_spin.value()
            end_frame = self.maya_render_end_frame_spin.value()
            by_frame = self.maya_render_by_frame_spin.value()

            if start_frame > end_frame:
                err = 'Start frame of {} cannot be more than end frame of {}'
                raise ValueError(err.format(start_frame, end_frame))

            frame_list = list(range(start_frame, (end_frame + 1)))[::by_frame]
            frame_list += [end_frame] if end_frame not in frame_list else []

            job.task_file = self.maya_render_scene_line.text()
            job.start_frame = start_frame
            job.end_frame = end_frame
            job.by_frame = by_frame
            job.render_layers = self._get_render_layers()
            job.project = self.maya_render_project_line.text()
            job.output_directory = self.maya_render_output_line.text()

        elif mode == 'MayaPy':
            script = self.mayapy_script_text.toPlainText().replace('\n', ';')
            job.script = script

        else:
            job.script = self.command_line.text()

        if hasattr(job, 'script') and len(job.script) > 2048:
            raise ValueError('Script cannot be longer than 2048 characters.')

        job.insert()
        logger.info('Submitted Job %s', job.id)

        tasks = []
        for frame in frame_list:
            t = sql.HydraRenderTask()
            t.job_id = job.id
            t.status = status
            t.priority = self.priority_spinbox.value()
            t.start_frame = frame
            t.end_frame = frame
            tasks.append(t)

        for t in tasks:
            t.insert()
            logger.info('Submitted Task %s', t.id)

        about_box(self, 'Submitted!', 'Submitted 1 jobs and {} tasks.'.format(len(tasks)))


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle('Fusion')
    window = SubmitterMain()
    retcode = app.exec_()
