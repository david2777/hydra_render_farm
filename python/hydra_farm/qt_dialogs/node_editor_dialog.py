"""Node Editor"""
import sys

from PyQt5 import QtWidgets, uic

import hydra_farm.database.hydra_db as sql
from hydra_farm.utils import resource_resolver


class NodeEditorDialog(QtWidgets.QDialog):
    def __init__(self, defaults, parent=None):
        super(NodeEditorDialog, self).__init__(parent)
        uic.loadUi(resource_resolver.get_resource('resources', 'ui', 'node_editor.ui'), self)

        # Variables
        self.save = False
        self.comp_checks = []

        # Connect Buttons
        self.cancelButton.clicked.connect(self.cancel_button_handler)
        self.okButton.clicked.connect(self.ok_button_handler)

        # Load requirements and populate checkboxes
        self.populate_comps()

        self.defaults = defaults
        if defaults:
            title = "Editing {0}:".format(defaults["host"])
            self.editorGroup.setTitle(title)
            self.minPrioritySpinbox.setValue(defaults["priority"])
            if defaults["ip_addr"]:
                self.ipLineEdit.setText(defaults["ip_addr"])
            if bool(defaults["is_render_node"]):
                self.renderNodeCheckBox.setCheckState(2)

            cbxList = defaults["comps"]
            for cbx in self.comp_checks:
                if cbx.text() in cbxList:
                    cbx.setCheckState(2)

    def populate_comps(self):
        # Get requirements master list from the DB
        compatibilities = sql.HydraCapabilities.fetch()
        compatibilities = [comp.name for comp in compatibilities]
        self.comp_checks = []
        col = 0
        row = 0
        for item in compatibilities:
            c = QtWidgets.QCheckBox(item)
            self.compGrid.addWidget(c, row, col)
            if col == 2:
                row += 1
                col = 0
            else:
                col += 1

            self.comp_checks.append(c)

    def get_comps(self):
        comp_list = []
        for check in self.comp_checks:
            if check.isChecked():
                comp_list.append(str(check.text()))
        return sorted(comp_list)

    def get_values(self):
        comps = " ".join(self.get_comps())
        r_dict = {"priority": int(self.minPrioritySpinbox.value()),
                  "comps": comps,
                  "is_render_node": bool(self.renderNodeCheckBox.isChecked()),
                  "ip_addr": str(self.ipLineEdit.text())}
        return r_dict

    def cancel_button_handler(self):
        self.close()

    def ok_button_handler(self):
        self.save = True
        self.close()

    @classmethod
    def create(cls, defaults) -> dict:
        dialog = NodeEditorDialog(defaults)
        dialog.exec_()
        if dialog.save:
            return dialog.get_values()


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = NodeEditorDialog(None, None)
    window.show()
    retcode = app.exec_()
