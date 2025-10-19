# ============================================================
# 🌍 AI + Global Risk Dashboard (Streamlit version - Stable)
# ============================================================
import streamlit as st
import pandas as pd
import yfinance as yf
import datetime
import requests
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
    """Fetch all external data safely."""
    # NVIDIA P/E
    try:
        nvda = yf.Ticker("NVDA")
        nvda_pe = nvda.info.get("trailingPE")
        if isinstance(nvda_pe, (list, pd.Series)):  # safety
            nvda_pe = float(nvda_pe.iloc[-1])
        nvda_pe = round(float(nvda_pe), 2) if nvda_pe else None
    except Exception:
        nvda_pe = None

    # VIX
    try:
        vix_data = yf.download("^VIX", period="5d", progress=False)
        vix_val = float(vix_data["Close"].dropna().iloc[-1])
        vix_val = round(vix_val, 2)
    except Exception:
        vix_val = None

    # Yield curve
    try:
        fred = Fred(api_key=FRED_API_KEY)
        spread = fred.get_series_latest_release("T10Y2Y").dropna().iloc[-1]
        yield_spread = round(float(spread), 2)
    except Exception:
        yield_spread = None

    # USD share and AI flows
    usd_share = 58.0
    ai_flows = "Inflows"

    # Geopolitical
    geo = {
        "china_us": "Tightened",
        "critical_resources": "Tightened",
        "ukraine": "Tense",
        "defense_spending": 12.0,
    }

    return nvda_pe, vix_val, yield_spread, usd_share, ai_flows, geo


# ---------- CLASSIFIERS ----------
def classify_nvda_pe(val):
    if val is None: return "Amber"
    try:
        if val < 40: return "Green"
        elif val <= 55: return "Amber"
        else: return "Red"
    except Exception:
        return "Amber"

def classify_vix(val):
    if val is None: return "Amber"
    try:
        if val < 20: return "Green"
        elif val <= 25: return "Amber"
        else: return "Red"
    except Exception:
        return "Amber"

def classify_yield(val):
    if val is None: return "Amber"
