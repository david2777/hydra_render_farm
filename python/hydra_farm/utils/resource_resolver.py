"""Resolving file paths within the project"""
import sys
from pathlib import Path

from hydra_farm.constants import BASEDIR
from hydra_farm.utils.logging_setup import logger

try:
    base_path = Path(sys._MEIPASS)  # Todo: Test
except AttributeError:
    import hydra_farm
    base_path = Path(hydra_farm.__file__).parents[2]


def get_resource(*parts, warn: bool = False) -> Path:
    """Returns a path up from the project root given a list of path parts.

    Args:
        parts: Path parts to add to the project root.
        warn (bool): If True will warn if a path does not exist, default False.

    Returns:
        Path: Path of project root plus parts, project root if none given.

    """
    if not parts:
        return base_path
    path = Path(base_path, *parts)
    if warn and not path.exists():
        logger.warning('%s does not exist', path)
    return path


def get_default_hydra_cfg() -> Path:
    """Returns the path to the default config hydra_cfg.yml

    Returns:
        Path: Path to default config hydra_cfg.yml

    """
    return get_resource('configs', 'hydra_cfg.yml')


def get_hydra_cfg() -> Path:
    """Returns the path to the live config hydra_cfg.yml

    Returns:
        Path: Path to live config hydra_cfg.yml

    """
    return Path(BASEDIR, 'hydra_cfg.yml')


def get_project_yml() -> Path:
    """Returns the path to the project.yml file

    Returns:
        Path: Path to project.yml
    """
    return get_resource('configs', 'project.yml')
