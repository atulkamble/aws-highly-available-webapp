import http.client
import io
import json
import os
import threading
import unittest
from unittest.mock import patch

from server import ApplicationServer, Handler, Settings


class FakeCounterClient:
    def __init__(self):
        self.calls = 0
        self.count = 41
        self.error = None
        self.last_request = None

    def invoke(self, **kwargs):
        self.calls += 1
        self.last_request = kwargs
        if self.error:
            raise self.error
        return {
            "Payload": io.BytesIO(
                json.dumps({"count": self.count + self.calls}).encode("utf-8")
            )
        }


class HandlerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.counter = FakeCounterClient()
        Handler.counter_client = cls.counter
        Handler.settings = Settings(
            host="127.0.0.1",
            port=0,
            aws_region="us-east-1",
            counter_function="test-counter",
        )
        cls.server = ApplicationServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.port = cls.server.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)
        Handler.counter_client = None
        Handler.settings = None

    def setUp(self):
        self.counter.calls = 0
        self.counter.count = 41
        self.counter.error = None
        self.counter.last_request = None

    def request(self, path, method="GET"):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=2)
        connection.request(method, path)
        response = connection.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        connection.close()
        return result

    def test_homepage_counts_one_request_and_sets_security_headers(self):
        status, headers, body = self.request("/")

        self.assertEqual(status, 200)
        self.assertEqual(self.counter.calls, 1)
        self.assertEqual(
            self.counter.last_request,
            {
                "FunctionName": "test-counter",
                "InvocationType": "RequestResponse",
                "Payload": b"{}",
            },
        )
        self.assertIn(b">42</div>", body)
        self.assertEqual(headers["Content-Type"], "text/html; charset=utf-8")
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(headers["X-Frame-Options"], "DENY")
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertTrue(headers["X-Request-ID"])

    def test_query_string_homepage_counts_once(self):
        status, _, _ = self.request("/?source=test")

        self.assertEqual(status, 200)
        self.assertEqual(self.counter.calls, 1)

    def test_health_endpoints_do_not_increment_counter(self):
        live_status, _, live_body = self.request("/health")
        ready_status, _, ready_body = self.request("/health/ready")

        self.assertEqual(live_status, 200)
        self.assertEqual(json.loads(live_body), {"status": "ok"})
        self.assertEqual(ready_status, 200)
        self.assertEqual(json.loads(ready_body), {"status": "ready"})
        self.assertEqual(self.counter.calls, 0)

    def test_readiness_fails_when_counter_client_is_not_initialized(self):
        Handler.counter_client = None
        try:
            status, _, body = self.request("/health/ready")
        finally:
            Handler.counter_client = self.counter

        self.assertEqual(status, 503)
        self.assertEqual(json.loads(body), {"status": "not_ready"})
        self.assertEqual(self.counter.calls, 0)

    def test_favicon_and_unknown_paths_do_not_increment_counter(self):
        favicon_status, _, _ = self.request("/favicon.ico")
        missing_status, _, _ = self.request("/does-not-exist")

        self.assertEqual(favicon_status, 204)
        self.assertEqual(missing_status, 404)
        self.assertEqual(self.counter.calls, 0)

    def test_head_does_not_increment_counter(self):
        status, headers, _ = self.request("/", method="HEAD")

        self.assertEqual(status, 405)
        self.assertEqual(headers["Allow"], "GET")
        self.assertEqual(self.counter.calls, 0)

    def test_counter_failure_keeps_homepage_available(self):
        self.counter.error = TimeoutError("simulated timeout")

        status, _, body = self.request("/")

        self.assertEqual(status, 200)
        self.assertIn("Counter temporarily unavailable".encode(), body)
        self.assertNotIn(b"simulated timeout", body)
        self.assertEqual(self.counter.calls, 1)

    def test_invalid_counter_value_is_not_rendered(self):
        self.counter.count = "<script>alert(1)</script>"

        status, _, body = self.request("/")

        self.assertEqual(status, 200)
        self.assertIn("Counter temporarily unavailable".encode(), body)
        self.assertNotIn(b"<script>alert(1)</script>", body)


class SettingsTests(unittest.TestCase):
    def test_reads_environment_configuration(self):
        with patch.dict(
            os.environ,
            {
                "HOST": "127.0.0.1",
                "PORT": "9000",
                "AWS_REGION": "eu-west-1",
                "COUNTER_FUNCTION": "web-counter",
            },
            clear=True,
        ):
            settings = Settings.from_environment()

        self.assertEqual(settings.host, "127.0.0.1")
        self.assertEqual(settings.port, 9000)
        self.assertEqual(settings.aws_region, "eu-west-1")
        self.assertEqual(settings.counter_function, "web-counter")

    def test_rejects_invalid_port_and_missing_function(self):
        with patch.dict(
            os.environ,
            {"PORT": "not-a-port", "COUNTER_FUNCTION": "web-counter"},
            clear=True,
        ):
            with self.assertRaisesRegex(ValueError, "PORT"):
                Settings.from_environment()

        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "COUNTER_FUNCTION"):
                Settings.from_environment()


if __name__ == "__main__":
    unittest.main()
