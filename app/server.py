import html
import json
import logging
import os
import re
import signal
import sys
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
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
    registration_table: str = ""

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
            registration_table=os.environ.get("REGISTRATION_TABLE", "").strip(),
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
  <meta name="theme-color" content="#172337">
  <meta name="description" content="Register for the Flipkart Mobile Launch Event and midnight sale.">
  <link rel="stylesheet" href="/dashboard.css">
  <script src="/dashboard.js" defer></script>
  <title>Flipkart | Mobile Launch Event</title>
</head>
<body>
  <div class="shell">
    <header class="topbar">
      <a class="brand" href="/" aria-label="Flipkart Mobile Launch Event home">
        <span class="brand-mark" aria-hidden="true">F</span>
        <span class="brand-copy"><strong>Flipkart</strong><span>MOBILE LAUNCH EVENT</span></span>
      </a>
      <span class="top-status"><span class="status-dot"></span><span id="app-status">Event registration open</span></span>
    </header>

    <main>
      <section class="intro" aria-labelledby="page-title">
        <span class="eyebrow"><span class="status-dot"></span> YOU'RE INVITED</span>
        <h1 id="page-title">A new phone.<br><span>A midnight moment.</span></h1>
        <p>Be among the first to discover our latest mobile launch. Register now and get ready when the sale opens at 12:00 AM.</p>
      </section>

      <section class="event-card" aria-labelledby="event-title">
        <div class="event-copy">
          <span class="section-kicker">THE COUNTDOWN IS ON</span>
          <h2 id="event-title">Mobile Launch Event</h2>
          <p>Exclusive launch offers go live at midnight.</p>
          <div class="countdown" aria-label="Time until midnight sale starts">
            <div class="countdown-unit"><strong id="countdown-hours">00</strong><span>HOURS</span></div>
            <div class="countdown-separator" aria-hidden="true">:</div>
            <div class="countdown-unit"><strong id="countdown-minutes">00</strong><span>MINUTES</span></div>
            <div class="countdown-separator" aria-hidden="true">:</div>
            <div class="countdown-unit"><strong id="countdown-seconds">00</strong><span>SECONDS</span></div>
          </div>
          <span class="sale-time"><span aria-hidden="true">✦</span> SALE STARTS AT 12:00 AM LOCAL TIME</span>
        </div>
        <div class="phone-art" aria-hidden="true"><div class="phone-screen"><span>NEW</span><strong>the<br>future<br>in your<br>hands.</strong><i></i></div></div>
      </section>

      <section class="registration-card" aria-labelledby="registration-title">
        <div class="registration-heading">
          <span class="section-kicker">SAVE YOUR SPOT</span>
          <h2 id="registration-title">Register for the launch</h2>
          <p>Share your details to register for the Mobile Launch Event.</p>
        </div>
        <form id="registration-form">
          <label for="customer-name">Customer name</label>
          <input id="customer-name" name="name" type="text" autocomplete="name" maxlength="100" required>
          <label for="customer-address">Address</label>
          <textarea id="customer-address" name="address" autocomplete="street-address" maxlength="300" rows="3" required></textarea>
          <label for="customer-pincode">PIN code</label>
          <input id="customer-pincode" name="pincode" type="text" inputmode="numeric" autocomplete="postal-code" pattern="[0-9]{6}" maxlength="6" aria-describedby="pincode-hint" required>
          <span class="field-hint" id="pincode-hint">Enter your 6-digit Indian PIN code.</span>
          <button class="register-button" type="submit">Register for the event <span aria-hidden="true">→</span></button>
          <p class="form-message" id="registration-message" role="status" aria-live="polite"></p>
          <p class="privacy-note">Your details are used to record your event registration.</p>
        </form>
      </section>

      <details class="event-details">
        <summary>Event details</summary>
        <p>The sale opens at the next 12:00 AM in your device's local time. Registration details are stored securely for event administration.</p>
      </details>

      <section class="platform-status" aria-label="Application status">
        <span id="application-health">Application status: checking</span>
        <span>Served by <strong id="instance-id">—</strong></span>
        <span id="availability-zone">—</span>
        <span id="region">—</span>
        <span>Uptime <strong id="uptime">—</strong></span>
        <span>Requests <strong id="page-requests">—</strong></span>
        <span>Build <strong id="app-version">—</strong></span>
        <span>Total visits <strong id="total-visits">{{total_visits}}</strong></span>
        <span class="counter-note">{{counter_message}}</span>
      </section>
    </main>

    <footer><span>Flipkart Mobile Launch Event</span><span>Sale opens at 12:00 AM local time</span></footer>
  </div>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    server_version = "AWS-HA-Dashboard"
    sys_version = ""
    runtime_state = None
    counter_client = None
    registration_table = None
    MAX_REGISTRATION_BODY = 8192

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
            "base-uri 'none'; form-action 'self'; frame-ancestors 'none'",
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

    def do_POST(self):
        if urlparse(self.path).path != "/api/register":
            self.send_error(404)
            return
        if self.headers.get_content_type() != "application/json":
            self._send_json(415, {"error": "Content-Type must be application/json"})
            return
        try:
            content_length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            self._send_json(400, {"error": "A valid Content-Length is required"})
            return
        if content_length < 1:
            self._send_json(400, {"error": "Registration details are required"})
            return
        if content_length > self.MAX_REGISTRATION_BODY:
            self._send_json(413, {"error": "Registration details are too large"})
            return
        try:
            payload = json.loads(self.rfile.read(content_length))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._send_json(400, {"error": "Registration details must be valid JSON"})
            return
        if not isinstance(payload, dict):
            self._send_json(400, {"error": "Registration details must be an object"})
            return
        registration = self._validate_registration(payload)
        if registration is None:
            self._send_json(
                400,
                {"error": "Enter a name, address, and valid 6-digit PIN code"},
            )
            return
        if self.registration_table is None or not self.runtime_state.settings.registration_table:
            LOGGER.error("registration_storage_unavailable")
            self._send_json(503, {"error": "Registration is temporarily unavailable"})
            return
        try:
            self.registration_table.put_item(
                Item={
                    "registration_id": uuid.uuid4().hex,
                    **registration,
                    "registered_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                }
            )
        except Exception as exc:
            LOGGER.error(
                "event_registration_failed",
                extra={"event_data": {"error_type": type(exc).__name__}},
            )
            self._send_json(503, {"error": "Registration could not be saved. Please try again."})
            return
        LOGGER.info("event_registration_created")
        self._send_json(201, {"status": "registered", "message": "You're registered for the event."})

    @staticmethod
    def _validate_registration(payload):
        name = payload.get("name")
        address = payload.get("address")
        pincode = payload.get("pincode")
        if not all(isinstance(value, str) for value in (name, address, pincode)):
            return None
        name = name.strip()
        address = address.strip()
        pincode = pincode.strip()
        if (
            not name
            or len(name) > 100
            or not address
            or len(address) > 300
            or re.search(r"[\x00-\x08\x0b-\x1f\x7f]", name + address)
            or re.fullmatch(r"[0-9]{6}", pincode) is None
        ):
            return None
        return {"name": name, "address": address, "pincode": pincode}

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
    if settings.counter_function or settings.registration_table:
        from botocore.config import Config
        import boto3

        aws_config = Config(
            connect_timeout=2,
            read_timeout=15,
            retries={"total_max_attempts": 1},
            max_pool_connections=50,
            user_agent_extra="aws-ha-webapp/1.0",
        )
    else:
        aws_config = None
    if settings.counter_function:
        Handler.counter_client = boto3.client(
            "lambda",
            region_name=settings.region,
            config=aws_config,
        )
    else:
        Handler.counter_client = None
    if settings.registration_table:
        Handler.registration_table = boto3.resource(
            "dynamodb", region_name=settings.region, config=aws_config
        ).Table(settings.registration_table)
    else:
        Handler.registration_table = None
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
