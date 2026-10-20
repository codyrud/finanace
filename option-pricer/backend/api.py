from backend.pricing.black_scholes import OptionInputs, price, greeks

REQUIRED_FIELDS = ("option_type", "spot", "strike", "time_to_expiry", "rate", "volatility")


def handle_price_request(payload: dict) -> tuple[dict, int]:
    if not isinstance(payload, dict):
        return {"error": "request body must be a JSON object"}, 400

    missing = [field for field in REQUIRED_FIELDS if field not in payload]
    if missing:
        return {"error": f"missing field(s): {', '.join(missing)}"}, 422

    try:
        inputs = OptionInputs(
            option_type=str(payload["option_type"]).strip().lower(),
            spot=float(payload["spot"]),
            strike=float(payload["strike"]),
            time_to_expiry=float(payload["time_to_expiry"]),
            rate=float(payload["rate"]),
            volatility=float(payload["volatility"]),
            dividend_yield=float(payload.get("dividend_yield", 0.0)),
        )
        computed_price = price(inputs)
        g = greeks(inputs)
    except (ValueError, TypeError, ArithmeticError) as exc:
        return {"error": str(exc)}, 422
    return {
        "price": computed_price,
        "greeks": {
            "delta": g.delta,
            "gamma": g.gamma,
            "theta": g.theta,
            "vega": g.vega,
            "rho": g.rho,
        },
    }, 200
