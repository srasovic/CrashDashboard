import streamlit as st, pandas as pd, yfinance as yf, datetime
from fredapi import Fred
import requests

FRED_API_KEY = "YOUR_FRED_API_KEY"

st.set_page_config(page_title="AI + Global Risk Dashboard", layout="wide")
st.title("🌍 AI + Global Risk Dashboard")

# Live data
nvda = yf.Ticker("NVDA")
pe = round(nvda.info.get("trailingPE", 0), 2)
vix = round(yf.download("^VIX", period="1d", progress=False)["Close"].iloc[-1], 2)

fred = Fred(api_key=FRED_API_KEY)
spread = round(fred.get_series_latest_release("T10Y2Y").iloc[-1], 2)

usd_share = 58.0
ai_flows = "Inflows"

signals = pd.DataFrame([
    ["NVIDIA P/E ratio", pe, "Green" if pe < 40 else "Amber" if pe <= 55 else "Red"],
    ["VIX Volatility Index", vix, "Green" if vix < 20 else "Amber" if vix <= 25 else "Red"],
    ["Yield Curve (10Y–2Y)", spread, "Red" if spread >= 0.5 else "Amber"],
    ["USD Reserve Share", usd_share, "Green" if usd_share >= 57 else "Red"],
    ["AI ETF Flows", ai_flows, "Green" if ai_flows == "Inflows" else "Red"]
], columns=["Signal","Current","Status"])

num_amber = (signals.Status == "Amber").sum()
num_red = (signals.Status == "Red").sum()
crash_prob = min(10 + num_amber*5 + num_red*10, 100)

if crash_prob >= 50:
    st.error(f"🚨 **CRITICAL RISK – Crash Probability {crash_prob}% – Action Required!**")
else:
    st.success(f"✅ System Stable – Crash Probability {crash_prob}%")

st.dataframe(signals, use_container_width=True)
st.caption(f"Last updated {datetime.date.today()}")
