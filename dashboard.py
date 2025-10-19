# ============================================================
# 🌍 AI + Global Risk Dashboard (Canonical 10 Signals + History)
# - Manual "Refresh now" button
# - Live data where feasible + safe fallbacks
# - Thresholds aligned with earlier traffic lights
# ============================================================
import streamlit as st
import pandas as pd
import yfinance as yf
import datetime, requests, re, os

HISTORY_FILE = "crash_history.csv"
CRITICAL_THRESHOLD = 50  # % => red banner
CACHE_TTL = 1800         # seconds (30 min)

st.set_page_config(page_title="AI + Global Risk Dashboard", layout="wide")
st.title("🌍 AI + Global Risk Dashboard")

# ---------- Helpers ----------
def safe_float(v, default=None):
    try:
        if isinstance(v, (list, tuple)):
            v = v[-1]
        if isinstance(v, pd.Series):
            v = v.dropna().iloc[-1]
        return round(float(v), 2)
    except Exception:
        return default

def dedup_append_history(date_str, prob):
    new = pd.DataFrame([[date_str, prob]], columns=["date", "crash_probability"])
    if os.path.exists(HISTORY_FILE):
        hist = pd.read_csv(HISTORY_FILE)
        hist = hist[hist["date"] != date_str]
        hist = pd.concat([hist, new], ignore_index=True)
    else:
        hist = new
    hist.to_csv(HISTORY_FILE, index=False)
    return hist

# ---------- Live fetch (cached) ----------
@st.cache_data(ttl=CACHE_TTL)
def fetch_live_signals():
    # 1) NVIDIA P/E (Yahoo)
    try:
        nvda = yf.Ticker("NVDA")
        nvda_pe = safe_float(nvda.info.get("trailingPE"), 55.0)
    except Exception:
        nvda_pe = 55.0

    # 2) Hyperscaler DC CapEx growth (no stable free API) -> use conservative fallback
    #    You can override this from the sidebar slider if desired.
    capex_growth = 35.0  # %

    # 3) Yield-curve slope 10Y-2Y (FRED CSV)
    try:
        fred = pd.read_csv("https://fred.stlouisfed.org/graph/fredgraph.csv?id=T10Y2Y")
        yield_spread = safe_float(fred["T10Y2Y"], -0.4)
    except Exception:
        yield_spread = -0.4

    # 4) VIX (Yahoo)
    try:
        vix_data = yf.download("^VIX", period="5d", progress=False)
        vix_val = safe_float(vix_data["Close"], 22.0)
    except Exception:
        vix_val = 22.0

    # 5) AI/Tech ETF fund flows (ETF.com channel page sentiment)
    try:
        page = requests.get("https://www.etf.com/channels/artificial-intelligence-etfs", timeout=15).text
        ai_flows = "Inflows" if "inflows" in page.lower() else "Outflows"
    except Exception:
        ai_flows = "Inflows"

    # 6) China–US tension sentiment (very light heuristic via Google News RSS)
    try:
        rss = requests.get("https://news.google.com/rss/search?q=china+us+tension", timeout=10).text.lower()
        cn_us_tension = "Tightened" if ("tension" in rss or "sanction" in rss or "export control" in rss) else "Stable"
    except Exception:
        cn_us_tension = "Tightened"

    # 7) Critical resources restrictions (rare earths/graphite) — heuristic
    try:
        rss2 = requests.get("https://news.google.com/rss/search?q=rare+earth+export+controls+graphite+restrictions", timeout=10).text.lower()
        critical_resources = "Tightened" if ("control" in rss2 or "ban" in rss2 or "restriction" in rss2) else "Stable"
    except Exception:
        critical_resources = "Tightened"

    # 8) Ukraine/Europe escalation — heuristic
    try:
        rss3 = requests.get("https://news.google.com/rss/search?q=ukraine+europe+tension+nato+incident", timeout=10).text.lower()
        ukraine_europe = "Tense" if ("tension" in rss3 or "escalation" in rss3 or "incident" in rss3) else "Stable"
    except Exception:
        ukraine_europe = "Tense"

    # 9) Global defense spending trend — proxy via ITA ETF (Yahoo)
    try:
        ita = yf.download("ITA", period="1mo", progress=False)["Close"].dropna()
        def_spend_trend = safe_float(((ita.iloc[-1] - ita.iloc[0]) / ita.iloc[0]) * 100, 0.0)
    except Exception:
        def_spend_trend = 0.0

    # 10) USD reserve share (IMF COFER scrape – fragile, fallback to 58%)
    try:
        html = requests.get("https://data.imf.org/regular.aspx?key=41175", timeout=15).text
        m = re.search(r"US DOLLAR.*?(\d{1,2}\.\d)", html, re.I | re.S)
        usd_share = safe_float(m.group(1)) if m else 58.0
    except Exception:
        usd_share = 58.0

    return {
        "nvda_pe": nvda_pe,
        "capex_growth": capex_growth,
        "yield_spread": yield_spread,
        "vix": vix_val,
        "ai_flows": ai_flows,
        "cn_us_tension": cn_us_tension,
        "critical_resources": critical_resources,
        "ukraine_europe": ukraine_europe,
        "def_spend_trend": def_spend_trend,
        "usd_share": usd_share,
    }

# ---------- Sidebar overrides (optional) ----------
with st.sidebar:
    st.markdown("### ⚙️ Options")
    force_refresh = st.button("🔄 Refresh now (pull live data, update history)")
    st.caption("If a source is flaky, click to re-fetch and update the chart.")
    manual_capex = st.slider("Override Hyperscaler CapEx growth (%)", 0, 50, 35)
    st.caption("Leave at 35% unless you have a new datapoint.")

# On initial load OR when user clicks "Refresh now", clear cache to re-fetch
if force_refresh:
    st.cache_data.clear()

data = fetch_live_signals()
# Apply optional CapEx override
data["capex_growth"] = float(manual_capex)

# ---------- Classifiers (aligned with earlier traffic lights) ----------
def classify_nvda_pe(v):
    # <40 green, 40–55 amber, >55 red
    return "Green" if v < 40 else "Amber" if v <= 55 else "Red"

def classify_vix(v):
    # <20 green, 20–25 amber, >25 red
    return "Green" if v < 20 else "Amber" if v <= 25 else "Red"

def classify_yield_spread(v):
    # We treat steepening >= +0.5 as Red; otherwise Amber (macro caution)
    return "Red" if v is not None and v >= 0.5 else "Amber"

def classify_ai_flows(s):
    return "Green" if s == "Inflows" else "Red"

def classify_cn_us(s):
    # Default Amber unless clearly stable
    return "Amber" if s.lower() != "stable" else "Green"

def classify_critical(s):
    # Default Amber unless clearly stable
    return "Amber" if s.lower() != "stable" else "Green"

def classify_ukr(s):
    # Default Amber unless clearly stable
    return "Amber" if s.lower() != "stable" else "Green"

def classify_def_spend_trend(v):
    # If sustained >+20% YoY we might worry; this proxy is monthly → keep simple
    return "Green" if v < 20 else "Red"

def classify_usd_share(v):
    # >=57% Green, else Red (matches prior logic)
    return "Green" if v >= 57 else "Red"

# ---------- Build the canonical 10-signal table ----------
rows = [
    ["NVIDIA P/E ratio", data["nvda_pe"], classify_nvda_pe(data["nvda_pe"])],
    ["Hyperscaler Datacenter CapEx growth", f"{data['capex_growth']}%", "Green" if data["capex_growth"] > 10 else "Amber"],
    ["Yield-curve slope (10Y–2Y)", data["yield_spread"], classify_yield_spread(data["yield_spread"])],
    ["VIX (Volatility Index)", data["vix"], classify_vix(data["vix"])],
    ["AI/Tech ETF fund flows", data["ai_flows"], classify_ai_flows(data["ai_flows"])],
    ["China–US tension", data["cn_us_tension"], classify_cn_us(data["cn_us_tension"])],
    ["Critical resources restrictions", data["critical_resources"], classify_critical(data["critical_resources"])],
    ["Ukraine / Europe escalation", data["ukraine_europe"], classify_ukr(data["ukraine_europe"])],
    ["Global defense spending (proxy: ITA trend %/mo)", f"{data['def_spend_trend']}%", classify_def_spend_trend(data["def_spend_trend"])],
    ["USD reserve share", f"{data['usd_share']}%", classify_usd_share(data["usd_share"])],
]
signals = pd.DataFrame(rows, columns=["Signal", "Current", "Status"])

# ---------- Crash probability (same formula we used before) ----------
num_amber = int((signals["Status"] == "Amber").sum())
num_red = int((signals["Status"] == "Red").sum())
crash_prob = min(10 + num_amber * 5 + num_red * 10, 100)

# ---------- Top alert/banner ----------
if crash_prob >= CRITICAL_THRESHOLD:
    st.error(f"🚨 **CRITICAL RISK — Crash Probability {crash_prob}% — ACTION REQUIRED**")
else:
    st.success(f"✅ System Stable — Crash Probability {crash_prob}%")

# ---------- Table (traffic-light colors) ----------
color_map = {"Green": "#00b050", "Amber": "#ffc000", "Red": "#c00000"}
styled = signals.style.applymap(lambda s: f"color:{color_map.get(s, 'black')}", subset=["Status"])
st.dataframe(styled, use_container_width=True)

# ---------- History (update on initial load and when user clicks Refresh) ----------
today = datetime.date.today().isoformat()
hist = dedup_append_history(today, crash_prob)

st.subheader("📈 Crash-Probability Trend")
st.line_chart(hist.set_index("date"))

st.caption(f"Last updated {today}  |  Live sources where feasible: Yahoo Finance, FRED (CSV), IMF (scrape), ETF.com, Google News. CapEx uses manual override until a stable public feed is available.")
