"""Sets up a global logger instance for use in other modules."""
import os
import sys
import ast
import logging
import pathlib
from logging import handlers

from hydra_farm.constants import BASELOGDIR  # TODO: Move this?

console_formatter = logging.Formatter("%(asctime)s %(levelname)-9s%(message)s\n"
                                      "%(pathname)s line %(lineno)s\n")

file_formatter = logging.Formatter("%(asctime)s %(levelname)-9s%(message)s\n"
                                   "%(pathname)s line %(lineno)s\n")

logger = logging.getLogger('hydra_farm')
logger.setLevel(logging.DEBUG)
debug_mode = os.environ.get('HydraFarm_Debug_Mode', True)
if not isinstance(debug_mode, bool):
    debug_mode = bool(ast.literal_eval(debug_mode))
log_dir = os.environ.get('HydraFarm_Log_Dir', BASELOGDIR)

try:
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.DEBUG)
    stream_handler.setFormatter(console_formatter)
    logger.addHandler(stream_handler)
except AttributeError:
    sys.stderr = sys.stdout

if sys.argv[0]:
    appname = sys.argv[0].replace('\\', '/').split('/')[-1]
    appname = os.path.splitext(appname)[0]
else:
    appname = "interpreter_output"

log_dir = pathlib.Path(log_dir, appname + '.log')
log_dir.parent.mkdir(parents=True, exist_ok=True)
file_logger = logging.handlers.TimedRotatingFileHandler(str(log_dir), when="midnight", backupCount=7)
file_logger.setLevel(logging.DEBUG if debug_mode else logging.INFO)
file_logger.setFormatter(file_formatter)
logger.addHandler(file_logger)
