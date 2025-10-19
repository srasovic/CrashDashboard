# ============================================================
# 🌍 AI + Global Risk Dashboard (Full Live Data + History)
# ============================================================
import streamlit as st
import pandas as pd
import yfinance as yf
import datetime, requests, re, os
from bs4 import BeautifulSoup

# ---------- CONFIG ----------
HISTORY_FILE = "crash_history.csv"
CRITICAL_THRESHOLD = 50  # %
st.set_page_config(page_title="AI + Global Risk Dashboard", layout="wide")
st.title("🌍 AI + Global Risk Dashboard (Live Sources)")

# ---------- HELPER: Safe value parsing ----------
def safe_float(v, default=None):
    try: return round(float(v),2)
    except Exception: return default

# ---------- FETCH DATA ----------
@st.cache_data(ttl=3600)
def fetch_all_live():
    """Pull all possible live signals from open sources."""
    # --- NVIDIA P/E ratio (Yahoo Finance)
    try:
        nvda = yf.Ticker("NVDA")
        nvda_pe = safe_float(nvda.info.get("trailingPE"), 55.0)
    except Exception:
        nvda_pe = 55.0

    # --- VIX (Yahoo Finance)
    try:
        vix_data = yf.download("^VIX", period="5d", progress=False)
        vix_val = safe_float(vix_data["Close"].dropna().iloc[-1], 22.0)
    except Exception:
        vix_val = 22.0

    # --- US 10Y-2Y Yield Spread (FRED CSV)
    try:
        fred = pd.read_csv("https://fred.stlouisfed.org/graph/fredgraph.csv?id=T10Y2Y")
        yield_spread = safe_float(fred["T10Y2Y"].dropna().iloc[-1], -0.4)
    except Exception:
        yield_spread = -0.4

    # --- USD Reserve Share (IMF COFER table)
    try:
        html = requests.get("https://data.imf.org/regular.aspx?key=41175", timeout=15).text
        match = re.search(r"US DOLLAR.*?(\d{1,2}\.\d)", html, re.I|re.S)
        usd_share = safe_float(match.group(1)) if match else 58.0
    except Exception:
        usd_share = 58.0

    # --- AI ETF Fund Flows (ETF.com)
    try:
        page = requests.get("https://www.etf.com/channels/artificial-intelligence-etfs", timeout=15).text
        ai_flows = "Inflows" if "inflows" in page.lower() else "Outflows"
    except Exception:
        ai_flows = "Inflows"

    # --- Nasdaq Index (Yahoo Finance)
    try:
        nasdaq = yf.download("^IXIC", period="5d", progress=False)["Close"].iloc[-1]
        nasdaq_chg = round(((nasdaq - yf.download("^IXIC", period="10d", progress=False)["Close"].iloc[0])/nasdaq)*100,2)
    except Exception:
        nasdaq_chg = 0.0

    # --- Gold Price (Yahoo Finance)
    try:
        gold = yf.download("GC=F", period="5d", progress=False)["Close"].dropna().iloc[-1]
        gold_chg = round(((gold - yf.download("GC=F", period="10d", progress=False)["Close"].iloc[0])/gold)*100,2)
    except Exception:
        gold_chg = 0.0

    # --- Oil Price (Yahoo Finance)
    try:
        brent = yf.download("BZ=F", period="5d", progress=False)["Close"].dropna().iloc[-1]
        oil_chg = round(((brent - yf.download("BZ=F", period="10d", progress=False)["Close"].iloc[0])/brent)*100,2)
    except Exception:
        oil_chg = 0.0

    # --- Defense spending trend (proxy: ITA ETF price)
    try:
        ita = yf.download("ITA", period="1mo", progress=False)["Close"].dropna()
        def_spend_trend = round(((ita.iloc[-1]-ita.iloc[0])/ita.iloc[0])*100,2)
    except Exception:
        def_spend_trend = 0.0

    # --- Geopolitical: placeholder sentiment feed (scrape from Google News headline)
    try:
        news = requests.get("https://news.google.com/rss/search?q=china+us+tension", timeout=10).text.lower()
        tension = "Tightened" if "tension" in news or "conflict" in news else "Stable"
    except Exception:
        tension = "Tightened"

    return dict(
        nvda_pe=nvda_pe, vix=vix_val, yield_spread=yield_spread, usd_share=usd_share,
        ai_flows=ai_flows, nasdaq_chg=nasdaq_chg, gold_chg=gold_chg, oil_chg=oil_chg,
        def_spend_trend=def_spend_trend, tension=tension
    )


data = fetch_all_live()

# ---------- CLASSIFIERS ----------
def classify_nvda_pe(v): return "Green" if v < 40 else "Amber" if v <= 55 else "Red"
def classify_vix(v): return "Green" if v < 20 else "Amber" if v <= 25 else "Red"
def classify_yield(v): return "Red" if v >= 0.5 else "Amber"
def classify_usd_share(v): return "Green" if v >= 57 else "Red"
def classify_trend(v): return "Green" if v > 0 else "Red"
def classify_tension(v): return "Amber" if "tight" in v.lower() else "Green"

# ---------- TABLE ----------
signals = pd.DataFrame([
    ["NVIDIA P/E ratio", data["nvda_pe"], classify_nvda_pe(data["nvda_pe"])],
    ["VIX Volatility Index", data["vix"], classify_vix(data["vix"])],
    ["Yield-curve (10Y-2Y)", data["yield_spread"], classify_yield(data["yield_spread"])],
    ["USD Reserve Share", f"{data['usd_share']}%", classify_usd_share(data["usd_share"])],
    ["AI/Tech ETF fund flows", data["ai_flows"], "Green" if data["ai_flows"]=="Inflows" else "Red"],
    ["NASDAQ 10-day change", f"{data['nasdaq_chg']}%", classify_trend(data["nasdaq_chg"])],
    ["Gold 10-day change", f"{data['gold_chg']}%", classify_trend(data["gold_chg"])],
    ["Oil (Brent) 10-day change", f"{data['oil_chg']}%", classify_trend(data["oil_chg"])],
    ["Defense ETF (ITA) trend", f"{data['def_spend_trend']}%", classify_trend(data["def_spend_trend"])],
    ["China–US tension sentiment", data["tension"], classify_tension(data["tension"])],
], columns=["Signal", "Current", "Status"])

# ---------- RISK CALC ----------
num_amber = (signals.Status=="Amber").sum()
num_red = (signals.Status=="Red").sum()
crash_prob = min(10 + num_amber*5 + num_red*10, 100)

# ---------- ALERT ----------
if crash_prob >= CRITICAL_THRESHOLD:
    st.error(f"🚨 **CRITICAL RISK – Crash Probability {crash_prob}% – Action Required!**")
else:
    st.success(f"✅ System Stable – Crash Probability {crash_prob}%")

# ---------- DISPLAY ----------
color_map = {"Green":"#00b050","Amber":"#ffc000","Red":"#c00000"}
st.dataframe(signals.style.applymap(lambda s:f"color:{color_map.get(s,'black')}",subset=["Status"]),
             use_container_width=True)

# ---------- HISTORY ----------
today = datetime.date.today().isoformat()
new = pd.DataFrame([[today, crash_prob]], columns=["date","crash_probability"])
if os.path.exists(HISTORY_FILE):
    hist = pd.read_csv(HISTORY_FILE)
    hist = hist[hist["date"] != today]
    hist = pd.concat([hist, new], ignore_index=True)
else:
    hist = new
hist.to_csv(HISTORY_FILE, index=False)

# ---------- CHART ----------
st.subheader("📈 Crash-Probability Trend")
st.line_chart(hist.set_index("date"))

st.caption(f"Last updated {today} | Live sources: Yahoo Finance, FRED, IMF, ETF.com, Google News")
