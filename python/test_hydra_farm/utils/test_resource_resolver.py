import unittest
from pathlib import Path

from hydra_farm.utils import resource_resolver


class TestGetResource(unittest.TestCase):
    def test_find_module(self):
        """Test get_resource by getting it to resolve it's own path and checking that against it's __path__.

        """
        mod_path = Path(resource_resolver.__file__)
        resolved_path = resource_resolver.get_resource('python', 'hydra_farm', 'utils', 'resource_resolver.py')
        self.assertEqual(mod_path, resolved_path)
        self.assertTrue(resolved_path.is_file())

    def test_find_farmview_ico(self):
        """Test get_resource by resolving the FarmView.ico icon and checking that the file exists.

        """
        path = resource_resolver.get_resource('resources', 'icons', 'FarmView.ico')
        self.assertTrue(path.is_file())


class TestResolveYamls(unittest.TestCase):
    def test_resolve_default_cfg(self):
        """Test that we can resolve the default hydra cfg.

        """
        path = resource_resolver.get_default_hydra_cfg()
        self.assertTrue(path.is_file())

    def test_resolve_hydra_cfg(self):
        """Test that we can resolve the live hydra cfg.

        """
        path = resource_resolver.get_hydra_cfg()
        self.assertTrue(path.is_file())

    def test_resolve_project_yaml(self):
        """Test that we can resolve the project.yml file.

        """
        path = resource_resolver.get_project_yml()
        self.assertTrue(path.is_file())


if __name__ == '__main__':
    unittest.main()
