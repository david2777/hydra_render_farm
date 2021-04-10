"""Module for handling yaml config files."""
from typing import Union
from pathlib import Path
from functools import lru_cache
from collections import UserDict

from ruamel import yaml

from hydra_farm.utils import resource_resolver


class YamlCache(UserDict):
    """Simple yaml cache object used for reading and writing yaml files."""
    yaml_path: Path
    data: dict

    def __init__(self, yaml_path: Union[str, Path]):
        """Simple yaml cache object used for reading and writing yaml files.

        Args:
            yaml_path (str, Path): Path to yaml file

        """
        super(YamlCache, self).__init__()
        self.yaml_path = Path(yaml_path)
        self.load_yaml()

    def load_yaml(self):
        """Read the data from the yaml file.

        """
        _yml = yaml.YAML(typ='rt')
        if self.yaml_path.is_file():
            with open(str(self.yaml_path.resolve()), 'r') as f:
                self.data = _yml.load(f)
        else:
            self.data = {}

    def write_yaml(self):
        """Write the data to the yaml file.

        """
        if not self.yaml_path.parent.exists():
            self.yaml_path.parent.mkdir(parents=True)
        with open(str(self.yaml_path.resolve()), 'w') as f:
            yaml.dump(self.data, f, Dumper=yaml.RoundTripDumper)


@lru_cache
def get_yaml_cache(yaml_path: Union[str, Path]) -> YamlCache:
    """Returns a yaml cache object for a given yaml file.

    Args:
        yaml_path (str, Path): Path to yaml file.

    Returns:
        YamlCache: yaml cache object

    """
    return YamlCache(yaml_path)


def get_hydra_cfg() -> YamlCache:
    """Returns the yaml cache object for the hydra cfg.

    Returns:
        YamlCache: yaml cache object for the hydra cfg.

    """
    return get_yaml_cache(resource_resolver.get_hydra_cfg())


def get_project_yml() -> YamlCache:
    """Returns the yaml cache object for the project yaml.

    Returns:
        YamlCache: yaml cache object for the project yaml.

    """
    return get_yaml_cache(resource_resolver.get_project_yml())
