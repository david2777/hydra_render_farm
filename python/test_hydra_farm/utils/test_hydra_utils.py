import time
import unittest

from hydra_farm.utils import hydra_utils


class TestHydraUtils(unittest.TestCase):
    def test_my_host_name(self):
        """Test that my_host_name returns a string, just in case this doesn't work on some platforms.

        """
        this_host = hydra_utils.my_host_name()
        self.assertIsInstance(this_host, str)

    def test_strip_sql_query(self):
        """Test the strip_sql_query functionality.

        """
        i = """SELECT T.*
                    FROM hydra.tasks T
                    JOIN
                        (SELECT id,
                                failed_nodes,
                                attempts,
                                max_attempts,
                                max_nodes,
                                requirements,
                                archived
                         FROM hydra.jobs) J ON (T.job_id = J.id)"""

        o = "SELECT T.* FROM hydra.tasks T JOIN (SELECT id, failed_nodes, attempts, max_attempts, max_nodes, " \
            "requirements, archived FROM hydra.jobs) J ON (T.job_id = J.id)"

        self.assertEqual(o, hydra_utils.strip_sql_query(i))

    def test_hasattr_static(self):
        """Test hydra_utils.hasattr_static

        """
        class Test(object):
            attribute = True

            def __getattr__(self, attr):  # Will return True for any attribute
                return True

        obj = Test()
        self.assertTrue(hasattr(obj, 'attribute'))
        self.assertTrue(hydra_utils.hasattr_static(obj, 'attribute'))
        self.assertTrue(hasattr(obj, 'does_not_exist'))
        self.assertFalse(hydra_utils.hasattr_static(obj, 'does_not_exist'))


if __name__ == '__main__':
    unittest.main()
