"""Constants"""
import os
import sys

VERSION = 0.50

# Files
if sys.platform.startswith("win"):
    BASEDIR = r"C:\Hydra"
else:
    BASEDIR = os.path.join("~", "Hydra")

BASELOGDIR = os.path.join(BASEDIR, "logs")

# connections
MANYBYTES = 4096
