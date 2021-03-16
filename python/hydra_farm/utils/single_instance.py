"""Uses a temp file to ensure only a single instance of a software is running."""
import os
import sys
import pathlib

from hydra_farm.utils.logging_setup import logger
from hydra_farm.constants import BASEDIR


class InstanceLock(object):
    """Class using temp files to ensure only a single instance of a software is running."""
    temp_file = None

    def __init__(self, name: str):
        """Class using temp files to ensure only a single instance of a software is running.

        Args:
            name (str): Software name to lock.

        """
        self.locked = False
        self.name = name
        self.temp_file_path = pathlib.Path(BASEDIR, '{}.lock'.format(self.name))
        logger.info("Temp File: %s", self.temp_file_path)

        # Windows
        if sys.platform.startswith("win"):
            try:
                if self.temp_file_path.exists():
                    self.temp_file_path.unlink()
                    logger.debug("Unlinked %s", self.temp_file_path)
                self.temp_file = os.open(self.temp_file_path, os.O_CREAT | os.O_EXCL | os.O_RDWR)
                self.locked = True
            except Exception as e:
                try:
                    if e.errno == 13:
                        logger.error("Another Instance of %s is already running!", self.name)
                        return
                except AttributeError:
                    pass
                logger.error(e)

        # Linux
        else:
            import fcntl
            self.temp_file = open(self.temp_file_path, "w")
            self.temp_file.flush()
            try:
                fcntl.lockf(self.temp_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
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
            if self.temp_file is not None:
                try:
                    self.temp_file.close()
                    os.unlink(self.temp_file_path)
                except Exception as e:
                    logger.error(e)
            else:
                logger.warning("No temp file found for %s", self.name)
        else:
            import fcntl
            try:
                fcntl.lockf(self.temp_file, fcntl.LOCK_UN)
                if os.path.isfile(self.temp_file_path):
                    os.unlink(self.temp_file_path)
            except Exception as e:
                logger.error(e)
