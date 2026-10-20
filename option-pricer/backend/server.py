import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from backend.api import handle_price_request

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


class PricingRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(FRONTEND_DIR), **kwargs)

    def do_POST(self):
        if self.path != "/api/price":
            self.send_error(404)
            return

        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            self._write_json({"error": "invalid Content-Length"}, 400)
            return
        if length < 0:
            self._write_json({"error": "invalid Content-Length"}, 400)
            return

        raw_body = self.rfile.read(length)
        try:
            payload = json.loads(raw_body)
        except (ValueError, RecursionError):
            body, status = {"error": "invalid JSON"}, 400
        else:
            body, status = handle_price_request(payload)

        self._write_json(body, status)

    def _write_json(self, body: dict, status: int) -> None:
        data = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format, *args):
        pass


def main(host: str = "127.0.0.1", port: int = 8000) -> None:
    server = ThreadingHTTPServer((host, port), PricingRequestHandler)
    print(f"Serving on http://{host}:{port}")
    server.serve_forever()
