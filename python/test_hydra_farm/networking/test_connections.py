import unittest

from hydra_farm.networking import connections


class TestHydraRequest(unittest.TestCase):
    def test_from_args_empty(self):
        request = connections.HydraRequest.from_args()
        self.assertIsInstance(request, connections.HydraRequest)
        self.assertEqual(request.cmd, "")
        self.assertEqual(request.args, ())
        self.assertEqual(request.kwargs, {})

    def test_from_args_full(self):
        request = connections.HydraRequest.from_args('test_cmd', ('test_arg1', 'test_arg2'), {'test_kwarg1': 1})
        self.assertEqual(request.cmd, 'test_cmd')
        self.assertEqual(request.args, ('test_arg1', 'test_arg2'))
        self.assertEqual(request.kwargs, {'test_kwarg1': 1})

    def test_from_bytes(self):
        x = b'{"cmd": "test_cmd", "args": ["test_arg1", "test_arg2"], "kwargs": {"test_kwarg1": 1}}'
        request = connections.HydraRequest.from_bytes(x)
        self.assertEqual(request.cmd, 'test_cmd')
        self.assertEqual(request.args, ('test_arg1', 'test_arg2'))
        self.assertEqual(request.kwargs, {'test_kwarg1': 1})

    def test_as_bytes(self):
        request = connections.HydraRequest.from_args('test_cmd', ('test_arg1', 'test_arg2'), {'test_kwarg1': 1})
        x = b'{"cmd": "test_cmd", "args": ["test_arg1", "test_arg2"], "kwargs": {"test_kwarg1": 1}}'
        self.assertEqual(x, request.as_json_bytes())


class TestHydraResponse(unittest.TestCase):
    def test_from_args_empty(self):
        request = connections.HydraResponse.from_args()
        self.assertIsInstance(request, connections.HydraResponse)
        self.assertEqual(request.msg, "")
        self.assertEqual(request.err, True)

    def test_from_args_full(self):
        request = connections.HydraResponse.from_args('Test Response', False)
        self.assertIsInstance(request, connections.HydraResponse)
        self.assertEqual(request.msg, 'Test Response')
        self.assertEqual(request.err, False)

    def test_from_bytes(self):
        x = b'{"msg": "Test Response", "err": false}'
        request = connections.HydraResponse.from_bytes(x)
        self.assertEqual(request.msg, 'Test Response')
        self.assertEqual(request.err, False)

    def test_as_bytes(self):
        request = connections.HydraResponse.from_args('Test Response', False)
        x = b'{"msg": "Test Response", "err": false}'
        self.assertEqual(x, request.as_json_bytes())


if __name__ == '__main__':
    unittest.main()
