import sys

import streamlit as st

from backend.api import handle_price_request
from backend.server import main as start_backend_server


def render_app() -> None:
    st.set_page_config(page_title="Option Pricer", layout="wide")
    st.title("Option Pricer")

    with st.form("pricing_form"):
        c1, c2, c3 = st.columns(3)
        with c1:
            spot = st.number_input("Spot Price", min_value=0.01, value=100.0, step=0.01)
        with c2:
            strike = st.number_input("Strike Price", min_value=0.01, value=105.0, step=0.01)
        with c3:
            days_to_maturity = st.number_input("Days to Maturity", min_value=1, value=182, step=1)

        c4, c5 = st.columns(2)
        with c4:
            rate_pct = st.slider("Risk-Free Rate (%)", min_value=-5.0, max_value=20.0, value=5.0, step=0.1)
        with c5:
            vol_pct = st.slider("Volatility (%)", min_value=0.5, max_value=100.0, value=20.0, step=0.5)

        option_type = st.radio("Option Type", ["call", "put"], horizontal=True)
        submitted = st.form_submit_button("Price option")

    if submitted:
        payload = {
            "option_type": option_type,
            "spot": float(spot),
            "strike": float(strike),
            "time_to_expiry": float(days_to_maturity) / 365.0,
            "rate": float(rate_pct) / 100.0,
            "volatility": float(vol_pct) / 100.0,
        }
        body, status = handle_price_request(payload)

        if status != 200:
            st.error(body.get("error", "Unable to price this option."))
        else:
            st.subheader("Results")
            st.metric("Estimated price", f"{body['price']:.4f}")

            greek_cols = st.columns(5)
            for idx, key in enumerate(("delta", "gamma", "theta", "vega", "rho")):
                greek_cols[idx].metric(key.title(), f"{body['greeks'][key]:.4f}")


def main(host: str = "127.0.0.1", port: int = 8000) -> None:
    # Hosted on Streamlit: render the app instead of starting a second web server.
    if "streamlit" in sys.modules:
        render_app()
        return

    # Standalone local HTTP server mode.
    start_backend_server(host=host, port=port)


if __name__ == "__main__":
    main()
