"""Simple Data Table Dialog"""
from typing import List

from PyQt5 import QtWidgets, uic

from hydra_farm.database import hydra_db
from hydra_farm.utils import resource_resolver
from hydra_farm.utils.logging_setup import logger


class RecordViewDialog(QtWidgets.QDialog):
    """Simple dialog for displaying a list of records in a table view."""
    records: List

    ok_button: QtWidgets.QPushButton
    record_tree: QtWidgets.QTreeWidget

    def __init__(self, parent: QtWidgets.QMainWindow, records: List[hydra_db.AbstractHydraTable]):
        """Simple dialog for displaying a list of records in a table view.

        Args:
            parent (QtWidgets.QMainWindow): Parent Window
            records (List[hydra_db.AbstractHydraTable]): List of hydra record instances.

        """
        super(RecordViewDialog, self).__init__(parent)
        uic.loadUi(resource_resolver.get_resource('resources', 'ui', 'record_view_dialog.ui'), self)

        self.records = records
        # noinspection PyTypeChecker
        self.ok_button.clicked.connect(self.close)

        classes = {r.__class__.__name__ for r in self.records}
        if len(classes) != 1:
            QtWidgets.QMessageBox.warning(self, 'Bad Data',
                                          f'Cannot have more than one class type in record view. Given:\n{classes}')
            return

        self.populate_record_tree()
        self.show()

    def populate_record_tree(self):
        """Populate the record tree with the records"""
        logger.debug('Populating with %s records', len(self.records))
        cols = sorted(self.records[0].columns)
        self.record_tree.setHeaderLabels(cols)

        for record in self.records:
            item = QtWidgets.QTreeWidgetItem()
            for i, col in enumerate(cols):
                item.setText(i, str(record.get_attr_static(col)))
            self.record_tree.addTopLevelItem(item)

        for col in range(len(cols)):
            self.record_tree.resizeColumnToContents(col)
