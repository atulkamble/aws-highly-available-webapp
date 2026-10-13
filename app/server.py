import os, json, boto3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

lambda_client = boto3.client('lambda', region_name=os.environ.get('AWS_REGION','us-east-1'))
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if urlparse(self.path).path == '/health':
            self.send_response(200); self.end_headers(); self.wfile.write(b'ok'); return
        count = 'unavailable'
        try:
            response = lambda_client.invoke(FunctionName=os.environ['COUNTER_FUNCTION'], InvocationType='RequestResponse', Payload=b'{}')
            result = json.loads(response['Payload'].read())
            count = result.get('count', 'unavailable')
        except Exception as e:
            print('Visitor counter failed:', repr(e), flush=True)
        body = f'''<!doctype html><html><head><title>Cloudnautic AWS Capstone</title><meta name="viewport" content="width=device-width, initial-scale=1"></head><body style="font-family:sans-serif;max-width:700px;margin:70px auto"><h1>Highly Available AWS Web Application</h1><p>Running on EC2 behind an Application Load Balancer.</p><h2>Visitor count: {count}</h2><p>Powered by Lambda + DynamoDB.</p></body></html>'''.encode()
        self.send_response(200); self.send_header('Content-Type','text/html; charset=utf-8'); self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)
ThreadingHTTPServer(('0.0.0.0', 8080), Handler).serve_forever()
