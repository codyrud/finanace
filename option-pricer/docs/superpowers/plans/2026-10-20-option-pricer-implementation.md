# Option Pricer Web App Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A local web app that prices vanilla European call/put options and their Greeks via Black-Scholes-Merton, implemented entirely from scratch on the Python standard library — no third-party packages anywhere in the shipped app.

**Architecture:** A pure-Python pricing module (`backend/pricing/black_scholes.py`) computes price and Greeks from `OptionInputs`. A pure function (`backend/api.py::handle_price_request`) validates a parsed JSON payload and calls the pricing module, returning a `(body, status)` tuple — no HTTP concepts leak into it, so it is directly unit-testable. A thin `http.server` adapter (`backend/server.py`) wires that function to a `POST /api/price` route and serves the static frontend from the same `ThreadingHTTPServer` process via `SimpleHTTPRequestHandler`. The frontend is a single static HTML page with vanilla JS calling `fetch('/api/price')`.

**Tech Stack:** Python 3.14, standard library only (`http.server`, `dataclasses`, `math`, `json`, `unittest`). No pip install step at all — zero third-party dependencies, including for tests.

**Spec:** `docs/superpowers/specs/2026-10-20-option-pricer-design.md`

## Global Constraints

- Pricing/Greeks math: pure Python, standard library only (`math.erf` for the normal CDF).
- Web layer: standard library `http.server` only — no FastAPI/Flask/any third-party web framework.
- Tests: standard library `unittest` only — no pytest or other third-party test framework.
- European vanilla options only (Black-Scholes-Merton); no American exercise, no other models.
- Greeks scaling: delta and gamma are raw per-unit; theta is per calendar day (raw annual theta ÷ 365); vega and rho are per 1 percentage-point move (raw value × 0.01).
- `option_type` is case/whitespace-normalized by the API layer to `"call"`/`"put"` before reaching the pricing module, which itself only accepts those two exact lowercase strings.
- `rate` and `dividend_yield` may be any real number (including negative); `spot`, `strike`, `time_to_expiry`, `volatility` must be strictly positive.
- No code is copied from quantt.co.uk or any other external source; formulas are implemented from the standard published Black-Scholes-Merton model.

## Review Focus

- Non-positive `spot`/`strike`/`time_to_expiry`/`volatility` (zero or negative) must raise a clear validation error (→ HTTP 422), never NaN, a crash, or a silently wrong price. Covered in Task 1 (pricing unit tests) and Task 3 (API tests).
- An unrecognized or oddly-cased `option_type` (`"CALL"`, `" call "`, `"straddle"`) must be normalized or rejected with 422, never silently priced as a call. Covered in Task 1 and Task 3.
- Negative `rate` or `dividend_yield` (real markets have had negative rates) must be accepted and priced, not rejected as invalid. Covered in Task 1 and Task 3.
- A malformed HTTP request (missing field, non-numeric value, invalid JSON body) must come back as a JSON error with 400/422, never a raw 500/traceback leaked to the client. Covered in Task 3 (API + server integration tests).
- Concurrent requests on the threaded server must not leak state between them (the handler path has no shared mutable state). Covered in Task 3's server integration test with concurrent requests carrying different inputs.

---

### Task 1: Pricing core — Black-Scholes price

**Files:**
- Create: `backend/__init__.py`
- Create: `backend/pricing/__init__.py`
- Create: `backend/pricing/black_scholes.py`
- Create: `tests/test_black_scholes.py`
- Create: `.gitignore`

**Interfaces:**
- Produces: `OptionInputs` (frozen dataclass: `option_type: str, spot: float, strike: float, time_to_expiry: float, rate: float, volatility: float, dividend_yield: float = 0.0`), raising `ValueError` from `__post_init__` for `option_type not in ("call", "put")`, or any of `spot, strike, time_to_expiry, volatility` `<= 0`.
- Produces: `norm_cdf(x: float) -> float`, `norm_pdf(x: float) -> float`.
- Produces: `price(inputs: OptionInputs) -> float`.

- [ ] **Step 1: Write failing tests for `OptionInputs` validation and `price()`**

```python
import math
import unittest
from backend.pricing.black_scholes import OptionInputs, price

class TestOptionInputsValidation(unittest.TestCase):
    def test_rejects_non_positive_spot(self):
        with self.assertRaises(ValueError):
            OptionInputs("call", spot=0.0, strike=105.0, time_to_expiry=0.5, rate=0.05, volatility=0.20)

    def test_rejects_non_positive_volatility(self):
        with self.assertRaises(ValueError):
            OptionInputs("call", spot=100.0, strike=105.0, time_to_expiry=0.5, rate=0.05, volatility=0.0)

    def test_rejects_unknown_option_type(self):
        with self.assertRaises(ValueError):
            OptionInputs("straddle", spot=100.0, strike=105.0, time_to_expiry=0.5, rate=0.05, volatility=0.20)

    def test_accepts_negative_rate_and_dividend_yield(self):
        inputs = OptionInputs("call", spot=100.0, strike=105.0, time_to_expiry=0.5, rate=-0.01, volatility=0.20, dividend_yield=-0.005)
        self.assertEqual(inputs.rate, -0.01)

class TestPrice(unittest.TestCase):
    def test_call_price_matches_reference_value(self):
        inputs = OptionInputs("call", spot=100.0, strike=105.0, time_to_expiry=0.5, rate=0.05, volatility=0.20)
        self.assertAlmostEqual(price(inputs), 4.58, delta=0.01)

    def test_put_price_matches_reference_value(self):
        inputs = OptionInputs("put", spot=100.0, strike=105.0, time_to_expiry=0.5, rate=0.05, volatility=0.20)
        self.assertAlmostEqual(price(inputs), 6.99, delta=0.01)

    def test_put_call_parity(self):
        call = OptionInputs("call", spot=100.0, strike=105.0, time_to_expiry=0.5, rate=0.05, volatility=0.20)
        put = OptionInputs("put", spot=100.0, strike=105.0, time_to_expiry=0.5, rate=0.05, volatility=0.20)
        lhs = price(call) - price(put)
        rhs = call.spot - call.strike * math.exp(-call.rate * call.time_to_expiry)
        self.assertAlmostEqual(lhs, rhs, places=6)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.test_black_scholes -v`
Expected: FAIL / ImportError (`black_scholes` module does not exist yet)

- [ ] **Step 3: Implement `black_scholes.py`**

Standard Black-Scholes-Merton closed form, with continuous dividend yield `q`:
`d1 = (ln(S/K) + (r - q + σ²/2)·T) / (σ√T)`, `d2 = d1 - σ√T`.
`call = S·e^(-qT)·N(d1) - K·e^(-rT)·N(d2)`; `put = K·e^(-rT)·N(-d2) - S·e^(-qT)·N(-d1)`.
Implement `norm_cdf` via `0.5 * (1 + math.erf(x / math.sqrt(2)))` and `norm_pdf` via the standard Gaussian density formula. `OptionInputs.__post_init__` performs the validation listed in Interfaces above. Create `backend/__init__.py` and `backend/pricing/__init__.py` as empty files. Create `.gitignore` with at least `__pycache__/` and `*.pyc`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests.test_black_scholes -v`
Expected: PASS (all tests in `TestOptionInputsValidation` and `TestPrice`)

- [ ] **Step 5: Commit**

```bash
git init
git add .gitignore backend/__init__.py backend/pricing/__init__.py backend/pricing/black_scholes.py tests/test_black_scholes.py docs/superpowers
git commit -m "feat: add Black-Scholes pricing core"
```

---

### Task 2: Greeks

**Files:**
- Modify: `backend/pricing/black_scholes.py`
- Modify: `tests/test_black_scholes.py`

**Interfaces:**
- Consumes: `OptionInputs`, `price(inputs: OptionInputs) -> float` from Task 1.
- Produces: `Greeks` (frozen dataclass: `delta: float, gamma: float, theta: float, vega: float, rho: float`).
- Produces: `greeks(inputs: OptionInputs) -> Greeks`.

- [ ] **Step 1: Write failing finite-difference tests for each Greek**

```python
from dataclasses import replace
from backend.pricing.black_scholes import OptionInputs, price, greeks

class TestGreeks(unittest.TestCase):
    def setUp(self):
        self.call = OptionInputs("call", spot=100.0, strike=105.0, time_to_expiry=0.5, rate=0.05, volatility=0.20)
        self.put = replace(self.call, option_type="put")

    def test_delta_matches_finite_difference(self):
        h = 1e-4
        for inputs in (self.call, self.put):
            numerical = (price(replace(inputs, spot=inputs.spot + h)) - price(replace(inputs, spot=inputs.spot - h))) / (2 * h)
            self.assertAlmostEqual(greeks(inputs).delta, numerical, places=3)

    def test_gamma_matches_finite_difference(self):
        h = 1e-2
        for inputs in (self.call, self.put):
            up = price(replace(inputs, spot=inputs.spot + h))
            mid = price(inputs)
            down = price(replace(inputs, spot=inputs.spot - h))
            numerical = (up - 2 * mid + down) / (h ** 2)
            self.assertAlmostEqual(greeks(inputs).gamma, numerical, places=2)

    def test_vega_matches_finite_difference_per_one_percent(self):
        h = 1e-4
        for inputs in (self.call, self.put):
            numerical = (price(replace(inputs, volatility=inputs.volatility + h)) - price(replace(inputs, volatility=inputs.volatility - h))) / (2 * h) * 0.01
            self.assertAlmostEqual(greeks(inputs).vega, numerical, places=3)

    def test_theta_matches_finite_difference_per_day(self):
        h = 1e-4
        for inputs in (self.call, self.put):
            numerical = -(price(replace(inputs, time_to_expiry=inputs.time_to_expiry + h)) - price(replace(inputs, time_to_expiry=inputs.time_to_expiry - h))) / (2 * h) / 365
            self.assertAlmostEqual(greeks(inputs).theta, numerical, places=3)

    def test_rho_matches_finite_difference_per_one_percent(self):
        h = 1e-4
        for inputs in (self.call, self.put):
            numerical = (price(replace(inputs, rate=inputs.rate + h)) - price(replace(inputs, rate=inputs.rate - h))) / (2 * h) * 0.01
            self.assertAlmostEqual(greeks(inputs).rho, numerical, places=3)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.test_black_scholes -v`
Expected: FAIL / `AttributeError` or `ImportError` (`greeks` not defined yet)

- [ ] **Step 3: Implement `greeks()` in `black_scholes.py`**

Closed-form Black-Scholes-Merton Greeks (continuous dividend yield `q`, `φ` = `norm_pdf`, `N` = `norm_cdf`):
`delta_call = e^(-qT)·N(d1)`; `delta_put = e^(-qT)·(N(d1) - 1)`.
`gamma = e^(-qT)·φ(d1) / (S·σ·√T)` (same for call/put).
`vega_raw = S·e^(-qT)·φ(d1)·√T`; report `vega = vega_raw * 0.01`.
`theta_call_annual = -(S·e^(-qT)·φ(d1)·σ)/(2√T) - r·K·e^(-rT)·N(d2) + q·S·e^(-qT)·N(d1)`; `theta_put_annual = -(S·e^(-qT)·φ(d1)·σ)/(2√T) + r·K·e^(-rT)·N(-d2) - q·S·e^(-qT)·N(-d1)`; report `theta = theta_annual / 365`.
`rho_call_raw = K·T·e^(-rT)·N(d2)`; `rho_put_raw = -K·T·e^(-rT)·N(-d2)`; report `rho = rho_raw * 0.01`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests.test_black_scholes -v`
Expected: PASS (all tests, including `TestGreeks`)

- [ ] **Step 5: Commit**

```bash
git add backend/pricing/black_scholes.py tests/test_black_scholes.py
git commit -m "feat: add Black-Scholes Greeks"
```

---

### Task 3: Request handling + http.server API

**Files:**
- Create: `backend/api.py`
- Create: `backend/server.py`
- Create: `tests/test_api.py`
- Create: `tests/test_server.py`
- Create: `run.py`

**Interfaces:**
- Consumes: `OptionInputs`, `price`, `greeks`, `Greeks` from `backend/pricing/black_scholes.py` (Tasks 1–2).
- Produces: `handle_price_request(payload: dict) -> tuple[dict, int]` in `backend/api.py`.
- Produces: `PricingRequestHandler` (subclass of `http.server.SimpleHTTPRequestHandler`) and `main(host: str = "127.0.0.1", port: int = 8000) -> None` in `backend/server.py`.

- [ ] **Step 1: Write failing tests for `handle_price_request`**

```python
# tests/test_api.py
import unittest
from backend.api import handle_price_request

VALID_PAYLOAD = {"option_type": "call", "spot": 100.0, "strike": 105.0, "time_to_expiry": 0.5, "rate": 0.05, "volatility": 0.20}

class TestHandlePriceRequest(unittest.TestCase):
    def test_valid_payload_returns_price_and_greeks(self):
        body, status = handle_price_request(VALID_PAYLOAD)
        self.assertEqual(status, 200)
        self.assertAlmostEqual(body["price"], 4.58, delta=0.01)
        self.assertEqual(set(body["greeks"]), {"delta", "gamma", "theta", "vega", "rho"})

    def test_normalizes_option_type_case_and_whitespace(self):
        payload = {**VALID_PAYLOAD, "option_type": " CALL "}
        body, status = handle_price_request(payload)
        self.assertEqual(status, 200)

    def test_missing_field_returns_422(self):
        payload = {k: v for k, v in VALID_PAYLOAD.items() if k != "strike"}
        body, status = handle_price_request(payload)
        self.assertEqual(status, 422)
        self.assertIn("error", body)

    def test_non_positive_volatility_returns_422(self):
        payload = {**VALID_PAYLOAD, "volatility": 0}
        _, status = handle_price_request(payload)
        self.assertEqual(status, 422)

    def test_invalid_option_type_returns_422(self):
        payload = {**VALID_PAYLOAD, "option_type": "straddle"}
        _, status = handle_price_request(payload)
        self.assertEqual(status, 422)

    def test_negative_rate_is_accepted(self):
        payload = {**VALID_PAYLOAD, "rate": -0.01}
        _, status = handle_price_request(payload)
        self.assertEqual(status, 200)

    def test_non_dict_payload_returns_400(self):
        _, status = handle_price_request(["not", "a", "dict"])
        self.assertEqual(status, 400)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.test_api -v`
Expected: FAIL / ImportError (`backend.api` does not exist yet)

- [ ] **Step 3: Implement `handle_price_request` in `backend/api.py`**

Required fields: `option_type, spot, strike, time_to_expiry, rate, volatility` (`dividend_yield` optional, default `0.0`). Reject non-dict input with `400`. Reject missing required fields with `422` and an `{"error": "..."}` body listing the missing field name(s). Normalize `option_type` via `str(value).strip().lower()` before constructing `OptionInputs`. Catch `ValueError`/`TypeError` raised while coercing fields to `float` or from `OptionInputs.__post_init__` and return `422` with `{"error": str(exc)}`. On success return `({"price": ..., "greeks": {"delta": ..., "gamma": ..., "theta": ..., "vega": ..., "rho": ...}}, 200)`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests.test_api -v`
Expected: PASS

- [ ] **Step 5: Write failing integration test for the real `http.server` wiring**

```python
# tests/test_server.py
import json
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
```

- [ ] **Step 6: Run integration test to verify it fails**

Run: `python -m unittest tests.test_server -v`
Expected: FAIL / ImportError (`backend.server` does not exist yet)

- [ ] **Step 7: Implement `backend/server.py` and `run.py`**

`PricingRequestHandler(SimpleHTTPRequestHandler)` constructed with `directory=<project_root>/frontend` (via `functools.partial` or an overridden `__init__`) so `GET` serves static files from `frontend/` unmodified. Override `do_POST`: if `self.path != "/api/price"`, call `self.send_error(404)`; otherwise read `Content-Length` bytes from `self.rfile`, `json.loads` them (catching `json.JSONDecodeError` → `400` `{"error": "invalid JSON"}`), call `handle_price_request`, and write the `(body, status)` back as JSON with `Content-Type: application/json`. Override `log_message` to no-op (quiet test output). `main(host="127.0.0.1", port=8000)` constructs a `ThreadingHTTPServer` and calls `serve_forever()`. `run.py` at the project root imports and calls `backend.server.main()` under `if __name__ == "__main__":`.

- [ ] **Step 8: Run tests to verify they pass**

Run: `python -m unittest discover -s tests -v`
Expected: PASS (all tests across `test_black_scholes.py`, `test_api.py`, `test_server.py`)

- [ ] **Step 9: Commit**

```bash
git add backend/api.py backend/server.py tests/test_api.py tests/test_server.py run.py
git commit -m "feat: add http.server API layer for option pricing"
```

---

### Task 4: Frontend, README, and manual verification

**Files:**
- Create: `frontend/index.html`
- Create: `frontend/styles.css`
- Create: `frontend/app.js`
- Create: `README.md`

**Interfaces:**
- Consumes: `POST /api/price` (Task 3) — request JSON `{option_type, spot, strike, time_to_expiry, rate, volatility, dividend_yield?}`, response JSON `{price, greeks: {delta, gamma, theta, vega, rho}}` on 200, `{error}` on 4xx.

- [ ] **Step 1: Build `frontend/index.html`**

A form with inputs for option type (select: call/put), spot, strike, time to expiry (years), rate, volatility, and optional dividend yield; a submit button; a results area (price + a row per Greek) hidden until a successful response; an error message area. Links `styles.css` and `app.js`.

- [ ] **Step 2: Build `frontend/app.js`**

On form submit: prevent default, build the JSON payload from form fields (coercing numeric fields with `Number(...)`), `fetch('/api/price', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)})`. On a non-ok response, parse the `{error}` body and show it in the error area. On success, parse `{price, greeks}` and render them into the results area.

- [ ] **Step 3: Build `frontend/styles.css`**

Simple, clean layout: centered form card, labeled inputs, a visually distinct results panel. No framework, no external font/CDN dependency (system font stack only, to keep the zero-dependency property — no network calls besides the app's own API).

- [ ] **Step 4: Write `README.md`**

Document: what this is (vanilla European option pricer, Black-Scholes-Merton, self-implemented, zero third-party dependencies); how to run (`python run.py`, then open `http://127.0.0.1:8000`); how to test (`python -m unittest discover -s tests -v`); the known reference test vector; explicit non-goals (no American options, no other models) carried over from the spec.

- [ ] **Step 5: Manual verification in the browser**

Start the server in the background (`python run.py`), open `http://127.0.0.1:8000` in the browser pane, submit the reference test vector (S=100, K=105, T=0.5, r=0.05, σ=0.20, call), and confirm the displayed price is ≈4.58 with all five Greeks shown. Also submit an invalid input (e.g. volatility 0) and confirm the UI shows a clear error rather than breaking. Stop the server afterward.

- [ ] **Step 6: Commit**

```bash
git add frontend/index.html frontend/styles.css frontend/app.js README.md
git commit -m "feat: add option pricer frontend and README"
```
