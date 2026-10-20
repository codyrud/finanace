# Option Pricer

A vanilla European option pricer (call/put) using the Black-Scholes-Merton
model. The pricing math and the web server are both implemented from
scratch — zero third-party dependencies, standard library only
(`http.server`, `dataclasses`, `math`, `json`).

## Run the Streamlit app

To host this in Streamlit without starting the standalone HTTP server on port
8000, use:

```
streamlit run option-pricer/streamlit_app.py
```

## Run the standalone local server

```
python option-pricer/run.py
```

Then open http://127.0.0.1:8000 in a browser.

## Test it

```
python -m unittest discover -s option-pricer/tests -v
```

## Using it

The form updates live as you change any input (spot, strike, days to
maturity, the rate/volatility sliders, or the Call/Put choice) — no submit
button. Switching the Greek Type selector just redraws the chart from
already-fetched data; it doesn't re-query the server. The chart sweeps
spot ±30% around the entered value and plots the theoretical price against
the selected Greek. Save Image exports the chart as a PNG; Download CSV
exports the full swept curve (spot, price, and all five Greeks per point).

Dividend yield isn't exposed in this UI (the mockup this was built against
doesn't show it); every request sends the server's default of 0. The API
still accepts `dividend_yield` directly if you need it.

## Reference values

For S=100, K=105, T=0.5 years, r=5%, σ=20%:

- Call price ≈ 4.58
- Put price ≈ 6.99 (consistent with put-call parity)

Greeks scaling: delta and gamma are raw per-unit values; theta is per
calendar day; vega and rho are per 1 percentage-point move.

## Non-goals

This prices vanilla European options only. It does not support American
exercise, or other models (binomial, Heston, SABR, Monte Carlo, implied
volatility).
