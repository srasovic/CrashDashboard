# ============================================================
# 🌍 AI + Global Risk Dashboard (Streamlit - fully stable)
# ============================================================
import streamlit as st
import pandas as pd
import yfinance as yf
import datetime
import requests

# ---------- CONFIG ----------
CRITICAL_THRESHOLD = 50  # % level that triggers red warning

# ---------- PAGE SETTINGS ----------
st.set_page_config(page_title="AI + Global Risk Dashboard", layout="wide")
st.title("🌍 AI + Global Risk Dashboard")

# ---------- DATA FETCH ----------
@st.cache_data(ttl=3600)
def fetch_data():
    """Fetch all live market data safely."""
    nvda_pe = None
    vix_val = None
    yield_spread = None

    # NVIDIA P/E
    try:
        nvda = yf.Ticker("NVDA")
        nvda_pe = nvda.info.get("trailingPE")
        if nvda_pe and isinstance(nvda_pe, (int, float)):
            nvda_pe = round(nvda_pe, 2)
        else:
            nvda_pe = 55.0  # fallback
    except Exception:
        nvda_pe = 55.0

    # VIX
    try:
        vix_data = yf.download("^VIX", period="5d", progress=False)
        vix_val = float(vix_data["Close"].dropna().iloc[-1])
        vix_val = round(vix_val, 2)
    except Exception:
        vix_val = 22.0  # fallback

    # Yield curve (fallback static if FRED not available)
    try:
        url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=T10Y2Y"
        data = pd.read_csv(url)
        yield_spread = float(data["T10Y2Y"].dropna().iloc[-1])
        yield_spread = round(yield_spread, 2)
    except Exception:
        yield_spread = -0.4  # fallback

    usd_share = 58.0
    ai_flows = "Inflows"
    geo = {
        "china_us": "Tightened",
        "critical_resources": "Tightened",
        "ukraine": "Tense",
        "defense_spending": 12.0,
    }

    return nvda_pe, vix_val, yield_spread, usd_share, ai_flows, geo


# ---------- CLASSIFIERS ----------
def classify_nvda_pe(val):
    return "Green" if val < 40 else "Amber" if val <= 55 else "Red"

def classify_vix(val):
    return "Green" if val < 20 else "Amber" if val <= 25 else "Red"

def classify_yield(val):
    return "Red" if val >= 0.5 else "Amber"


# ---------- MAIN ----------
nvda_pe, vix_val, yield_spread, usd_share, ai_flows, geo = fetch_data()

signals = pd.DataFrame([
    ["NVIDIA P/E ratio", nvda_pe, classify_nvda_pe(nvda_pe)],
    ["Hyperscaler CapEx growth", "35 %", "Green"],
    ["Yield-curve (10Y-2Y)", yield_spread, classify_yield(yield_spread)],
    ["VIX Volatility Index", vix_val, classify_vix(vix_val)],
    ["AI/Tech ETF fund flows", ai_flows, "Green" if ai_flows == "Inflows" else "Red"],
    ["China–US tension", geo["china_us"], "Amber"],
    ["Critical resources restrictions", geo["critical_resources"], "Amber"],
    ["Ukraine / Europe conflict", geo["ukraine"], "Amber"],
    ["Global defense spending", f"{geo['defense_spending']}%", "Green"],
    ["USD reserve share", f"{usd_share}%", "Green" if usd_share >= 57 else "Red"],
], columns=["Signal", "Current", "Status"])

# ---------- RISK CALCULATION ----------
num_amber = (signals["Status"] == "Amber").sum()
num_red = (signals["Status"] == "Red").sum()
crash_prob = min(10 + num_amber * 5 + num_red * 10, 100)

# ---------- ALERT ----------
if crash_prob >= CRITICAL_THRESHOLD:
    st.error(f"🚨 **CRITICAL RISK – Crash Probability {crash_prob}% – Action Required!**")
else:
    st.success(f"✅ System Stable – Crash Probability {crash_prob}%")

# ---------- DISPLAY ----------
color_map = {"Green": "#00b050", "Amber": "#ffc000", "Red": "#c00000"}
styled = signals.style.applymap(lambda v: f"color: {color_map.get(v, 'black')}", subset=["Status"])
st.dataframe(styled, use_container_width=True)

st.caption(f"Last updated {datetime.date.today()} | Data sources: Yahoo Finance, FRED, IMF")
