import html
import json
import logging
import os
import signal
import sys
import threading
import time
import uuid
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

LOGGER = logging.getLogger("ha_dashboard")
METADATA_URL = "http://169.254.169.254/latest"


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    region: str
    app_version: str
    counter_function: str

    @classmethod
    def from_environment(cls):
        raw_port = os.environ.get("PORT", "8080")
        try:
            port = int(raw_port)
        except ValueError as exc:
            raise ValueError("PORT must be an integer between 1 and 65535") from exc
        if not 1 <= port <= 65535:
            raise ValueError("PORT must be an integer between 1 and 65535")

        return cls(
            host=os.environ.get("HOST", "0.0.0.0"),
            port=port,
            region=os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "local",
            app_version=os.environ.get("APP_VERSION", "development"),
            counter_function=os.environ.get("COUNTER_FUNCTION", "").strip(),
        )


@dataclass(frozen=True)
class InstanceMetadata:
    instance_id: str = "local"
    availability_zone: str = "local"
    region: str = "local"


class RuntimeState:
    def __init__(self, settings, metadata):
        self.settings = settings
        self.metadata = metadata
        self.started_at = time.monotonic()
        self.page_requests = 0
        self.lock = threading.Lock()

    def record_page_request(self):
        with self.lock:
            self.page_requests += 1

    def snapshot(self):
        with self.lock:
            page_requests = self.page_requests
        uptime_seconds = max(0, int(time.monotonic() - self.started_at))
        return {
            "status": "ok",
            "instance_id": self.metadata.instance_id,
            "availability_zone": self.metadata.availability_zone,
            "region": self.metadata.region,
            "app_version": self.settings.app_version,
            "uptime_seconds": uptime_seconds,
            "page_requests": page_requests,
        }


class JsonLogFormatter(logging.Formatter):
    def format(self, record):
        entry = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        event_data = getattr(record, "event_data", None)
        if event_data:
            entry.update(event_data)
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=True, default=str)


def configure_logging():
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonLogFormatter())
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)


def load_instance_metadata(timeout=1):
    token_request = Request(
        f"{METADATA_URL}/api/token",
        data=b"",
        headers={"X-aws-ec2-metadata-token-ttl-seconds": "60"},
        method="PUT",
    )
    try:
        with urlopen(token_request, timeout=timeout) as response:
            token = response.read().decode("utf-8")
        headers = {"X-aws-ec2-metadata-token": token}

        def read_metadata(path):
            request = Request(f"{METADATA_URL}/{path}", headers=headers)
            with urlopen(request, timeout=timeout) as response:
                return response.read().decode("utf-8").strip()

        return InstanceMetadata(
            instance_id=read_metadata("meta-data/instance-id"),
            availability_zone=read_metadata("meta-data/placement/availability-zone"),
            region=read_metadata("meta-data/placement/region"),
        )
    except (HTTPError, URLError, TimeoutError, OSError, UnicodeError) as exc:
        LOGGER.info(
            "instance_metadata_unavailable",
            extra={"event_data": {"error_type": type(exc).__name__}},
        )
        return InstanceMetadata()


PAGE_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#0b1020">
  <meta name="description" content="Live view of a highly available AWS application.">
  <link rel="stylesheet" href="/dashboard.css">
  <script src="/dashboard.js" defer></script>
  <title>Cloudnautic | Availability Dashboard</title>
</head>
<body>
  <video class="background-video" aria-hidden="true" tabindex="-1" muted loop playsinline preload="metadata">
    <source src="https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4" type="video/mp4">
  </video>
  <div class="video-overlay" aria-hidden="true"></div>
  <div class="shell">
    <header class="topbar">
      <a class="brand" href="/" aria-label="Cloudnautic availability dashboard">
        <span class="brand-mark" aria-hidden="true">C</span>
        <span class="brand-copy"><strong>cloudnautic</strong><span>AVAILABILITY LAB</span></span>
      </a>
      <span class="top-status"><span class="status-dot"></span><span id="app-status">Connecting</span></span>
    </header>

    <main>
      <section class="intro" aria-labelledby="page-title">
        <span class="eyebrow"><span class="status-dot"></span> Live infrastructure view</span>
        <h1 id="page-title">Built to stay<br><span>up and running.</span></h1>
        <p>See which EC2 instance is serving you, where it lives, and how the application recovers across Availability Zones.</p>
      </section>

      <section class="node-card" aria-labelledby="node-title">
        <div class="node-heading">
          <div>
            <span class="section-kicker">CURRENT RESPONSE</span>
            <h2 id="node-title">Serving instance</h2>
          </div>
          <span class="live-indicator"><span class="status-dot"></span> LIVE</span>
        </div>
        <div class="node-id" id="instance-id" aria-live="polite">Discovering instance…</div>
        <div class="node-grid">
          <div class="node-fact"><span>Availability zone</span><strong id="availability-zone">—</strong></div>
          <div class="node-fact"><span>AWS region</span><strong id="region">—</strong></div>
          <div class="node-fact"><span>Instance uptime</span><strong id="uptime">—</strong></div>
          <div class="node-fact"><span>Page requests served here</span><strong id="page-requests">—</strong></div>
        </div>
        <p class="node-footnote">Values describe the instance that answered the latest status check. Refresh to see load-balancer routing in action.</p>
      </section>

      <section class="counter-card" aria-labelledby="counter-title">
        <div>
          <span class="section-kicker">PERSISTENT GLOBAL COUNT</span>
          <h2 id="counter-title">Total page visits</h2>
          <p class="counter-note">{{counter_message}}</p>
        </div>
        <div class="counter-value" id="total-visits" aria-live="polite">{{total_visits}}</div>
        <span class="counter-source">Lambda + DynamoDB</span>
      </section>

      <div class="section-heading"><span>Resilience at a glance</span><span>Live app telemetry</span></div>
      <section class="services" aria-label="Application and AWS health">
        <article class="service"><span class="service-icon">01</span><span class="service-copy"><strong>Application</strong><span id="application-health">Checking</span></span></article>
        <article class="service"><span class="service-icon">02</span><span class="service-copy"><strong>Load balancer</strong><span>ALB health checks</span></span></article>
        <article class="service"><span class="service-icon">03</span><span class="service-copy"><strong>Auto Scaling</strong><span>Self-healing capacity</span></span></article>
        <article class="service"><span class="service-icon">04</span><span class="service-copy"><strong>Build version</strong><span id="app-version">—</span></span></article>
      </section>

      <section class="lab-note">
        <span class="lab-icon" aria-hidden="true">↗</span>
        <div><strong>Try the resilience demo</strong><p>Refresh this dashboard, then terminate one EC2 instance from the Auto Scaling group. The ALB should route to a healthy peer while Auto Scaling launches a replacement.</p></div>
      </section>
    </main>

    <footer><span>Cloudnautic AWS Capstone</span><span>One request. One responding instance. Multi-AZ resilience.</span></footer>
  </div>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    server_version = "AWS-HA-Dashboard"
    sys_version = ""
    runtime_state = None
    counter_client = None

    def handle_one_request(self):
        self.request_id = uuid.uuid4().hex
        self.response_status = 0
        self.request_started_at = time.perf_counter()
        super().handle_one_request()

    def send_response(self, code, message=None):
        self.response_status = code
        super().send_response(code, message)

    def end_headers(self):
        self.send_header("X-Request-ID", self.request_id)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; style-src 'self'; script-src 'self'; "
            "media-src https://interactive-examples.mdn.mozilla.net; "
            "base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
        )
        super().end_headers()

    def log_request(self, code="-", size="-"):
        LOGGER.info(
            "http_request",
            extra={
                "event_data": {
                    "request_id": self.request_id,
                    "method": self.command,
                    "path": urlparse(self.path).path,
                    "status": code,
                    "response_bytes": size,
                    "duration_ms": round((time.perf_counter() - self.request_started_at) * 1000, 2),
                }
            },
        )

    def log_message(self, format_string, *args):
        LOGGER.warning(
            "http_server_message",
            extra={
                "event_data": {
                    "request_id": self.request_id,
                    "message_template": format_string,
                    "argument_count": len(args),
                }
            },
        )

    def _send_bytes(self, status, body, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        request_path = urlparse(self.path).path
        if request_path in ("/health", "/health/ready"):
            self._send_json(200, {"status": "ok"})
            return
        if request_path == "/favicon.ico":
            self.send_response(204)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if request_path == "/":
            self.runtime_state.record_page_request()
            try:
                count = self._increment_visits()
                count_text = f"{count:,}"
                counter_message = "This total is shared across all application instances."
            except Exception as exc:
                LOGGER.warning(
                    "visitor_counter_unavailable",
                    extra={
                        "event_data": {
                            "request_id": self.request_id,
                            "error_type": type(exc).__name__,
                        }
                    },
                )
                count_text = "—"
                counter_message = "Counter temporarily unavailable. Check application logs."
            body = PAGE_TEMPLATE.replace(
                "{{total_visits}}", html.escape(count_text)
            ).replace("{{counter_message}}", html.escape(counter_message)).encode("utf-8")
            self._send_bytes(200, body, "text/html; charset=utf-8")
            return
        if request_path == "/dashboard.css":
            self._send_static_file("dashboard.css", "text/css; charset=utf-8")
            return
        if request_path == "/dashboard.js":
            self._send_static_file("dashboard.js", "text/javascript; charset=utf-8")
            return
        if request_path == "/api/status":
            self._send_json(200, self.runtime_state.snapshot())
            return
        self.send_error(404)

    def _increment_visits(self):
        state = self.runtime_state
        if self.counter_client is None or not state.settings.counter_function:
            raise RuntimeError("Visitor counter is not configured")

        response = self.counter_client.invoke(
            FunctionName=state.settings.counter_function,
            InvocationType="RequestResponse",
            Payload=b"{}",
        )
        if response.get("FunctionError"):
            raise RuntimeError("Visitor counter Lambda returned a function error")
        result = json.loads(response["Payload"].read())
        count = result.get("count")
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise ValueError("Visitor counter Lambda returned an invalid count")
        return count

    def do_HEAD(self):
        self.send_response(405)
        self.send_header("Allow", "GET")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _send_json(self, status, payload):
        self._send_bytes(status, json.dumps(payload).encode("utf-8"), "application/json; charset=utf-8")

    def _send_static_file(self, filename, content_type):
        try:
            with open(os.path.join(os.path.dirname(__file__), filename), "rb") as asset:
                body = asset.read()
        except OSError:
            LOGGER.exception(
                "dashboard_asset_unavailable",
                extra={"event_data": {"request_id": self.request_id, "asset": filename}},
            )
            self.send_error(500)
            return
        self._send_bytes(200, body, content_type)


class ApplicationServer(ThreadingHTTPServer):
    daemon_threads = False
    request_queue_size = 128


def stop_on_termination(signum, _frame):
    LOGGER.info("termination_signal_received", extra={"event_data": {"signal": signum}})
    raise KeyboardInterrupt


def main():
    configure_logging()
    try:
        settings = Settings.from_environment()
    except ValueError as exc:
        LOGGER.critical("invalid_configuration", extra={"event_data": {"error": str(exc)}})
        return 2

    metadata = load_instance_metadata()
    Handler.runtime_state = RuntimeState(settings, metadata)
    if settings.counter_function:
        from botocore.config import Config
        import boto3

        Handler.counter_client = boto3.client(
            "lambda",
            region_name=settings.region,
            config=Config(
                connect_timeout=2,
                read_timeout=15,
                retries={"total_max_attempts": 1},
                max_pool_connections=50,
                user_agent_extra="aws-ha-webapp/1.0",
            ),
        )
    else:
        Handler.counter_client = None
    server = ApplicationServer((settings.host, settings.port), Handler)
    LOGGER.info(
        "server_started",
        extra={
            "event_data": {
                "host": settings.host,
                "port": settings.port,
                "app_version": settings.app_version,
                "instance_id": metadata.instance_id,
                "availability_zone": metadata.availability_zone,
            }
        },
    )
    try:
        signal.signal(signal.SIGTERM, stop_on_termination)
        server.serve_forever()
    except KeyboardInterrupt:
        LOGGER.info("server_shutdown_requested")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
