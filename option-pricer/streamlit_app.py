import altair as alt
import pandas as pd
import streamlit as st

from backend.api import handle_price_request


CSS = """
<style>
    .main .block-container {
        max-width: 1400px;
        padding-top: 1rem;
        padding-bottom: 2rem;
    }
    .app-shell {
        background: #f3efe9;
    }
    .uibox {
        background: #f7f5f1;
        border: 1px solid rgba(40,45,52,0.28);
        border-radius: 12px;
        padding: 1rem 1.1rem 0.8rem 1.1rem;
        margin-bottom: 1rem;
    }
    .metric-box {
        background: #f5f4f1;
        border: 1px solid rgba(40,45,52,0.28);
        border-radius: 12px;
        padding: 1rem 1.2rem;
        margin-top: 0.5rem;
    }
    .big-title {
        font-size: 2.2rem;
        font-weight: 800;
        margin-bottom: 1rem;
        color: #1d2431;
    }
    .small-label {
        font-size: 0.9rem;
        color: #2b2d35;
        font-weight: 600;
        display: block;
        margin-bottom: 0.25rem;
    }
    .result-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 0.5rem 0;
        border-top: 1px solid rgba(40,45,52,0.18);
    }
    .chart-title {
        font-size: 1.15rem;
        font-weight: 700;
        color: #1d2431;
        margin: 0 0 0.25rem 0;
    }
</style>
"""


def build_curve_payloads(payload: dict) -> list[dict]:
    center_spot = float(payload["spot"])
    min_spot = center_spot * 0.7
    max_spot = center_spot * 1.3
    spots = [min_spot + (max_spot - min_spot) * i / 24 for i in range(25)]

    rows = []
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


def render_chart(df: pd.DataFrame, greek_name: str) -> None:
    if df.empty:
        st.info("No curve available yet.")
        return

    greek_key = greek_name.lower()
    price_chart = (
        alt.Chart(df)
        .mark_line(color="#1f5fbf", strokeWidth=2.5)
        .encode(
            x=alt.X("Spot:Q", title="Spot Price"),
            y=alt.Y("Price:Q", title="Theoretical Price"),
        )
    )

    greek_chart = (
        alt.Chart(df)
        .mark_line(color="#d95473", strokeDash=[6, 4], strokeWidth=2.2)
        .encode(
            x=alt.X("Spot:Q", title="Spot Price"),
            y=alt.Y(f"{greek_key.title()}:Q", title=f"{greek_name} (Δ)"),
        )
    )

    chart = alt.layer(price_chart, greek_chart).resolve_scale(y="independent")
    st.altair_chart(chart, use_container_width=True)


def app() -> None:
    st.set_page_config(page_title="Option Pricer", layout="wide")
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown('<div class="big-title">Vanilla Option Calculator</div>', unsafe_allow_html=True)

    with st.form("pricing_form"):
        left, right = st.columns([1.05, 1.35], gap="large")

        with left:
            c1, c2, c3 = st.columns(3)
            with c1:
                spot = st.number_input("Spot Price *", value=100.0, min_value=0.01, step=0.01)
            with c2:
                strike = st.number_input("Strike Price *", value=105.0, min_value=0.01, step=0.01)
            with c3:
                days_to_maturity = st.number_input("Days to Maturity *", value=365, min_value=1, step=1)

            r1, r2 = st.columns(2)
            with r1:
                rate_pct = st.slider("Risk-Free Rate (%) *", min_value=-5.0, max_value=20.0, value=5.0, step=0.1)
            with r2:
                vol_pct = st.slider("Volatility (%) *", min_value=0.5, max_value=100.0, value=20.0, step=0.5)

            st.markdown('<div class="small-label">Option Type *</div>', unsafe_allow_html=True)
            option_type = st.radio("", ["call", "put"], horizontal=True, label_visibility="collapsed")

            submitted = st.form_submit_button("Price option")

        with right:
            st.markdown('<p class="chart-title">Black-Scholes Model</p>', unsafe_allow_html=True)
            if not submitted:
                st.caption("Enter your inputs and click Price option to generate the curve.")

    if not submitted:
        return

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

    st.markdown('<div style="height: 0.5rem"></div>', unsafe_allow_html=True)
    left_result, right_result = st.columns([0.9, 1.6], gap="large")

    with left_result:
        st.markdown(
            f"""
            <div class='metric-box'>
                <div class='result-row'><span>Price:</span><strong>{body['price']:.4f}</strong></div>
                <div class='result-row'><span>Delta</span><span>{body['greeks']['delta']:.4f}</span></div>
                <div class='result-row'><span>Gamma</span><span>{body['greeks']['gamma']:.4f}</span></div>
                <div class='result-row'><span>Theta</span><span>{body['greeks']['theta']:.4f}</span></div>
                <div class='result-row'><span>Vega</span><span>{body['greeks']['vega']:.4f}</span></div>
                <div class='result-row'><span>Rho</span><span>{body['greeks']['rho']:.4f}</span></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with right_result:
        greek_choice = st.radio(
            "Greek Type",
            ["Delta", "Gamma", "Vega", "Theta", "Rho"],
            index=0,
            horizontal=True,
        )
        render_chart(curve_df, greek_choice)


if __name__ == "__main__":
    app()
