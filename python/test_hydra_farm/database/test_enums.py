import unittest

from hydra_farm.database import hydra_db as sql
from hydra_farm.database import enums


class TestEnums(unittest.TestCase):
    """Test Status and Color enums.

    """

    def test_status_color_coverage(self):
        """Test that all statuses have colors in Color.

        """
        for status in sql.HydraStatus:
            try:
                enums.Color[status.value]
            except KeyError:
                self.fail(f'{status.value} is not in enums.Color')

    def test_status_eq(self):
        """Test that we can compare strings and Enums to our HydraStatus class.

        """
        self.assertTrue('S' == sql.HydraStatus.STARTED)
        self.assertTrue(sql.HydraStatus.STARTED == sql.HydraStatus.STARTED)
        self.assertFalse('s' == sql.HydraStatus.STARTED)

    def test_nice_name(self):
        """Test that Enum.nice_name returns a nice version of the name.

        """
        self.assertEqual('Started', sql.HydraStatus.STARTED.nice_name)

    def test_hash(self):
        """Test that the enum hashing function does what we want.

        Returns:

        """
        enum_set = {sql.HydraStatus.STARTED, sql.HydraStatus.STARTED, sql.HydraStatus.READY}
        self.assertEqual(2, len(enum_set))
        self.assertIn(sql.HydraStatus.STARTED, enum_set)
        self.assertIn(sql.HydraStatus.READY, enum_set)
        self.assertIn("R", enum_set)
        self.assertNotIn("r", enum_set)
        self.assertNotIn(sql.HydraStatus.OFFLINE, enum_set)


if __name__ == '__main__':
    unittest.main()
