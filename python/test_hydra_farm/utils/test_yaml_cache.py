import unittest

from hydra_farm.utils import yaml_cache


class TestYamlCache(unittest.TestCase):
    def test_lru_cache(self):
        """Test that the LRU Cache is working by comparing the memory ids after calling the function twice.

        """
        config1 = yaml_cache.get_project_yml()
        config2 = yaml_cache.get_project_yml()
        self.assertEqual(id(config1), id(config2))

    def test_load(self):
        """Test that the data loads by asserting that 'version' is in the project yaml.

        """
        config = yaml_cache.get_project_yml()
        self.assertIn('version', config.data)


if __name__ == '__main__':
    unittest.main()
