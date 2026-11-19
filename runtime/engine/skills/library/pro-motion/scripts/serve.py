#!/usr/bin/env python3
# Local static server for a generated-video project + POST /save?name=file.mp4 writes renders into <project>/render.
# macOS / Linux twin of server.ps1. Usage: python3 serve.py "<project folder>" [port]
import http.server, os, sys, urllib.parse

root = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.getcwd()
port = int(sys.argv[2]) if len(sys.argv) > 2 else 8765
os.makedirs(os.path.join(root, 'render'), exist_ok=True)


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=root, **k)

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()

    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        if u.path != '/save':
            self.send_error(404)
            return
        name = os.path.basename(urllib.parse.parse_qs(u.query).get('name', ['render.mp4'])[0])
        out = os.path.join(root, 'render', name)
        with open(out, 'wb') as f:
            f.write(self.rfile.read(int(self.headers.get('Content-Length', 0))))
        print('saved', out, flush=True)
        self.send_response(200)
        self.send_header('Content-Length', '2')
        self.end_headers()
        self.wfile.write(b'ok')


print(f'listening on http://localhost:{port}/ (root: {root})', flush=True)
http.server.ThreadingHTTPServer(('localhost', port), Handler).serve_forever()
