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
        # Pinned to the call reference value (4.58) so a normalization bug that
        # silently priced this as a put (~6.99) would be caught, not just a
        # generic "it returned 200".
        self.assertAlmostEqual(body["price"], 4.58, delta=0.01)

    def test_normalizes_put_case_and_whitespace(self):
        payload = {**VALID_PAYLOAD, "option_type": " PUT "}
        body, status = handle_price_request(payload)
        self.assertEqual(status, 200)
        self.assertAlmostEqual(body["price"], 6.99, delta=0.01)

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

    def test_non_numeric_value_returns_422(self):
        payload = {**VALID_PAYLOAD, "volatility": "abc"}
        body, status = handle_price_request(payload)
        self.assertEqual(status, 422)
        self.assertIn("error", body)

    def test_extreme_valid_inputs_return_422_not_crash(self):
        # rate=-1, T=1000 overflows math.exp(-rate*T) inside price()/greeks(),
        # well after OptionInputs construction succeeds.
        payload = {**VALID_PAYLOAD, "rate": -1.0, "time_to_expiry": 1000.0}
        body, status = handle_price_request(payload)
        self.assertEqual(status, 422)
        self.assertIn("error", body)
