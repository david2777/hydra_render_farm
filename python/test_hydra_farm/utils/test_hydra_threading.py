import unittest

from hydra_farm.utils import hydra_threading as ht


def simple_target():
    pass


class MyTestCase(unittest.TestCase):
    def test_simple_threads(self):
        ht.HydraThreadManager.shutdown()
        thread = ht.HydraThread('test', simple_target, 5, 0)
        self.assertEqual(False, thread.stopped)
        ht.HydraThreadManager.add_thread(thread)
        self.assertEqual(1, len(ht.HydraThreadManager.all_threads))
        thread2 = ht.HydraThread('test', simple_target, 5, 0)
        ht.HydraThreadManager.add_thread(thread2)
        self.assertEqual(2, len(ht.HydraThreadManager.all_threads))
        ht.HydraThreadManager.shutdown()
        self.assertEqual(0, len(ht.HydraThreadManager.all_threads))


if __name__ == '__main__':
    unittest.main()
