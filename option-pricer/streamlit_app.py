import math

import altair as alt
import pandas as pd
import streamlit as st

from backend.api import handle_price_request


CSS = """
<style>
    .appview-container {
        background: #f2efe9;
    }
    .main .block-container {
        max-width: 1400px;
        padding-top: 1.5rem;
        padding-bottom: 2rem;
    }
    div[data-testid="stForm"] {
        border: 1px solid rgba(43, 53, 66, 0.25);
        background: #f5f3ee;
        border-radius: 14px;
        padding: 0.75rem 1rem 1rem 1rem;
        box-shadow: none;
    }
    .block-container .stNumberInput, .stSlider, .stRadio {
        margin-bottom: 0.2rem;
    }
    .stNumberInput label, .stSlider label, .stRadio label {
        font-size: 1.02rem;
        font-weight: 600;
        color: #2b2d3a;
        margin-bottom: 0.2rem;
    }
    .stNumberInput input, .stSlider [data-testid="stBaseWidget"] {
        background: #eef0f1;
        border: 1px solid rgba(30, 35, 40, 0.28);
        border-radius: 10px;
    }
    .stSlider > div {
        padding: 0.25rem 0.1rem 0.2rem 0.1rem;
    }
    .stSlider .stSliderLabel {
        color: #2b2d3a;
    }
    .stRadio > div {
        display: flex;
        gap: 0.7rem;
        align-items: center;
    }
    .stRadio [role="radiogroup"] {
        display: flex;
        flex-wrap: wrap;
        gap: 0.85rem;
    }
    .stRadio label {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        border: 1px solid rgba(30, 35, 40, 0.35);
        border-radius: 10px;
        padding: 0.4rem 0.8rem;
        background: #f2f1ee;
        min-width: 92px;
        justify-content: center;
    }
    .stRadio input {
        accent-color: #202b39;
        width: 1rem;
        height: 1rem;
    }
    .price-card {
        background: #f5f3ee;
        border: 1px solid rgba(43, 53, 66, 0.25);
        border-radius: 12px;
        padding: 1rem 1.25rem;
        margin-top: 1rem;
    }
    .price-card .price-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 0.9rem;
        font-weight: 700;
    }
    .price-card .price-row strong {
        font-size: 1.1rem;
        color: #1d2431;
    }
    .greek-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        font-size: 1.02rem;
        padding: 0.6rem 0;
        border-top: 1px solid rgba(43, 53, 66, 0.18);
    }
    .greek-row span:first-child {
        color: #2a2d35;
    }
    .greek-row span:last-child {
        font-variant-numeric: tabular-nums;
        color: #1d2431;
        font-weight: 500;
    }
    .chart-panel {
        border: 1px solid rgba(43, 53, 66, 0.25);
        border-radius: 12px;
        background: #f5f3ee;
        padding: 0.8rem 0.8rem 0.5rem 0.8rem;
    }
    .chart-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 0.3rem;
    }
    .chart-header h3 {
        font-size: 1.3rem;
        margin: 0;
        color: #242b35;
    }
    .chart-actions {
        display: flex;
        gap: 0.4rem;
    }
    .chart-actions button {
        border: 1px solid rgba(43, 53, 66, 0.25);
        background: #f5f3ee;
        border-radius: 8px;
        padding: 0.5rem 0.75rem;
        color: #303645;
        font-weight: 500;
    }
    .stFormSubmitButton button {
        background: #f5f3ee;
        border: 1px solid rgba(43, 53, 66, 0.3);
        color: #1d2431;
        border-radius: 10px;
        font-weight: 600;
    }
    .stButton button:hover {
        border-color: rgba(43, 53, 66, 0.5);
    }
    @media (max-width: 900px) {
        .chart-header { display: block; }
    }
</style>
"""


def build_curve_payloads(payload: dict) -> list[dict]:
    center_spot = float(payload["spot"])
    min_spot = center_spot * (1 - 0.3)
    max_spot = center_spot * (1 + 0.3)
    spots = [min_spot + (max_spot - min_spot) * i / 24 for i in range(25)]

    rows: list[dict] = []
    for spot in spots:
        resp, status = handle_price_request({**payload, "spot": spot})
        if status != 200:
            continue
        greeks = resp["greeks"]
        rows.append(
            {
                "Spot": spot,
                "Price": resp["price"],
                "Delta": greeks["delta"],
                "Gamma": greeks["gamma"],
                "Theta": greeks["theta"],
                "Vega": greeks["vega"],
                "Rho": greeks["rho"],
            }
        )
    return rows


def render_chart(df: pd.DataFrame, greek_key: str) -> None:
    if df.empty:
        st.info("No pricing data available yet.")
        return

    price_chart = (
        alt.Chart(df)
        .mark_line(color="#1f5fbf", strokeWidth=2.5)
        .encode(
            x=alt.X("Spot:Q", axis=alt.Axis(title="Spot Price", labelAngle=0)),
            y=alt.Y("Price:Q", axis=alt.Axis(title="Theoretical Price")),
        )
    )

    greek_chart = (
        alt.Chart(df)
        .mark_line(color="#d5506e", strokeDash=[6, 4], strokeWidth=2)
        .encode(
            x=alt.X("Spot:Q", axis=alt.Axis(title="Spot Price", labelAngle=0)),
            y=alt.Y(f"{greek_key}:Q", axis=alt.Axis(title=f"{greek_key.title()} (Δ)")),
        )
    )

    combined = alt.layer(price_chart, greek_chart).resolve_scale(y="independent")
    st.altair_chart(combined, use_container_width=True)


def app() -> None:
    st.set_page_config(page_title="Option Pricer", layout="wide")
    st.markdown(CSS, unsafe_allow_html=True)

    with st.form("option_pricer_form"):
        left, right = st.columns([1.05, 1.35], gap="large")

        with left:
            c1, c2, c3 = st.columns(3)
            with c1:
                spot = st.number_input("Spot Price", value=100.0, min_value=0.01, step=0.01)
            with c2:
                strike = st.number_input("Strike Price", value=105.0, min_value=0.01, step=0.01)
            with c3:
                days_to_maturity = st.number_input("Days to Maturity", value=365, min_value=1, step=1)

            r1, r2 = st.columns(2)
            with r1:
                rate_pct = st.slider("Risk-Free Rate (%)", min_value=-5.0, max_value=20.0, value=5.0, step=0.1)
            with r2:
                vol_pct = st.slider("Volatility (%)", min_value=0.5, max_value=100.0, value=20.0, step=0.5)

            option_type = st.radio("Option Type", ["call", "put"], horizontal=True)
            submitted = st.form_submit_button("Price option")

        with right:
            st.markdown("<h3 style='margin:0 0 0.5rem 0;'>Black-Scholes Model</h3>", unsafe_allow_html=True)
            if not submitted:
                submitted = True

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
        return

    curve_df = pd.DataFrame(build_curve_payloads(payload))
    greek_choice = st.radio(
        "Greek Type",
        ["Delta", "Gamma", "Vega", "Theta", "Rho"],
        index=0,
        horizontal=True,
        label_visibility="visible",
    )

    st.markdown("<div style='height: 1.2rem;'></div>", unsafe_allow_html=True)

    left, right = st.columns([1.02, 1.35], gap="large")
    with left:
        st.markdown(
            f"""
            <div class='price-card'>
                <div class='price-row'><span>Price:</span><strong>{body['price']:.4f}</strong></div>
                <div class='greek-row'><span>Delta</span><span>{body['greeks']['delta']:.4f}</span></div>
                <div class='greek-row'><span>Gamma</span><span>{body['greeks']['gamma']:.4f}</span></div>
                <div class='greek-row'><span>Theta</span><span>{body['greeks']['theta']:.4f}</span></div>
                <div class='greek-row'><span>Vega</span><span>{body['greeks']['vega']:.4f}</span></div>
                <div class='greek-row'><span>Rho</span><span>{body['greeks']['rho']:.4f}</span></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with right:
        st.markdown(
            """
            <div class='chart-panel'>
                <div class='chart-header'>
                    <h3>Black-Scholes Model</h3>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        render_chart(curve_df, greek_choice.lower())


if __name__ == "__main__":
    app()


# This script intentionally renders the custom UI in Streamlit instead of starting
# the standalone backend HTTP server. The backend server remains available via
# `python option-pricer/run.py` when a local browser app is desired.
