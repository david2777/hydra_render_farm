from PyQt5 import QtWidgets


def clear_layout(layout):
    while layout.count():
        child = layout.takeAt(0)
        if child.widget() is not None:
            child.widget().deleteLater()
        elif child.layout() is not None:
            clear_layout(child.layout())


def setup_data_grid(records, columns, grid):
    """Populate a data grid. "columns" is a list of widget factory objects."""
    # Build the header row
    for(column, attr) in enumerate(columns):
        item = grid.itemAtPosition(0, column)
        if item:
            grid.removeItem(item)
            item.widget().hide()
        grid.addWidget(attr.header_widget(), 0, column)

    # Build the data rows
    for(row, record) in enumerate(records):
        for(column, attr) in enumerate(columns):
            item = grid.itemAtPosition(row + 1, column)
            if item:
                grid.removeItem(item)
                item.widget().hide()
            grid.addWidget(attr.data_widget(record), row + 1, column)


class widget_factory(object):
    """A widget building class intended to be subclassed for building particular
    types of widgets. 'name' must be the name of a database column."""

    def __init__(self, name, intention=None):
        self.name = name
        self.intention = intention

    def header_widget(self):
        """Makes a label for the header row of the display."""

        return QtWidgets.QLabel('<b>' + self.name + '</b>')

    def data(self, record):

        return str(getattr(record, self.name))

    def data_widget(self, record):
        """Create a QWidget instance and return a reference to it. To make a
        widget, given a record, extract the named attribute from the record
        with the data method, and use that as the widget's text/data."""

        raise NotImplementedError()


class label_factory(widget_factory):
    """A label widget factory. The object's name is the name of a database
    column."""

    def data_widget(self, record):
        return QtWidgets.QLabel(self.data(record))
