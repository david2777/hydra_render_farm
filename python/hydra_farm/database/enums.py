"""Define Enums"""
from enum import Enum

from PyQt5 import QtGui


class HydraStatus(Enum):
    """Enum to store statuses used for Jobs, Tasks, and Nodes.

    """
    # Both Status
    STARTED = 'S'  # Job in progress

    # Job/Task Status
    READY = 'R'  # Ready to be run by a render node
    PAUSED = 'U'  # Job was paused
    FINISHED = 'F'  # Job complete
    KILLED = 'K'  # Job was killed
    ERROR = 'E'  # Job returned a non-zero exit code
    CRASHED = 'C'  # Machine or server software crashed, task was found in host's DB record upon restart
    TIMEOUT = 'T'  # Job took longer than the timeout time allowed

    # Node Status
    IDLE = 'I'  # Ready to accept jobs
    OFFLINE = 'O'  # Not ready to accept jobs
    PENDING = 'P'  # Offline after current job is complete
    GETOFF = 'G'  # Getting off node

    def __eq__(self, other):
        if isinstance(other, str):
            return bool(self.value == other)  # Overriding so that 'S' == HydraStatus.STARTED is True.
        else:
            return super().__eq__(other)

    def __hash__(self):
        return hash(self.value)  # Using value here so that 'S' in {HydraStatus.STARTED} is True.

    @property
    def nice_name(self) -> str:
        """Return the enum name capitalized. Eg READY => Ready.

        Returns:
            str: The enum name capitalized.

        """
        return self.name.capitalize()


class Color(Enum):
    """"Enum to store colors with a method to return them as QColors.

    """
    U = (240, 230, 200)  # Light Orange
    R = (255, 255, 255)  # White
    F = (200, 240, 200)  # Light Green
    K = (240, 200, 200)  # Light Red
    C = (220,  90,  90)  # Dark Red
    S = (200, 220, 240)  # Light Blue
    E = (220,  90,  90)  # Red
    I = (255, 255, 255)  # White
    O = (240, 240, 240)  # Gray
    P = (240, 230, 200)  # Orange
    T = (220,  90,  90)  # Dark Red
    G = (220,  90,  90)  # Dark Red

    @property
    def q_color(self) -> QtGui.QColor:
        """Returns the color value as a Qt QColor.

        Returns:
            QtGui.QColor: A QColor of the color value.

        """
        return QtGui.QColor(*self.value)
