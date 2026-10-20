import math
from dataclasses import dataclass

_VALID_OPTION_TYPES = ("call", "put")


@dataclass(frozen=True)
class OptionInputs:
    option_type: str
    spot: float
    strike: float
    time_to_expiry: float
    rate: float
    volatility: float
    dividend_yield: float = 0.0

    def __post_init__(self):
        if self.option_type not in _VALID_OPTION_TYPES:
            raise ValueError(f"option_type must be 'call' or 'put', got {self.option_type!r}")
        for field_name in ("spot", "strike", "time_to_expiry", "rate", "volatility", "dividend_yield"):
            if not math.isfinite(getattr(self, field_name)):
                raise ValueError(f"{field_name} must be a finite number")
        if self.spot <= 0:
            raise ValueError("spot must be positive")
        if self.strike <= 0:
            raise ValueError("strike must be positive")
        if self.time_to_expiry <= 0:
            raise ValueError("time_to_expiry must be positive")
        if self.volatility <= 0:
            raise ValueError("volatility must be positive")


def norm_cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2 * math.pi)


def _d1_d2(inputs: OptionInputs) -> tuple[float, float]:
    s, k, t, r, sigma, q = (
        inputs.spot,
        inputs.strike,
        inputs.time_to_expiry,
        inputs.rate,
        inputs.volatility,
        inputs.dividend_yield,
    )
    d1 = (math.log(s / k) + (r - q + 0.5 * sigma * sigma) * t) / (sigma * math.sqrt(t))
    d2 = d1 - sigma * math.sqrt(t)
    return d1, d2


def price(inputs: OptionInputs) -> float:
    d1, d2 = _d1_d2(inputs)
    s, k, t, r, q = (
        inputs.spot,
        inputs.strike,
        inputs.time_to_expiry,
        inputs.rate,
        inputs.dividend_yield,
    )
    if inputs.option_type == "call":
        return s * math.exp(-q * t) * norm_cdf(d1) - k * math.exp(-r * t) * norm_cdf(d2)
    return k * math.exp(-r * t) * norm_cdf(-d2) - s * math.exp(-q * t) * norm_cdf(-d1)


@dataclass(frozen=True)
class Greeks:
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float


def greeks(inputs: OptionInputs) -> Greeks:
    d1, d2 = _d1_d2(inputs)
    s, k, t, r, sigma, q = (
        inputs.spot,
        inputs.strike,
        inputs.time_to_expiry,
        inputs.rate,
        inputs.volatility,
        inputs.dividend_yield,
    )
    discounted_pdf = math.exp(-q * t) * norm_pdf(d1)
    discounted_spot_pdf = s * discounted_pdf
    gamma = discounted_pdf / (s * sigma * math.sqrt(t))
    vega = discounted_spot_pdf * math.sqrt(t) * 0.01
    common_theta_term = -(discounted_spot_pdf * sigma) / (2 * math.sqrt(t))

    if inputs.option_type == "call":
        delta = math.exp(-q * t) * norm_cdf(d1)
        theta_annual = common_theta_term - r * k * math.exp(-r * t) * norm_cdf(d2) + q * s * math.exp(-q * t) * norm_cdf(d1)
        rho = k * t * math.exp(-r * t) * norm_cdf(d2) * 0.01
    else:
        delta = math.exp(-q * t) * (norm_cdf(d1) - 1)
        theta_annual = common_theta_term + r * k * math.exp(-r * t) * norm_cdf(-d2) - q * s * math.exp(-q * t) * norm_cdf(-d1)
        rho = -k * t * math.exp(-r * t) * norm_cdf(-d2) * 0.01

    return Greeks(delta=delta, gamma=gamma, theta=theta_annual / 365, vega=vega, rho=rho)
