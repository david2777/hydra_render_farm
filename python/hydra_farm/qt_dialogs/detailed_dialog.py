"""Detailed Data Dialog"""
from PyQt5 import QtWidgets, uic

from hydra_farm.utils import resource_resolver


class DetailedDialog(QtWidgets.QDialog):
    def __init__(self, record, parent=None):
        super(DetailedDialog, self).__init__(parent)
        uic.loadUi(resource_resolver.get_resource('resources', 'ui', 'detailed_dialog.ui'), self)

        self.record = record
        # Connect Buttons
        self.okButton.clicked.connect(self.close)
        self.update_view()

    def update_view(self):
        columns = self.record[0].columns
        # columns = [label_factory(col) for col in columns if '__' not in col]
        #
        # clear_layout(self.detailedGridLayout)
        # setup_data_grid(self.record, columns, self.detailedGridLayout)

    @classmethod
    def create(cls, data):
        dialog = DetailedDialog(data)
        dialog.exec_()
