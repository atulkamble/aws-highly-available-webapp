import os, json, html, boto3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

lambda_client = boto3.client('lambda', region_name=os.environ.get('AWS_REGION','us-east-1'))

PAGE_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#0b1020">
  <meta name="description" content="A highly available web application powered by AWS.">
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
      <span class="top-status"><span class="status-dot"></span> System operational</span>
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
        <div class="metric-note">Tracked in real time with <strong>Lambda + DynamoDB</strong></div>
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
    def do_GET(self):
        if urlparse(self.path).path == '/health':
            self.send_response(200)
            self.send_header('Content-Length', '2')
            self.end_headers()
            self.wfile.write(b'ok')
            return
        count = 'unavailable'
        try:
            response = lambda_client.invoke(FunctionName=os.environ['COUNTER_FUNCTION'], InvocationType='RequestResponse', Payload=b'{}')
            result = json.loads(response['Payload'].read())
            count = result.get('count', 'unavailable')
        except Exception as e:
            print('Visitor counter failed:', repr(e), flush=True)
        body = PAGE_TEMPLATE.replace('{{visitor_count}}', html.escape(str(count))).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)


ThreadingHTTPServer(('0.0.0.0', 8080), Handler).serve_forever()
