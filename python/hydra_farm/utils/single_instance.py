"""Uses a temp file to ensure only a single instance of a software is running."""
import os
import sys
import pathlib
from typing import TextIO, Union
if not sys.platform.startswith("win"):
    import fcntl

from hydra_farm.utils.logging_setup import logger
from hydra_farm.constants import BASEDIR


class InstanceLock(object):
    """Class using temp files to ensure only a single instance of a software is running."""
    name: str
    locked: bool = False
    temp_file_path: pathlib.Path
    temp_file_handle: Union[TextIO, int] = None

    def __init__(self, name: str):
        """Class using temp files to ensure only a single instance of a software is running.

        Args:
            name (str): Software name to lock.

        """
        self.name = name
        self.temp_file_path = pathlib.Path(BASEDIR, f'{self.name}.lock')
        logger.info("Temp File: %s", self.temp_file_path)

        # Windows
        if sys.platform.startswith("win"):
            try:
                if self.temp_file_path.exists():
                    self.temp_file_path.unlink()
                    logger.debug("Unlinked %s", self.temp_file_path)
                self.temp_file_handle = os.open(self.temp_file_path, os.O_CREAT | os.O_EXCL | os.O_RDWR)
                self.locked = True
            except OSError as e:
                if e.errno == 13:
                    logger.error("Another Instance of %s is already running!", self.name)
                    return

        # Linux
        else:
            self.temp_file_handle = open(self.temp_file_path, "w")
            self.temp_file_handle.flush()
            try:
                fcntl.lockf(self.temp_file_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                self.locked = True
            except IOError:
                logger.error("Another Instance of %s is already running", self.name)

    def is_locked(self) -> bool:
        """Returns True if the software is already running, False if not.

        Returns:
            bool: True if the software is already running, False if not.

        """
        return self.locked

    def remove(self):
        """Unlock the software by removing the temp file.

        Returns:
            None

        """
        if not self.locked:
            logger.debug('%s is not locked', self.name)
            return

        if sys.platform.startswith("win"):
            if self.temp_file_handle is not None:
                try:
                    os.close(self.temp_file_handle)
                    if self.temp_file_path.exists():
                        self.temp_file_path.unlink()
                    self.locked = False
                except Exception:
                    logger.exception(f'Unhandled Exception Unlocking {self.temp_file_path}')
            else:
                logger.warning("No temp file found for %s", self.name)
        else:
            try:
                fcntl.lockf(self.temp_file_handle, fcntl.LOCK_UN)
                if self.temp_file_path.exists():
                    self.temp_file_path.unlink()
                self.locked = False
            except Exception:
                logger.exception(f'Unhandled Exception Unlocking {self.temp_file_path}')
