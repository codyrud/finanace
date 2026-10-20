# Option Pricer Web App — Design

## Intent

A small web application that prices vanilla European call and put options
and shows their Greeks, built as a playground project in
`C:\Rud\PG\Playground\option-pricer`. The user asked to use the
"vanilla option quant library" referenced at quantt.co.uk/resources; that
page turned out to be an educational article index, not a downloadable
library — its Black-Scholes explainer page has reference Python code and
a worked example, but no installable package. The user then confirmed
they want the pricing math implemented from scratch rather than depending
on a third-party options-pricing package, partly to avoid license/IP
exposure from reusing someone else's code.

## Goals

- Price vanilla European call and put options via the Black-Scholes-Merton
  closed-form model.
- Report the standard Greeks: delta, gamma, theta, vega, rho.
- Simple web UI: a form for inputs (option type, spot, strike, time to
  expiry, risk-free rate, volatility, optional dividend yield) submitted
  to a backend API, rendering price + Greeks.
- All pricing math implemented from scratch, from the published
  Black-Scholes-Merton formulas — no third-party options-pricing package
  (e.g. QuantLib, py_vollib), no code copied from quantt.co.uk or any
  other reference site.
- Correctness validated against a known reference value (S=100, K=105,
  T=0.5, r=0.05, σ=0.20 → call ≈ 4.58, per quantt.co.uk's worked example)
  and the put-call parity identity.

## Non-goals

- American-style options, early exercise, or other exercise styles.
- Other pricing models (binomial tree, Heston, SABR, Monte Carlo,
  implied-volatility solver).
- Authentication, persistence/database, multi-user support.
- Production deployment/hosting concerns (this is a local playground app).

## Anti-goals

(Would make this a failure even if it technically "works".)

- Reproducing quantt.co.uk's (or any other site's) code or text verbatim.
- Depending on a dedicated third-party option-pricing library.
- Silent wrong numbers for edge-case inputs (e.g. zero time-to-expiry or
  zero volatility producing NaN or a crash) instead of a sensible result
  or a clear validation error.

## Constraints

- Pricing/Greeks module: pure Python, standard library only (`math.erf`
  for the normal CDF) — zero third-party dependencies for the math
  itself.
- Backend: Python standard library `http.server` only (`ThreadingHTTPServer`
  plus a `SimpleHTTPRequestHandler` subclass) serving both the JSON
  pricing API and the static frontend — no third-party web framework
  (e.g. no FastAPI/Flask), confirmed by the user. Frontend: static
  HTML/CSS/vanilla JS, no build step, no frontend framework.
- License hygiene: the application has zero third-party package
  dependencies, standard library only; no code copied from external
  articles.
- Python 3.14 and git are available locally and should be used.
- Greeks scaling convention: delta and gamma in raw per-unit terms; theta
  reported per calendar day; vega and rho reported per 1 percentage-point
  move (i.e. raw value × 0.01).

## How it's built (decided)

- A single Python process, using only the `http.server` standard-library
  module, serves both the JSON API and the static frontend — no
  separate frontend build/dev server, no third-party web framework.
- The pricing module is fully unit-testable in isolation from the web
  layer, developed test-first (TDD), since the formulas have known
  numeric test vectors and admit finite-difference cross-checks for the
  Greeks.
- Invalid inputs (non-positive spot/strike/time-to-expiry/volatility,
  unrecognized option type) are rejected with a clear validation error
  rather than silently computed. Negative interest rates and dividend
  yields are valid (real markets have seen negative rates) and must be
  accepted.

## Left to the builder

- Exact internal file/module layout within the constraints above.
- Exact request/response JSON shape for the pricing API.
- Frontend visual styling (kept simple and clean; no specific design
  system was requested).
