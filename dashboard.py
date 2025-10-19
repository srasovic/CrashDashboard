# ============================================================
# 🌍 AI + Global Risk Dashboard  (Streamlit version)
# ============================================================
import streamlit as st
import pandas as pd
import yfinance as yf
import datetime, requests
from fredapi import Fred

# ---------- CONFIG ----------
FRED_API_KEY = "YOUR_FRED_API_KEY"   # get a free key from https://fred.stlouisfed.org/
CRITICAL_THRESHOLD = 50              # % level that triggers red warning

# ---------- PAGE SETTINGS ----------
st.set_page_config(page_title="AI + Global Risk Dashboard", layout="wide")
st.title("🌍 AI + Global Risk Dashboard")

# ---------- DATA FETCH ----------
@st.cache_data(ttl=3600)
def fetch_data():
    try:
        nvda = yf.Ticker("NVDA")
        nvda_pe = round(nvda.info.get("trailingPE", 0), 2)
    except:
        nvda_pe = None

    try:
        vix = yf.download("^VIX", period="1d", progress=False)["Close"].iloc[-1]
        vix = round(vix, 2)
    except:
        vix = None

    try:
        fred = Fred(api_key=FRED_API_KEY)
        spread = round(fred.get_series_latest_release("T10Y2Y").iloc[-1], 2)
    except:
        spread = None

    usd_share = 58.0
    ai_flows = "Inflows"

    geo = {
        "china_us": "Tightened",
        "critical_resources": "Tightened",
        "ukraine": "Tense",
        "defense_spending": 12.0,
    }

    return nvda_pe, vix, spread, usd_share, ai_flows, geo

nvda_pe, vix_val, yield_spread, usd_share, ai_flows, geo = fetch_data()

# ---------- CLASSIFIERS ----------
def classify_nvda_pe(val):
    if val is None: return "Amber"
    return "Green" if val < 40 else "Amber" if val <= 55 else "Red"

def classify_vix(val):
    if val is None: return "Amber"
    return "Green" if val < 20 else "Amber" if val <= 25 else "Red"

def classify_yield(val):
    if val is None: return "Amber"
    return "Red" if val >= 0.5 else "Amber"

# ---------- BUILD SIGNAL TABLE ----------
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

# ---------- DISPLAY ALERT ----------
if crash_prob >= CRITICAL_THRESHOLD:
    st.error(f"🚨 **CRITICAL RISK – Crash Probability {crash_prob}% – Action Required!**")
else:
    st.success(f"✅ System Stable – Crash Probability {crash_prob}%")

# ---------- DISPLAY TABLE ----------
color_map = {"Green": "#00b050", "Amber": "#ffc000", "Red": "#c00000"}
def colorize(val): return f"color: {color_map.get(val,'black')}"
st.dataframe(signals.style.applymap(lambda v: color_map.get(v, ""), subset=["Status"]),
             use_container_width=True)

# ---------- FOOTER ----------
st.caption(f"Last updated {datetime.date.today()}  |  Data sources: Yahoo Finance, FRED, IMF")
