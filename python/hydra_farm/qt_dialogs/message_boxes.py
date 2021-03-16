"""Basic Message Boxes"""
from PyQt5.QtWidgets import QMessageBox, QInputDialog


def about_box(parent, title="About", msg="This is a sample about box."):
    """Creates a message box with an OK button, suitable for displaying short
    messages to the user."""
    QMessageBox.about(parent, title, msg)


def warning_box(parent, title="Warning!", msg="This is a sample warning!"):
    """Creates a message box with an OK button and a yellow yeild sign, suitable
    for displaying short errors/warning messages to the user."""
    return QMessageBox.warning(parent, title, msg)


def yes_no_box(parent, title="Yes/No?", msg="This is a sample yes/no dialog."):
    """Creates a message box with Yes and No buttons. Returns QMessageBox.Yes
    if the user clicked Yes, or QMessageBox.No otherwise."""
    return QMessageBox.question(parent, title, msg, buttons=(QMessageBox.Yes | QMessageBox.No),
                                defaultButton=QMessageBox.Yes)


def int_box(parent, title="IntBox", msg="This is a sample int dialog.", default=0):
    """Makes a box for getting ints"""
    return QInputDialog.getInt(parent, title, msg, default)


def str_box(parent, title="StrBox", msg="This is a sample StrBox."):
    """Makes a box for getting strings"""
    return QInputDialog.getText(parent, title, msg)
