# ============================================================
# 🌍 AI + Global Risk Dashboard (Canonical 10 Signals + History + Diffs)
# - Manual "Refresh now" button
# - Live data where feasible + safe fallbacks
# - Yield logic aligned with Replit (Red only if >= threshold; else Amber)
# - Previous run comparison: Last Status + Change; probability delta
# ============================================================
import streamlit as st
import pandas as pd
import yfinance as yf
import datetime, requests, re, os, json

HISTORY_FILE = "crash_history.csv"
LAST_FILE = "last_snapshot.json"
CRITICAL_THRESHOLD = 50     # % => red banner
CACHE_TTL = 1800            # seconds (30 min)
DEFAULT_YIELD_RED = 0.50    # 10y-2y steepening threshold for Red

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

def load_last_snapshot():
    if os.path.exists(LAST_FILE):
        with open(LAST_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"crash_probability": None, "statuses": {}}

def save_last_snapshot(crash_prob, status_map):
    data = {"crash_probability": crash_prob, "statuses": status_map}
    with open(LAST_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f)

# ---------- Sidebar controls ----------
with st.sidebar:
    st.markdown("### ⚙️ Options")
    force_refresh = st.button("🔄 Refresh now (pull live data, update history)")
    st.caption("Click if values look stale or to force a new run.")
    yield_avg = st.checkbox("Use 5-day average for yield spread", value=False)
    yield_red_threshold = st.slider("Yield Red threshold (10y–2y, %)", 0.10, 1.00, DEFAULT_YIELD_RED, 0.05)
    manual_capex = st.slider("Override Hyperscaler CapEx growth (%)", 0, 50, 35)
    st.caption("CapEx has no stable free feed; override if you have a new datapoint.")
    st.caption("Diffs vs last run are shown in the table as ▲ worsened / ▼ improved / • no change.")

if force_refresh:
    st.cache_data.clear()

# ---------- Live fetch (cached) ----------
@st.cache_data(ttl=CACHE_TTL)
def fetch_live_signals(use_avg_for_yield: bool, yield_red: float):
    # 1) NVIDIA P/E (Yahoo)
    try:
        nvda = yf.Ticker("NVDA")
        nvda_pe = safe_float(nvda.info.get("trailingPE"), 55.0)
    except Exception:
        nvda_pe = 55.0

    # 2) Hyperscaler DC CapEx growth (manual override later)
    capex_growth = 35.0  # %

    # 3) Yield-curve slope 10Y-2Y (FRED CSV)
    try:
        fred = pd.read_csv("https://fred.stlouisfed.org/graph/fredgraph.csv?id=T10Y2Y")
        series = fred["T10Y2Y"].dropna()
        if use_avg_for_yield and len(series) >= 5:
            yield_spread = safe_float(series.tail(5).mean(), -0.4)
        else:
            yield_spread = safe_float(series, -0.4)
    except Exception:
        yield_spread = -0.4

    # 4) VIX (Yahoo)
    try:
        vix = yf.download("^VIX", period="5d", progress=False)["Close"].dropna()
        vix_val = safe_float(vix, 22.0)
    except Exception:
        vix_val = 22.0

    # 5) AI/Tech ETF fund flows (ETF.com channel page sentiment)
    try:
        page = requests.get("https://www.etf.com/channels/artificial-intelligence-etfs", timeout=15).text
        ai_flows = "Inflows" if "inflows" in page.lower() else "Outflows"
    except Exception:
        ai_flows = "Inflows"

    # 6) China–US tension (very light heuristic via Google News RSS)
    try:
        rss = requests.get("https://news.google.com/rss/search?q=china+us+tension", timeout=10).text.lower()
        cn_us_tension = "Tightened" if any(k in rss for k in ["tension", "sanction", "export control"]) else "Stable"
    except Exception:
        cn_us_tension = "Tightened"

    # 7) Critical resources restrictions (rare earths/graphite) — heuristic
    try:
        rss2 = requests.get("https://news.google.com/rss/search?q=rare+earth+export+controls+graphite+restrictions", timeout=10).text.lower()
        critical_resources = "Tightened" if any(k in rss2 for k in ["control", "ban", "restriction"]) else "Stable"
    except Exception:
        critical_resources = "Tightened"

    # 8) Ukraine/Europe escalation — heuristic
    try:
        rss3 = requests.get("https://news.google.com/rss/search?q=ukraine+europe+tension+nato+incident", timeout=10).text.lower()
        ukraine_europe = "Tense" if any(k in rss3 for k in ["tension", "escalation", "incident"]) else "Stable"
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
        "yield_red_threshold": yield_red,   # carry for classifiers
        "vix": vix_val,
        "ai_flows": ai_flows,
        "cn_us_tension": cn_us_tension,
        "critical_resources": critical_resources,
        "ukraine_europe": ukraine_europe,
        "def_spend_trend": def_spend_trend,
        "usd_share": usd_share,
    }

data = fetch_live_signals(yield_avg, yield_red_threshold)
data["capex_growth"] = float(manual_capex)  # apply override

# ---------- Classifiers (aligned with Replit) ----------
def classify_nvda_pe(v):
    # <40 green, 40–55 amber, >55 red
    return "Green" if v < 40 else "Amber" if v <= 55 else "Red"

def classify_vix(v):
    # <20 green, 20–25 amber, >25 red
    return "Green" if v < 20 else "Amber" if v <= 25 else "Red"

def classify_yield_spread(v, threshold):
    # Red only if >= threshold; else Amber (no Green), like Replit
    if v is None:
        return "Amber"
    return "Red" if v >= threshold else "Amber"

def classify_ai_flows(s):
    return "Green" if s == "Inflows" else "Red"

def classify_cn_us(s):
    # Default Amber unless clearly stable
    return "Amber" if s.lower() != "stable" else "Green"

def classify_critical(s):
    return "Amber" if s.lower() != "stable" else "Green"

def classify_ukr(s):
    return "Amber" if s.lower() != "stable" else "Green"

def classify_def_spend_trend(v):
    # If sustained >+20% YoY we'd worry; proxy is monthly -> simple rule
    return "Green" if v < 20 else "Red"

def classify_usd_share(v):
    return "Green" if v >= 57 else "Red"

# ---------- Build the canonical 10-signal table ----------
rows = [
    ["NVIDIA P/E ratio", data["nvda_pe"], classify_nvda_pe(data["nvda_pe"])],
    ["Hyperscaler Datacenter CapEx growth", f"{data['capex_growth']}%", "Green" if data["capex_growth"] > 10 else "Amber"],
    ["Yield-curve slope (10Y–2Y)", data["yield_spread"], classify_yield_spread(data["yield_spread"], data["yield_red_threshold"])],
    ["VIX (Volatility Index)", data["vix"], classify_vix(data["vix"])],
    ["AI/Tech ETF fund flows", data["ai_flows"], classify_ai_flows(data["ai_flows"])],
    ["China–US tension", data["cn_us_tension"], classify_cn_us(data["cn_us_tension"])],
    ["Critical resources restrictions", data["critical_resources"], classify_critical(data["critical_resources"])],
    ["Ukraine / Europe escalation", data["ukraine_europe"], classify_ukr(data["ukraine_europe"])],
    ["Global defense spending (proxy: ITA trend %/mo)", f"{data['def_spend_trend']}%", classify_def_spend_trend(data["def_spend_trend"])],
    ["USD reserve share", f"{data['usd_share']}%", classify_usd_share(data["usd_share"])],
]
signals = pd.DataFrame(rows, columns=["Signal", "Current", "Status"])

# ---------- Load last snapshot for diffs ----------
last = load_last_snapshot()
last_prob = last.get("crash_probability")
last_statuses = last.get("statuses", {})

# Add last status + change markers
def change_marker(prev, curr):
    if prev is None:
        return "•"
    if prev == curr:
        return "•"
    # Worsening if moving toward Red; improving otherwise
    order = {"Green": 0, "Amber": 1, "Red": 2}
    return "▲" if order.get(curr,1) > order.get(prev,1) else "▼"

signals["Last Status"] = [ last_statuses.get(s, None) for s in signals["Signal"] ]
signals["Change"] = [ change_marker(p, c) for p, c in zip(signals["Last Status"], signals["Status"]) ]

# ---------- Crash probability (same formula as before) ----------
num_amber = int((signals["Status"] == "Amber").sum())
num_red = int((signals["Status"] == "Red").sum())
crash_prob = min(10 + num_amber * 5 + num_red * 10, 100)

# ---------- Top alert/banner ----------
delta_label = ""
if last_prob is not None:
    delta = crash_prob - float(last_prob)
    arrow = "↑" if delta > 0 else "↓" if delta < 0 else "→"
    delta_label = f" (Prev {last_prob:.0f}% {arrow} {abs(delta):.0f}pp)"
if crash_prob >= CRITICAL_THRESHOLD:
    st.error(f"🚨 **CRITICAL RISK — Crash Probability {crash_prob}%**{delta_label} — **ACTION REQUIRED**")
else:
    st.success(f"✅ System Stable — Crash Probability {crash_prob}%{delta_label}")

# ---------- Table (traffic-light colors) ----------
color_map = {"Green": "#00b050", "Amber": "#ffc000", "Red": "#c00000"}
styled = signals.style.applymap(lambda s: f"color:{color_map.get(s, 'black')}", subset=["Status"]) \
                      .applymap(lambda s: f"color:{color_map.get(s, 'black')}", subset=["Last Status"]) \
                      .applymap(lambda s: "font-weight:bold", subset=["Change"])
st.dataframe(styled, use_container_width=True)

# ---------- Persist current snapshot + history ----------
today = datetime.date.today().isoformat()
hist = dedup_append_history(today, crash_prob)
# Save current statuses for next run comparison
save_last_snapshot(crash_prob, {row["Signal"]: row["Status"] for _, row in signals.iterrows()})

# ---------- Trend ----------
st.subheader("📈 Crash-Probability Trend")
st.line_chart(hist.set_index("date"))

st.caption(
    f"Last updated {today} | Live sources where feasible: Yahoo Finance, FRED (CSV), "
    f"IMF (scrape), ETF.com, Google News. Yield Red threshold = {data['yield_red_threshold']:.2f}%"
)
