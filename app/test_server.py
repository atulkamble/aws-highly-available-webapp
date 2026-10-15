import http.client
import io
import json
import os
import threading
import unittest
from unittest.mock import patch

from server import (
    ApplicationServer,
    Handler,
    InstanceMetadata,
    RuntimeState,
    Settings,
    load_instance_metadata,
)


class FakeCounterClient:
    def __init__(self):
        self.calls = 0
        self.count = 0
        self.error = None

    def invoke(self, **_kwargs):
        self.calls += 1
        if self.error:
            raise self.error
        self.count += 1
        return {"Payload": io.BytesIO(json.dumps({"count": self.count}).encode())}


class HandlerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.metadata = InstanceMetadata(
            instance_id="i-0123456789abcdef0",
            availability_zone="us-east-1a",
            region="us-east-1",
        )
        cls.state = RuntimeState(
            Settings("127.0.0.1", 0, "us-east-1", "test-build", "test-counter"),
            cls.metadata,
        )
        cls.counter = FakeCounterClient()
        Handler.runtime_state = cls.state
        Handler.counter_client = cls.counter
        cls.server = ApplicationServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.port = cls.server.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)
        Handler.runtime_state = None
        Handler.counter_client = None

    def setUp(self):
        with self.state.lock:
            self.state.page_requests = 0
        self.counter.calls = 0
        self.counter.count = 0
        self.counter.error = None

    def request(self, path, method="GET"):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=2)
        connection.request(method, path)
        response = connection.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        connection.close()
        return result

    def test_homepage_serves_dashboard_and_sets_security_headers(self):
        status, headers, body = self.request("/")

        self.assertEqual(status, 200)
        self.assertEqual(self.state.snapshot()["page_requests"], 1)
        self.assertEqual(self.counter.calls, 1)
        self.assertIn(b"Serving instance", body)
        self.assertIn(b"Total page visits", body)
        self.assertIn(b'class="background-video"', body)
        self.assertIn(b"https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4", body)
        self.assertIn(b">1</div>", body)
        self.assertIn(b"/dashboard.js", body)
        self.assertEqual(headers["Content-Type"], "text/html; charset=utf-8")
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(headers["X-Frame-Options"], "DENY")
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertIn("script-src 'self'", headers["Content-Security-Policy"])
        self.assertIn(
            "media-src https://interactive-examples.mdn.mozilla.net",
            headers["Content-Security-Policy"],
        )
        self.assertTrue(headers["X-Request-ID"])

    def test_status_endpoint_returns_instance_telemetry(self):
        status, headers, body = self.request("/api/status")

        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "application/json; charset=utf-8")
        payload = json.loads(body)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["instance_id"], "i-0123456789abcdef0")
        self.assertEqual(payload["availability_zone"], "us-east-1a")
        self.assertEqual(payload["region"], "us-east-1")
        self.assertEqual(payload["app_version"], "test-build")
        self.assertGreaterEqual(payload["uptime_seconds"], 0)
        self.assertEqual(payload["page_requests"], 0)

    def test_dashboard_assets_are_served(self):
        css_status, css_headers, css_body = self.request("/dashboard.css")
        js_status, js_headers, js_body = self.request("/dashboard.js")

        self.assertEqual(css_status, 200)
        self.assertEqual(css_headers["Content-Type"], "text/css; charset=utf-8")
        self.assertIn(b".node-card", css_body)
        self.assertEqual(js_status, 200)
        self.assertEqual(js_headers["Content-Type"], "text/javascript; charset=utf-8")
        self.assertIn(b"/api/status", js_body)

    def test_query_string_homepage_counts_once(self):
        status, _, _ = self.request("/?source=test")

        self.assertEqual(status, 200)
        self.assertEqual(self.state.snapshot()["page_requests"], 1)
        self.assertEqual(self.counter.calls, 1)

    def test_status_poll_does_not_increment_global_counter(self):
        self.counter.count = 9
        status, _, body = self.request("/api/status")

        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["page_requests"], 0)
        self.assertEqual(self.counter.calls, 0)

    def test_counter_failure_keeps_dashboard_available_and_shows_message(self):
        self.counter.error = TimeoutError("simulated timeout")

        status, _, body = self.request("/")

        self.assertEqual(status, 200)
        self.assertIn("Counter temporarily unavailable".encode(), body)
        self.assertIn(">—</div>".encode(), body)
        self.assertEqual(self.counter.calls, 1)

    def test_health_endpoints_do_not_increment_page_count(self):
        live_status, _, live_body = self.request("/health")
        ready_status, _, ready_body = self.request("/health/ready")

        self.assertEqual(live_status, 200)
        self.assertEqual(json.loads(live_body), {"status": "ok"})
        self.assertEqual(ready_status, 200)
        self.assertEqual(json.loads(ready_body), {"status": "ok"})
        self.assertEqual(self.state.snapshot()["page_requests"], 0)

    def test_favicon_and_unknown_paths_do_not_increment_page_count(self):
        favicon_status, _, _ = self.request("/favicon.ico")
        missing_status, _, _ = self.request("/does-not-exist")

        self.assertEqual(favicon_status, 204)
        self.assertEqual(missing_status, 404)
        self.assertEqual(self.state.snapshot()["page_requests"], 0)

    def test_head_does_not_increment_page_count(self):
        status, headers, _ = self.request("/", method="HEAD")

        self.assertEqual(status, 405)
        self.assertEqual(headers["Allow"], "GET")
        self.assertEqual(self.state.snapshot()["page_requests"], 0)


class SettingsTests(unittest.TestCase):
    def test_reads_environment_configuration(self):
        with patch.dict(
            os.environ,
            {
                "PORT": "8090",
                "AWS_REGION": "eu-west-1",
                "APP_VERSION": "test",
                "COUNTER_FUNCTION": "visit-counter",
            },
            clear=True,
        ):
            settings = Settings.from_environment()

        self.assertEqual(settings.host, "0.0.0.0")
        self.assertEqual(settings.port, 8090)
        self.assertEqual(settings.region, "eu-west-1")
        self.assertEqual(settings.app_version, "test")
        self.assertEqual(settings.counter_function, "visit-counter")

    def test_rejects_invalid_port(self):
        with patch.dict(os.environ, {"PORT": "not-a-port"}, clear=True):
            with self.assertRaisesRegex(ValueError, "PORT"):
                Settings.from_environment()

    def test_reports_local_metadata_outside_ec2(self):
        from urllib.error import URLError

        with patch("server.urlopen", side_effect=URLError("metadata service unavailable")):
            metadata = load_instance_metadata(timeout=0.01)

        self.assertEqual(metadata, InstanceMetadata())


if __name__ == "__main__":
    unittest.main()
