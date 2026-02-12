import http.server
import socketserver
from pathlib import Path

class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            readme = Path('README.md').read_text(encoding='utf-8')
            html = f'<!DOCTYPE html><html><head><meta charset="utf-8"><title>Mukul Prasad</title></head><body><pre>{readme}</pre></body></html>'
            self.wfile.write(html.encode())
        else:
            super().do_GET()

for port in range(3000, 9000):
    try:
        with socketserver.TCPServer(("", port), Handler) as httpd:
            print(f"Server running at http://localhost:{port}")
            httpd.serve_forever()
        break
    except OSError:
        continue
