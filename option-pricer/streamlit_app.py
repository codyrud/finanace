import altair as alt
import pandas as pd
import streamlit as st

from backend.api import handle_price_request


st.set_page_config(page_title="Option Pricer", layout="wide")

CSS = """
<style>
    .stApp {
        background: #071722;
        color: #edf4fb;
    }
    .main .block-container {
        max-width: 1400px;
        padding-top: 1rem;
        padding-bottom: 2rem;
    }
    .title {
        font-size: 2.2rem;
        font-weight: 800;
        color: #edf4fb;
        margin-bottom: 1rem;
    }
    .main-panel {
        border: 1px solid rgba(148,163,184,0.35);
        border-radius: 12px;
        background: rgba(15, 23, 42, 0.7);
        padding: 1rem 1.1rem 0.8rem 1.1rem;
        margin-bottom: 1.5rem;
    }
    .metric-box {
        margin-top: 0.5rem;
        max-width: 430px;
        width: 100%;
        background: transparent;
        border: none;
        padding: 0;
    }
    .metric-row {
        display: grid;
        grid-template-columns: 1fr auto;
        align-items: center;
        gap: 1rem;
        padding: 0.58rem 0;
        border-top: 1px solid rgba(148,163,184,0.22);
        color: #edf4fb;
    }
    .metric-row:first-child {
        border-top: 0;
    }
    .metric-label {
        color: #dfeaf7;
        font-size: 1.05rem;
        font-weight: 500;
        text-align: left;
    }
    .metric-value {
        font-size: 1.06rem;
        font-weight: 700;
        color: #ffffff;
        text-align: right;
        min-width: 110px;
    }
    .section-title {
        font-size: 1.15rem;
        font-weight: 700;
        color: #edf4fb;
        margin: 0 0 0.45rem 0;
    }
    .field-label {
        font-size: 0.96rem;
        font-weight: 600;
        color: #edf4fb;
        margin-bottom: 0.35rem;
        display: block;
    }
    .stNumberInput label, .stSlider label, .stRadio label {
        color: #edf4fb !important;
    }
    .stNumberInput input, .stSlider > div > div > div {
        background: rgba(15, 23, 42, 0.7);
        color: #edf4fb;
        border: 1px solid rgba(148,163,184,0.35);
    }
    .stSlider [data-testid="stBaseWidgetLabel"] {
        color: #edf4fb !important;
    }
    .stRadio [role="radiogroup"] {
        display: flex;
        gap: 0.8rem;
    }
    .stFormSubmitButton button {
        background: rgba(15, 23, 42, 0.72);
        color: #edf4fb;
        border: 1px solid rgba(148,163,184,0.4);
        border-radius: 8px;
        font-weight: 600;
        padding: 0.4rem 1rem;
    }
    .stRadio input {
        accent-color: #ff5a5f;
    }
</style>
"""

st.markdown(CSS, unsafe_allow_html=True)


def build_curve_payloads(payload: dict) -> list[dict]:
    center_spot = float(payload["spot"])
    min_spot = center_spot * 0.7
    max_spot = center_spot * 1.3
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


def render_chart(df: pd.DataFrame, greek_name: str) -> None:
    if df.empty:
        st.info("No curve available yet.")
        return

    greek_key = greek_name.lower()
    price_chart = (
        alt.Chart(df)
        .mark_line(color="#3b82f6", strokeWidth=2.5)
        .encode(
            x=alt.X("Spot:Q", title="Spot Price"),
            y=alt.Y("Price:Q", title="Theoretical Price"),
        )
    )

    greek_chart = (
        alt.Chart(df)
        .mark_line(color="#ff5a5f", strokeDash=[6, 4], strokeWidth=2.2)
        .encode(
            x=alt.X("Spot:Q", title="Spot Price"),
            y=alt.Y(f"{greek_key.title()}:Q", title=f"{greek_name}"),
        )
    )

    chart = alt.layer(price_chart, greek_chart).resolve_scale(y="independent")
    st.altair_chart(chart, width="stretch")


def app() -> None:
    st.markdown('<div class="title">Vanilla Option Calculator</div>', unsafe_allow_html=True)

    with st.form("pricing_form"):
        left, right = st.columns([1.05, 1.35], gap="large")

        with left:
            c1, c2, c3 = st.columns(3)
            with c1:
                spot = st.number_input("Spot Price *", value=115.0, min_value=0.01, step=0.01)
            with c2:
                strike = st.number_input("Strike Price *", value=150.0, min_value=0.01, step=0.01)
            with c3:
                days_to_maturity = st.number_input("Days to Maturity *", value=365, min_value=1, step=1)

            r1, r2 = st.columns(2)
            with r1:
                rate_pct = st.slider("Risk-Free Rate (%) *", min_value=-5.0, max_value=20.0, value=-0.70, step=0.1)
            with r2:
                vol_pct = st.slider("Volatility (%) *", min_value=0.5, max_value=100.0, value=46.0, step=0.5)

            st.markdown('<div class="field-label">Option Type *</div>', unsafe_allow_html=True)
            option_type = st.radio("Option Type *", ["call", "put"], horizontal=True)
            submitted = st.form_submit_button("Price option")

        with right:
            st.markdown('<div class="section-title">Black-Scholes Model</div>', unsafe_allow_html=True)
            greek_choice = st.radio("Greek Type", ["Delta", "Gamma", "Vega", "Theta", "Rho"], index=0, horizontal=True)

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
            render_chart(curve_df, greek_choice)

    st.markdown('<div style="height: 0.8rem"></div>', unsafe_allow_html=True)

    st.markdown(
        f"""
        <div class='metric-box'>
            <div class='metric-row'><div class='metric-label'>Price:</div><div class='metric-value'>{body['price']:.4f}</div></div>
            <div class='metric-row'><div class='metric-label'>Delta</div><div class='metric-value'>{body['greeks']['delta']:.4f}</div></div>
            <div class='metric-row'><div class='metric-label'>Gamma</div><div class='metric-value'>{body['greeks']['gamma']:.4f}</div></div>
            <div class='metric-row'><div class='metric-label'>Theta</div><div class='metric-value'>{body['greeks']['theta']:.4f}</div></div>
            <div class='metric-row'><div class='metric-label'>Vega</div><div class='metric-value'>{body['greeks']['vega']:.4f}</div></div>
            <div class='metric-row'><div class='metric-label'>Rho</div><div class='metric-value'>{body['greeks']['rho']:.4f}</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    app()
