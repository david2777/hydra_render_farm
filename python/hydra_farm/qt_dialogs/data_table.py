"""Simple Data Table Dialog"""
from PyQt5 import QtWidgets, uic

from hydra_farm.utils import resource_resolver


class DataTableDialog(QtWidgets.QDialog):
    def __init__(self, record, parent=None):
        super(DataTableDialog, self).__init__(parent)
        uic.loadUi(resource_resolver.get_resource('resources', 'ui', 'data_table_dialog.ui'), self)

        self.record = record
        self.OkButton.clicked.connect(self.close)
        self.build_data_table()

    def build_data_table(self):
        rows = self.record.columns
        self.DataTable.setRowCount(len(rows))
        self.DataTable.setVerticalHeaderLabels(rows)

        for pos, row in enumerate(rows):
            self.DataTable.setItem(pos, 0, QtWidgets.QTableWidgetItem(str(getattr(self.record, row))))

    @classmethod
    def create(cls, data):
        dialog = DataTableDialog(data)
        dialog.exec_()
