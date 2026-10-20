import math
import unittest
from dataclasses import replace
from backend.pricing.black_scholes import OptionInputs, price, greeks

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

    def test_rejects_non_positive_strike(self):
        with self.assertRaises(ValueError):
            OptionInputs("call", spot=100.0, strike=0.0, time_to_expiry=0.5, rate=0.05, volatility=0.20)

    def test_rejects_non_positive_time_to_expiry(self):
        with self.assertRaises(ValueError):
            OptionInputs("call", spot=100.0, strike=105.0, time_to_expiry=0.0, rate=0.05, volatility=0.20)

    def test_rejects_negative_spot_strike_time_volatility(self):
        base = dict(spot=100.0, strike=105.0, time_to_expiry=0.5, rate=0.05, volatility=0.20)
        for field in ("spot", "strike", "time_to_expiry", "volatility"):
            with self.assertRaises(ValueError, msg=f"negative {field} should be rejected"):
                OptionInputs("call", **{**base, field: -1.0})

    def test_rejects_nan_and_infinite_numeric_fields(self):
        base = dict(spot=100.0, strike=105.0, time_to_expiry=0.5, rate=0.05, volatility=0.20, dividend_yield=0.0)
        for field in base:
            for bad in (math.nan, math.inf, -math.inf):
                kwargs = {**base, field: bad}
                with self.assertRaises(ValueError, msg=f"{field}={bad} should be rejected"):
                    OptionInputs("call", **kwargs)

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

    def test_put_call_parity_with_dividend_yield(self):
        call = OptionInputs("call", spot=100.0, strike=105.0, time_to_expiry=0.5, rate=0.05, volatility=0.20, dividend_yield=0.03)
        put = replace(call, option_type="put")
        lhs = price(call) - price(put)
        rhs = call.spot * math.exp(-call.dividend_yield * call.time_to_expiry) - call.strike * math.exp(-call.rate * call.time_to_expiry)
        self.assertAlmostEqual(lhs, rhs, places=6)

    def test_negative_rate_is_priced_and_finite(self):
        inputs = OptionInputs("call", spot=100.0, strike=105.0, time_to_expiry=0.5, rate=-0.01, volatility=0.20)
        result = price(inputs)
        self.assertTrue(math.isfinite(result))
        self.assertGreater(result, 0)

    def test_negative_dividend_yield_is_priced_and_finite(self):
        inputs = OptionInputs("call", spot=100.0, strike=105.0, time_to_expiry=0.5, rate=0.05, volatility=0.20, dividend_yield=-0.02)
        result = price(inputs)
        self.assertTrue(math.isfinite(result))
        self.assertGreater(result, 0)

    def test_dividend_yield_lowers_call_and_raises_put(self):
        # A dividend yield reduces the stock's forward value, so it must make
        # a call cheaper and a put more expensive, all else equal. This
        # catches a flipped e^(-qT) sign that an exact-value test might not.
        no_dividend_call = OptionInputs("call", spot=100.0, strike=105.0, time_to_expiry=0.5, rate=0.05, volatility=0.20, dividend_yield=0.0)
        with_dividend_call = replace(no_dividend_call, dividend_yield=0.03)
        self.assertLess(price(with_dividend_call), price(no_dividend_call))

        no_dividend_put = replace(no_dividend_call, option_type="put")
        with_dividend_put = replace(with_dividend_call, option_type="put")
        self.assertGreater(price(with_dividend_put), price(no_dividend_put))

class TestGreeks(unittest.TestCase):
    def setUp(self):
        self.call = OptionInputs("call", spot=100.0, strike=105.0, time_to_expiry=0.5, rate=0.05, volatility=0.20)
        self.put = replace(self.call, option_type="put")
        self.call_with_dividend = replace(self.call, dividend_yield=0.03)
        self.put_with_dividend = replace(self.put, dividend_yield=0.03)
        # Every Greek test runs across all four, so a dividend-yield sign/term
        # bug (invisible at q=0, where e^(-qT) == e^(+qT) == 1) can't hide.
        self.scenarios = (self.call, self.put, self.call_with_dividend, self.put_with_dividend)

    def test_delta_matches_finite_difference(self):
        h = 1e-4
        for inputs in self.scenarios:
            numerical = (price(replace(inputs, spot=inputs.spot + h)) - price(replace(inputs, spot=inputs.spot - h))) / (2 * h)
            self.assertTrue(math.isclose(greeks(inputs).delta, numerical, rel_tol=1e-3), f"{inputs}: {greeks(inputs).delta} != {numerical}")

    def test_gamma_matches_finite_difference(self):
        h = 1e-2
        for inputs in self.scenarios:
            up = price(replace(inputs, spot=inputs.spot + h))
            mid = price(inputs)
            down = price(replace(inputs, spot=inputs.spot - h))
            numerical = (up - 2 * mid + down) / (h ** 2)
            self.assertTrue(math.isclose(greeks(inputs).gamma, numerical, rel_tol=1e-3), f"{inputs}: {greeks(inputs).gamma} != {numerical}")

    def test_vega_matches_finite_difference_per_one_percent(self):
        h = 1e-4
        for inputs in self.scenarios:
            numerical = (price(replace(inputs, volatility=inputs.volatility + h)) - price(replace(inputs, volatility=inputs.volatility - h))) / (2 * h) * 0.01
            self.assertTrue(math.isclose(greeks(inputs).vega, numerical, rel_tol=1e-3), f"{inputs}: {greeks(inputs).vega} != {numerical}")

    def test_theta_matches_finite_difference_per_day(self):
        h = 1e-4
        for inputs in self.scenarios:
            numerical = -(price(replace(inputs, time_to_expiry=inputs.time_to_expiry + h)) - price(replace(inputs, time_to_expiry=inputs.time_to_expiry - h))) / (2 * h) / 365
            self.assertTrue(math.isclose(greeks(inputs).theta, numerical, rel_tol=1e-3), f"{inputs}: {greeks(inputs).theta} != {numerical}")

    def test_rho_matches_finite_difference_per_one_percent(self):
        h = 1e-4
        for inputs in self.scenarios:
            numerical = (price(replace(inputs, rate=inputs.rate + h)) - price(replace(inputs, rate=inputs.rate - h))) / (2 * h) * 0.01
            self.assertTrue(math.isclose(greeks(inputs).rho, numerical, rel_tol=1e-3), f"{inputs}: {greeks(inputs).rho} != {numerical}")
