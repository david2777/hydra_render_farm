import os
import unittest

os.environ['Hydra_Unit_Test'] = 'True'

from hydra_farm.database import hydra_db as sql


class TestEnums(unittest.TestCase):
    """Test Status and Color enums.

    """

    def test_status_color_coverage(self):
        """Test that all statuses have colors in Color.

        """
        for status in sql.HydraStatus:
            try:
                sql.Color[status.value]
            except KeyError:
                self.fail('{} is not in sql.Color'.format(status.value))

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


class TestTransaction(unittest.TestCase):
    """Run some basic tests on Transaction.

    """

    @classmethod
    def setUpClass(cls):
        """Test that we have all the db login info we need to run this test.

        """
        t = sql.Transaction()
        self = cls()
        self.assertIsInstance(t.host, str)
        self.assertIsInstance(t.db_username, str)
        self.assertIsInstance(t.db_password, str)
        self.assertIsInstance(t.database_name, str)
        self.assertIsInstance(t.port, int)

    def test_context(self):
        """Test that the transaction context manager is working.

        """
        t = sql.Transaction()
        self.assertFalse(t.in_transaction)
        with t:
            self.assertTrue(t.in_transaction)
        self.assertFalse(t.in_transaction)


class TestAbstractHydraTable(unittest.TestCase):
    _render_node: sql.HydraRenderNode

    @classmethod
    def setUpClass(cls):
        """Setup by getting the first node in the Render Node table.

        """
        cls._render_node = sql.HydraRenderNode.fetch()[0]

    def test_get_attr(self):
        """Test that we can get the two cols we requested by accessing them with node.attr.

        """
        self.assertEqual(1, self._render_node.id)
        self.assertIsInstance(self._render_node.host, str)
        self.assertIsInstance(self._render_node.status, str)

    def test_getattr_col(self):
        """Test looking up a col we didn't request on the db.

        """
        self.assertIsInstance(self._render_node.platform, str)

    def test_set_attr(self):
        """Test setting an attr and making sure it shows up in _dirty.

        """
        current_status = self._render_node.status
        self._render_node._dirty.clear()
        # Set status to Z (not a real status)
        self._render_node.status = 'Z'
        # Check the result and that status is in _dirty
        self.assertEqual('Z', self._render_node.status)
        self.assertSetEqual({'status'}, self._render_node._dirty)
        # Reset
        self._render_node.status = current_status
        self._render_node._dirty.clear()

    def test_set_no_dirty(self):
        """Test setting an attr with set_no_dirty and checking that _dirty remains empty.

        """
        current_status = self._render_node.status
        self._render_node._dirty.clear()
        # Set status to Z (not a real status)
        self._render_node.set_no_dirty('status', 'Z')
        # Check the result and that _dirty is empty
        self.assertEqual('Z', self._render_node.status)
        self.assertSetEqual(set(), self._render_node._dirty)
        # Reset
        self._render_node.status = current_status
        self._render_node._dirty.clear()

    def test_status_enum(self):
        """Test node.status_enum making sure it returns an HydraStatus Enum object.

        """
        self.assertIsInstance(self._render_node.status_enum, sql.HydraStatus)


class BaseTests:
    class TestHydraTable(unittest.TestCase):
        """Base tests ofr hydra tables.

        """
        table: sql.AbstractHydraTable

        def test_column_coverage(self):
            """Test that we've properly defined all of the columns in the table by comparing the server to the class.

            """
            with sql.Transaction() as t:
                t.cur.execute('DESCRIBE {}'.format(self.table.table_name))
                cols = set([desc[0] for desc in t.cur.fetchall()])
            self.assertSetEqual(self.table.columns, cols)


class TestHydraRenderNode(BaseTests.TestHydraTable):
    table = sql.HydraRenderNode

    def test_query(self):
        """Test that we can resolve a node.

        """
        self.assertIsInstance(self.table.fetch()[0], self.table)


class TestHydraRenderJob(BaseTests.TestHydraTable):
    table = sql.HydraRenderJob


class TestHydraRenderTask(BaseTests.TestHydraTable):
    table = sql.HydraRenderTask


class TestHydraCapabilities(BaseTests.TestHydraTable):
    table = sql.HydraCapabilities


if __name__ == '__main__':
    unittest.main()
