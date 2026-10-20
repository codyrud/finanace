import json
import socket
import threading
import unittest
import urllib.request
import urllib.error
from http.server import ThreadingHTTPServer
from backend.server import PricingRequestHandler

class TestServerIntegration(unittest.TestCase):
    def setUp(self):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), PricingRequestHandler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def _post(self, payload):
        data = json.dumps(payload).encode()
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/api/price", data=data, headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req) as resp:
                return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def _raw_post(self, headers: str, body: bytes, timeout: float = 2.0) -> bytes:
        """Send a POST with hand-built headers, bypassing urllib's own
        correctness checks, so a malformed request can actually be sent."""
        with socket.create_connection(("127.0.0.1", self.port), timeout=timeout) as sock:
            request = f"POST /api/price HTTP/1.1\r\nHost: 127.0.0.1\r\n{headers}\r\n".encode() + body
            sock.sendall(request)
            sock.settimeout(timeout)
            chunks = []
            try:
                while True:
                    chunk = sock.recv(4096)
                    if not chunk:
                        break
                    chunks.append(chunk)
            except socket.timeout:
                pass
            return b"".join(chunks)

    def test_price_endpoint_end_to_end(self):
        status, body = self._post({"option_type": "call", "spot": 100.0, "strike": 105.0, "time_to_expiry": 0.5, "rate": 0.05, "volatility": 0.20})
        self.assertEqual(status, 200)
        self.assertAlmostEqual(body["price"], 4.58, delta=0.01)

    def test_invalid_payload_returns_422_not_500(self):
        status, body = self._post({"option_type": "call", "spot": 100.0})
        self.assertEqual(status, 422)
        self.assertIn("error", body)

    def test_concurrent_requests_do_not_leak_state(self):
        payloads = [
            {"option_type": "call", "spot": s, "strike": 105.0, "time_to_expiry": 0.5, "rate": 0.05, "volatility": 0.20}
            for s in (90.0, 100.0, 110.0, 120.0)
        ]
        results = [None] * len(payloads)

        def worker(i, payload):
            results[i] = self._post(payload)

        threads = [threading.Thread(target=worker, args=(i, p)) for i, p in enumerate(payloads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        expected_prices = [self._post(p)[1]["price"] for p in payloads]
        for (status, body), expected in zip(results, expected_prices):
            self.assertEqual(status, 200)
            self.assertAlmostEqual(body["price"], expected, places=6)

    def test_negative_content_length_returns_400_not_hang(self):
        response = self._raw_post("Content-Length: -1\r\n\r\n", b"")
        self.assertIn(b" 400 ", response)

    def test_non_integer_content_length_returns_400(self):
        response = self._raw_post("Content-Length: abc\r\n\r\n", b"")
        self.assertIn(b" 400 ", response)

    def test_invalid_utf8_body_returns_400(self):
        body = b"\xff\xfe\x00\x01"
        headers = f"Content-Type: application/json\r\nContent-Length: {len(body)}\r\n\r\n"
        response = self._raw_post(headers, body)
        self.assertIn(b" 400 ", response)

    def test_deeply_nested_json_returns_400(self):
        body = b"[" * 100_000
        headers = f"Content-Type: application/json\r\nContent-Length: {len(body)}\r\n\r\n"
        response = self._raw_post(headers, body)
        self.assertIn(b" 400 ", response)

    def test_malformed_json_syntax_returns_400(self):
        body = b"{not valid json}"
        headers = f"Content-Type: application/json\r\nContent-Length: {len(body)}\r\n\r\n"
        response = self._raw_post(headers, body)
        self.assertIn(b" 400 ", response)
