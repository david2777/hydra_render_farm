import unittest

from hydra_farm.utils import single_instance


class TestInstanceLock(unittest.TestCase):
    def test_instance_lock(self):
        lock = single_instance.InstanceLock('test_lock')
        self.assertTrue(lock.locked)

        lock2 = single_instance.InstanceLock('test_lock')
        self.assertFalse(lock2.locked)

        lock.remove()
        self.assertFalse(lock.locked)

        lock3 = single_instance.InstanceLock('test_lock')
        self.assertTrue(lock3.locked)

        self.assertEqual(lock3.locked, lock3.is_locked())
        lock3.remove()


if __name__ == '__main__':
    unittest.main()
