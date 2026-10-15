import html
import json
import logging
import os
import signal
import sys
import time
import uuid
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

LOGGER = logging.getLogger("webapp")


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    aws_region: str
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

        counter_function = os.environ.get("COUNTER_FUNCTION", "").strip()
        if not counter_function:
            raise ValueError("COUNTER_FUNCTION must be set to the visitor counter Lambda name")

        return cls(
            host=os.environ.get("HOST", "0.0.0.0"),
            port=port,
            aws_region=os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-east-1",
            counter_function=counter_function,
        )


class JsonLogFormatter(logging.Formatter):
    def format(self, record):
        entry = {
            "timestamp": time.strftime(
                "%Y-%m-%dT%H:%M:%S%z", time.gmtime(record.created)
            ),
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


def create_counter_client(aws_region):
    import boto3
    from botocore.config import Config

    return boto3.client(
        "lambda",
        region_name=aws_region,
        config=Config(
            connect_timeout=2,
            read_timeout=15,
            # A timed-out increment may have reached Lambda; retrying could count it twice.
            retries={"total_max_attempts": 1},
            max_pool_connections=50,
            user_agent_extra="aws-ha-webapp/1.0",
        ),
    )

PAGE_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#0b1020">
  <meta name="description" content="A highly available web application powered by AWS.">
  <link rel="icon" href="data:,">
  <title>Cloudnautic | AWS Cloud</title>
  <style>
    :root {
      color-scheme: dark;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #0b1020;
      color: #f4f6fc;
      font-synthesis: none;
      text-rendering: optimizeLegibility;
      -webkit-font-smoothing: antialiased;
      --muted: #929bb2;
      --line: rgba(255, 255, 255, .1);
      --panel: rgba(20, 27, 48, .78);
      --cyan: #5eead4;
    }
    * { box-sizing: border-box; }
    body {
      min-width: 320px;
      min-height: 100vh;
      margin: 0;
      background:
        radial-gradient(ellipse at 50% 0%, rgba(93, 73, 190, .25), transparent 48%),
        radial-gradient(ellipse at 90% 50%, rgba(24, 159, 170, .08), transparent 32%),
        #0b1020;
    }
    a { color: inherit; }
    .shell { width: min(1080px, calc(100% - 48px)); margin-inline: auto; }
    .topbar {
      height: 76px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      border-bottom: 1px solid var(--line);
    }
    .brand { display: flex; align-items: center; gap: 12px; text-decoration: none; }
    .brand-mark {
      width: 38px; height: 38px; display: grid; place-items: center;
      border: 1px solid rgba(94, 234, 212, .3); border-radius: 12px;
      background: rgba(94, 234, 212, .09); color: var(--cyan);
    }
    .brand-mark svg { width: 21px; height: 21px; }
    .brand-copy { display: grid; gap: 2px; }
    .brand-copy strong { font-size: 14px; letter-spacing: .01em; }
    .brand-copy span { color: var(--muted); font-size: 11px; }
    .top-status, .eyebrow {
      display: inline-flex; align-items: center; gap: 8px;
      color: #b9c2d5; font-size: 12px; letter-spacing: .06em; text-transform: uppercase;
    }
    .status-dot {
      width: 7px; height: 7px; border-radius: 50%;
      background: var(--cyan); box-shadow: 0 0 12px rgba(94, 234, 212, .8);
    }
    main { padding: 76px 0 72px; }
    .intro { max-width: 700px; margin: 0 auto 36px; text-align: center; }
    .eyebrow { color: var(--cyan); }
    h1 {
      margin: 18px 0 14px; font-size: clamp(38px, 7vw, 66px);
      line-height: 1.04; letter-spacing: -.055em; font-weight: 650;
    }
    h1 span {
      color: transparent; background: linear-gradient(100deg, #a5b4fc 8%, #67e8d2 92%);
      background-clip: text; -webkit-background-clip: text;
    }
    .intro p { max-width: 560px; margin: 0 auto; color: var(--muted); font-size: 16px; line-height: 1.7; }
    .metric-card {
      position: relative; overflow: hidden; max-width: 720px; margin: 0 auto;
      padding: 34px 40px 30px; text-align: center;
      border: 1px solid rgba(255, 255, 255, .13); border-radius: 22px;
      background: linear-gradient(145deg, rgba(29, 38, 65, .9), rgba(17, 23, 42, .88));
      box-shadow: 0 24px 90px rgba(0, 0, 0, .28), inset 0 1px rgba(255, 255, 255, .06);
    }
    .metric-card::before {
      position: absolute; top: -120px; left: 50%; width: 380px; height: 220px;
      border-radius: 50%; background: rgba(105, 94, 230, .16);
      filter: blur(70px); content: ""; transform: translateX(-50%); pointer-events: none;
    }
    .metric-label, .metric-value, .metric-note { position: relative; }
    .metric-label { color: #c3cada; font-size: 13px; font-weight: 550; letter-spacing: .04em; }
    .metric-value {
      margin: 12px 0 8px; font-variant-numeric: tabular-nums;
      font-size: clamp(58px, 11vw, 88px); font-weight: 650; line-height: 1;
      letter-spacing: -.065em;
    }
    .metric-note { color: var(--muted); font-size: 13px; }
    .metric-note strong { color: var(--cyan); font-weight: 550; }
    .refresh-link {
      display: inline-flex; align-items: center; gap: 7px; margin-top: 24px;
      padding: 10px 15px; border: 1px solid rgba(255, 255, 255, .14); border-radius: 10px;
      background: rgba(255, 255, 255, .04); color: #e9edf8; font-size: 13px;
      font-weight: 550; text-decoration: none; transition: background .18s, border-color .18s;
    }
    .refresh-link:hover { border-color: rgba(94, 234, 212, .4); background: rgba(94, 234, 212, .08); }
    .refresh-link:focus-visible { outline: 2px solid var(--cyan); outline-offset: 3px; }
    .refresh-link svg { width: 15px; height: 15px; }
    .section-heading {
      display: flex; align-items: center; justify-content: space-between;
      margin: 54px 0 16px; color: #cbd2e1; font-size: 13px; font-weight: 600;
    }
    .section-heading span:last-child { color: var(--muted); font-size: 12px; font-weight: 400; }
    .services { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
    .service {
      min-height: 92px; display: flex; align-items: center; gap: 13px;
      padding: 17px; border: 1px solid var(--line); border-radius: 14px;
      background: var(--panel); backdrop-filter: blur(12px);
    }
    .service-icon {
      width: 38px; height: 38px; flex: 0 0 38px; display: grid; place-items: center;
      border: 1px solid rgba(165, 180, 252, .14); border-radius: 11px;
      background: rgba(129, 140, 248, .09); color: #a5b4fc;
    }
    .service-icon svg { width: 19px; height: 19px; }
    .service-copy { display: grid; gap: 5px; }
    .service-copy strong { font-size: 13px; font-weight: 580; }
    .service-copy span { color: var(--muted); font-size: 11px; }
    footer {
      display: flex; justify-content: space-between; gap: 16px;
      padding: 22px 0 28px; border-top: 1px solid var(--line);
      color: #778198; font-size: 11px;
    }
    footer span:last-child { color: #9ba5ba; }
    @media (max-width: 700px) {
      .shell { width: min(100% - 32px, 540px); }
      main { padding: 58px 0 54px; }
      .services { grid-template-columns: repeat(2, 1fr); }
      .metric-card { padding: 30px 20px 26px; }
    }
    @media (max-width: 420px) {
      .topbar { height: 68px; }
      .top-status { font-size: 10px; }
      .services { grid-template-columns: 1fr; }
      .service { min-height: 78px; }
      footer { flex-direction: column; }
    }
    @media (prefers-reduced-motion: reduce) {
      *, *::before, *::after { scroll-behavior: auto !important; transition-duration: .01ms !important; }
    }
  </style>
</head>
<body>
  <div class="shell">
    <header class="topbar">
      <a class="brand" href="/" aria-label="Cloudnautic AWS Cloud home">
        <span class="brand-mark" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none"><path d="M4 16.5 8.5 8l3.5 6 2.5-4 5.5 9H4Z" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/><path d="M6 19h14" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg>
        </span>
        <span class="brand-copy"><strong>cloudnautic</strong><span>AWS CLOUD PROJECT</span></span>
      </a>
      <span class="top-status"><span class="status-dot"></span> Application online</span>
    </header>

    <main>
      <section class="intro" aria-labelledby="page-title">
        <span class="eyebrow"><span class="status-dot"></span> Built for availability</span>
        <h1 id="page-title">Cloud-native.<br><span>Always ready.</span></h1>
        <p>A resilient web experience running across multiple Availability Zones, with serverless data processing at its core.</p>
      </section>

      <section class="metric-card" aria-labelledby="visitor-heading">
        <div class="metric-label" id="visitor-heading">Total page visits</div>
        <div class="metric-value" aria-live="polite">{{visitor_count}}</div>
        <div class="metric-note">{{counter_message}}</div>
        <a class="refresh-link" href="/" aria-label="Refresh page and record another visit">
          <svg viewBox="0 0 20 20" fill="none" aria-hidden="true"><path d="M16.5 8A6.7 6.7 0 0 0 5 5.4L3.5 7M3.5 7V3.8M3.5 7h3.2M3.5 12A6.7 6.7 0 0 0 15 14.6l1.5-1.6m0 0v3.2m0-3.2h-3.2" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
          Refresh to count your visit
        </a>
      </section>

      <div class="section-heading"><span>Under the hood</span><span>Powered by AWS</span></div>
      <section class="services" aria-label="AWS services">
        <article class="service">
          <span class="service-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none"><rect x="4" y="4" width="16" height="6" rx="1.5" stroke="currentColor" stroke-width="1.6"/><rect x="4" y="14" width="16" height="6" rx="1.5" stroke="currentColor" stroke-width="1.6"/><path d="M7.5 7h.01M7.5 17h.01M11 7h6M11 17h6" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg></span>
          <span class="service-copy"><strong>Amazon EC2</strong><span>Scalable compute</span></span>
        </article>
        <article class="service">
          <span class="service-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none"><path d="M4 7h5m6 0h5M4 17h5m6 0h5M9 7l3 5 3-5m-6 10 3-5 3 5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/><circle cx="4" cy="7" r="1.5" fill="currentColor"/><circle cx="20" cy="7" r="1.5" fill="currentColor"/><circle cx="4" cy="17" r="1.5" fill="currentColor"/><circle cx="20" cy="17" r="1.5" fill="currentColor"/></svg></span>
          <span class="service-copy"><strong>Load Balancer</strong><span>Traffic distribution</span></span>
        </article>
        <article class="service">
          <span class="service-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none"><path d="M13.5 2.8 5.8 13h5l-.5 8.2 7.9-10.4h-5.1l.4-8Z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/></svg></span>
          <span class="service-copy"><strong>AWS Lambda</strong><span>Serverless compute</span></span>
        </article>
        <article class="service">
          <span class="service-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none"><ellipse cx="12" cy="5.5" rx="7.5" ry="3" stroke="currentColor" stroke-width="1.6"/><path d="M4.5 5.5v6c0 1.7 3.4 3 7.5 3s7.5-1.3 7.5-3v-6M4.5 11.5v6c0 1.7 3.4 3 7.5 3s7.5-1.3 7.5-3v-6" stroke="currentColor" stroke-width="1.6"/></svg></span>
          <span class="service-copy"><strong>Amazon DynamoDB</strong><span>Managed data store</span></span>
        </article>
      </section>
    </main>

    <footer><span>Cloudnautic AWS Capstone</span><span>High availability, designed in.</span></footer>
  </div>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    server_version = "AWS-HA-WebApp"
    sys_version = ""
    counter_client = None
    settings = None

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
            "default-src 'none'; style-src 'unsafe-inline'; img-src data:; "
            "base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
        )
        self.send_header("Cache-Control", "no-store")
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
                    "duration_ms": round(
                        (time.perf_counter() - self.request_started_at) * 1000, 2
                    ),
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

    def _send_json(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        request_path = urlparse(self.path).path
        if request_path == '/health':
            self._send_json(200, {"status": "ok"})
            return
        if request_path == '/health/ready':
            ready = self.counter_client is not None and self.settings is not None
            status = 200 if ready else 503
            self._send_json(status, {"status": "ready" if ready else "not_ready"})
            return
        if request_path == '/favicon.ico':
            self.send_response(204)
            self.send_header('Content-Length', '0')
            self.end_headers()
            return
        if request_path != '/':
            self.send_error(404)
            return

        count = None
        try:
            if self.counter_client is None or self.settings is None:
                raise RuntimeError("Counter client has not been initialized")
            response = self.counter_client.invoke(
                FunctionName=self.settings.counter_function,
                InvocationType="RequestResponse",
                Payload=b"{}",
            )
            if response.get("FunctionError"):
                raise RuntimeError("Counter Lambda returned a function error")
            result = json.loads(response["Payload"].read())
            count = result.get("count")
            if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                raise ValueError("Counter Lambda returned an invalid count")
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

        count_text = f"{count:,}" if count is not None else "—"
        counter_message = (
            "Tracked in real time with <strong>Lambda + DynamoDB</strong>"
            if count is not None
            else "Counter temporarily unavailable. Please try again shortly."
        )
        body = PAGE_TEMPLATE.replace(
            "{{visitor_count}}", html.escape(count_text)
        ).replace("{{counter_message}}", counter_message).encode("utf-8")
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_HEAD(self):
        self.send_response(405)
        self.send_header("Allow", "GET")
        self.send_header("Content-Length", "0")
        self.end_headers()


class ApplicationServer(ThreadingHTTPServer):
    daemon_threads = False
    request_queue_size = 128


def stop_on_termination(_signum, _frame):
    LOGGER.info(
        "termination_signal_received",
        extra={
            "event_data": {
                "signal": _signum,
                "handler": _frame.f_code.co_name if _frame is not None else None,
            }
        },
    )
    raise KeyboardInterrupt


def main():
    configure_logging()
    try:
        settings = Settings.from_environment()
    except ValueError as exc:
        LOGGER.critical("invalid_configuration", extra={"event_data": {"error": str(exc)}})
        return 2

    Handler.settings = settings
    Handler.counter_client = create_counter_client(settings.aws_region)
    server = ApplicationServer((settings.host, settings.port), Handler)
    LOGGER.info(
        "server_started",
        extra={
            "event_data": {
                "host": settings.host,
                "port": settings.port,
                "aws_region": settings.aws_region,
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
