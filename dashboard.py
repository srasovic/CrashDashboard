# ============================================================
# 🌍 AI + Global Risk Dashboard (Strict LIVE, No Silent Fallbacks, With Diffs)
# ============================================================
import streamlit as st
import pandas as pd
import yfinance as yf
import datetime, requests, re, os, json
from typing import Optional

HISTORY_FILE = "crash_history.csv"
LAST_FILE = "last_snapshot.json"
CRITICAL_THRESHOLD = 50        # % => red banner
CACHE_TTL = 900                # 15 min cache
YIELD_RED_THRESHOLD = 0.50     # % (10y–2y) => Red only if >= this
USE_YIELD_5D_AVG = True        # smooth flickers

st.set_page_config(page_title="AI + Global Risk Dashboard", layout="wide")
st.title("🌍 AI + Global Risk Dashboard — Strict LIVE Mode")

# ----------------- Helpers -----------------
def safe_float_last(x) -> Optional[float]:
    try:
        if isinstance(x, pd.Series):
            x = x.dropna()
            if len(x) == 0: return None
            x = x.iloc[-1]
        return round(float(x), 2)
    except Exception:
        return None

def load_last_snapshot():
    if os.path.exists(LAST_FILE):
        with open(LAST_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"crash_probability": None, "statuses": {}}

def save_last_snapshot(crash_prob, status_map):
    with open(LAST_FILE, "w", encoding="utf-8") as f:
        json.dump({"crash_probability": crash_prob, "statuses": status_map}, f)

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

# ----------------- Sidebar -----------------
with st.sidebar:
    st.markdown("### ⚙️ Controls")
    force_refresh = st.button("🔄 Refresh now (clear cache & re-pull)")
    st.caption("Use this whenever you want to force a 100% live refresh.")
    yield_threshold = st.slider("Yield Red threshold (10y–2y, %)", 0.10, 1.00, YIELD_RED_THRESHOLD, 0.05)
    use_yield_avg = st.checkbox("Use 5-day average for yield", value=USE_YIELD_5D_AVG)
    manual_capex = st.slider("Override Hyperscaler CapEx growth (%)", 0, 50, 35)
    st.caption("No stable free feed for CapEx yet; override if you have a number.")

if force_refresh:
    st.cache_data.clear()

# ----------------- Live fetch (cached) -----------------
@st.cache_data(ttl=CACHE_TTL)
def fetch_live(yield_red: float, use_yield_avg: bool):
    audit = {}  # raw values for debug panel

    # NVDA P/E = latest close / trailing EPS
    try:
        t = yf.Ticker("NVDA")
        # price: last close from 2-day window (fallback to last available)
        px_series = t.history(period="2d")["Close"].dropna()
        price = safe_float_last(px_series)
        # trailing EPS: Yahoo info
        eps = t.fast_info.get("trailing_eps", None)
        if eps is None:
            info = t.info  # may be slow but more likely to have trailingEps
            eps = info.get("trailingEps", None)
        eps = safe_float_last(eps)
        nvda_pe = round(price / eps, 2) if (price is not None and eps and eps != 0) else None
        audit["NVDA_price"] = price
        audit["NVDA_trailingEPS"] = eps
        audit["NVDA_PE_calc"] = nvda_pe
    except Exception:
        nvda_pe = None

    # VIX last close
    try:
        vix = yf.download("^VIX", period="5d", progress=False)["Close"]
        vix_val = safe_float_last(vix)
        audit["VIX_series_tail"] = vix.tail(3).to_dict()
    except Exception:
        vix_val = None

    # Yield 10y–2y from FRED CSV
    try:
        fred = pd.read_csv("https://fred.stlouisfed.org/graph/fredgraph.csv?id=T10Y2Y")
        s = fred["T10Y2Y"].dropna()
        y_now = safe_float_last(s)
        y_avg = safe_float_last(s.tail(5).mean()) if len(s) >= 5 else y_now
        yield_spread = y_avg if use_yield_avg else y_now
        audit["Yield_last"] = y_now
        audit["Yield_5d_avg"] = y_avg
        audit["Yield_used"] = yield_spread
    except Exception:
        yield_spread = None

    # AI ETF flows cue (very rough heuristic)
    try:
        page = requests.get("https://www.etf.com/channels/artificial-intelligence-etfs", timeout=15).text.lower()
        ai_flows = "Inflows" if "inflows" in page else "Outflows" if "outflows" in page else "Unknown"
        audit["ETF_com_snippet_has_inflows"] = "inflows" in page
        audit["ETF_com_snippet_has_outflows"] = "outflows" in page
    except Exception:
        ai_flows = "Unknown"

    # China–US tension cue (headlines heuristic)
    try:
        rss = requests.get("https://news.google.com/rss/search?q=china+us+tension", timeout=10).text.lower()
        cn_us_tension = "Tightened" if any(k in rss for k in ["tension", "sanction", "export control"]) else "Stable"
        audit["CN_US_news_has_tension_keywords"] = any(k in rss for k in ["tension","sanction","export control"])
    except Exception:
        cn_us_tension = "Unknown"

    # Critical resources cue (headlines heuristic)
    try:
        rss2 = requests.get("https://news.google.com/rss/search?q=rare+earth+export+controls+graphite+restrictions", timeout=10).text.lower()
        critical_resources = "Tightened" if any(k in rss2 for k in ["control", "ban", "restriction"]) else "Stable"
        audit["Critical_news_has_restrict_keywords"] = any(k in rss2 for k in ["control","ban","restriction"])
    except Exception:
        critical_resources = "Unknown"

    # Ukraine/Europe cue (headlines heuristic)
    try:
        rss3 = requests.get("https://news.google.com/rss/search?q=ukraine+europe+tension+nato+incident", timeout=10).text.lower()
        ukraine_europe = "Tense" if any(k in rss3 for k in ["tension", "escalation", "incident"]) else "Stable"
        audit["Ukraine_news_has_tension_keywords"] = any(k in rss3 for k in ["tension","escalation","incident"])
    except Exception:
        ukraine_europe = "Unknown"

    # Defense-spend proxy (ITA monthly change)
    try:
        ita = yf.download("ITA", period="1mo", progress=False)["Close"].dropna()
        def_spend_trend = safe_float_last(((ita.iloc[-1] - ita.iloc[0]) / ita.iloc[0]) * 100)
        audit["ITA_first_last"] = {"first": safe_float_last(ita.iloc[0]), "last": safe_float_last(ita.iloc[-1])}
    except Exception:
        def_spend_trend = None

    # USD reserve share (IMF COFER scrape; if not parsable -> Unknown)
    try:
        html = requests.get("https://data.imf.org/regular.aspx?key=41175", timeout=15).text
        m = re.search(r"US DOLLAR.*?(\d{1,2}\.\d)", html, re.I | re.S)
        usd_share = safe_float_last(m.group(1)) if m else None
        audit["USD_share_raw_match"] = m.group(1) if m else None
    except Exception:
        usd_share = None

    return {
        "nvda_pe": nvda_pe,
        "capex_growth": float(manual_capex),   # from sidebar
        "yield_spread": yield_spread,
        "yield_red_threshold": yield_red,
        "vix": vix_val,
        "ai_flows": ai_flows,
        "cn_us_tension": cn_us_tension,
        "critical_resources": critical_resources,
        "ukraine_europe": ukraine_europe,
        "def_spend_trend": def_spend_trend,
        "usd_share": usd_share,
        "audit": audit,
    }

data = fetch_live(yield_threshold, use_yield_avg)

# ----------------- Classifiers (identical to Replit rules) -----------------
def classify_nvda_pe(v):
    if v is None: return "Unknown"
    return "Green" if v < 40 else "Amber" if v <= 55 else "Red"

def classify_vix(v):
    if v is None: return "Unknown"
    return "Green" if v < 20 else "Amber" if v <= 25 else "Red"

def classify_yield(v, threshold):
    if v is None: return "Unknown"
    return "Red" if v >= threshold else "Amber"   # no Green

def classify_ai_flows(s):
    if s == "Unknown": return "Unknown"
    return "Green" if s == "Inflows" else "Red"

def classify_text_amber_stable(s):
    if s == "Unknown": return "Unknown"
    return "Green" if s.lower() == "stable" else "Amber"

def classify_def_spend(v):
    if v is None: return "Unknown"
    return "Green" if v < 20 else "Red"

def classify_usd_share(v):
    if v is None: return "Unknown"
    return "Green" if v >= 57 else "Red"

rows = [
    ["NVIDIA P/E ratio", data["nvda_pe"], classify_nvda_pe(data["nvda_pe"])],
    ["Hyperscaler Datacenter CapEx growth", f"{data['capex_growth']}%", "Green" if data["capex_growth"] > 10 else "Amber"],
    ["Yield-curve slope (10Y–2Y)", data["yield_spread"], classify_yield(data["yield_spread"], data["yield_red_threshold"])],
    ["VIX (Volatility Index)", data["vix"], classify_vix(data["vix"])],
    ["AI/Tech ETF fund flows", data["ai_flows"], classify_ai_flows(data["ai_flows"])],
    ["China–US tension", data["cn_us_tension"], classify_text_amber_stable(data["cn_us_tension"])],
    ["Critical resources restrictions", data["critical_resources"], classify_text_amber_stable(data["critical_resources"])],
    ["Ukraine / Europe escalation", data["ukraine_europe"], classify_text_amber_stable(data["ukraine_europe"])],
    ["Global defense spending (proxy: ITA monthly %)", data["def_spend_trend"], classify_def_spend(data["def_spend_trend"])],
    ["USD reserve share", data["usd_share"], classify_usd_share(data["usd_share"])],
]
signals = pd.DataFrame(rows, columns=["Signal","Current","Status"])

# ----------------- Last run diffs -----------------
last = load_last_snapshot()
last_prob = last.get("crash_probability")
last_map = last.get("statuses", {})

def change_marker(prev, curr):
    if prev is None or prev == "Unknown": return "•"
    if curr == "Unknown": return "•"
    order = {"Green":0, "Amber":1, "Red":2}
    if order.get(curr,1) > order.get(prev,1): return "▲"
    if order.get(curr,1) < order.get(prev,1): return "▼"
    return "•"

signals["Last Status"] = [ last_map.get(s, None) for s in signals["Signal"] ]
signals["Change"] = [ change_marker(p, c) for p, c in zip(signals["Last Status"], signals["Status"]) ]

# ----------------- Crash probability (exclude Unknown, then scale) -----------------
known = signals[signals["Status"] != "Unknown"]
amber = (known["Status"] == "Amber").sum()
red   = (known["Status"] == "Red").sum()
raw_score = 10 + amber*5 + red*10

# Scale score to full 10-signal basis so results are comparable if some are Unknown
scale = 10 / max(1, len(known))
crash_prob = min(int(round(raw_score * scale)), 100)

# ----------------- Top banner with deltas -----------------
improved = (signals["Change"] == "▼").sum()
worsened = (signals["Change"] == "▲").sum()
movement = f" ({improved} improved, {worsened} worsened)" if (improved or worsened) else ""

delta_label = ""
if last_prob is not None:
    d = crash_prob - int(round(float(last_prob)))
    arrow = "↑" if d > 0 else "↓" if d < 0 else "→"
    delta_label = f" (Prev {int(round(float(last_prob)))}% {arrow} {abs(d)}pp){movement}"
else:
    delta_label = movement

if crash_prob >= CRITICAL_THRESHOLD:
    st.error(f"🚨 **CRITICAL RISK — Crash Probability {crash_prob}%**{delta_label} — **ACTION REQUIRED**")
else:
    st.success(f"✅ System Stable — Crash Probability {crash_prob}%{delta_label}")

# ----------------- Table w/ colors -----------------
color_map = {"Green":"#00b050","Amber":"#ffc000","Red":"#c00000","Unknown":"#808080"}
styled = (signals.style
    .applymap(lambda s: f"color:{color_map.get(s,'black')}", subset=["Status"])
    .applymap(lambda s: f"color:{color_map.get(s,'black')}", subset=["Last Status"])
    .applymap(lambda s: "font-weight:bold", subset=["Change"])
)
st.dataframe(styled, use_container_width=True)

# ----------------- Persist snapshot & history -----------------
today = datetime.date.today().isoformat()
hist = dedup_append_history(today, crash_prob)
save_last_snapshot(crash_prob, {r["Signal"]: r["Status"] for _, r in signals.iterrows()})

# ----------------- Trend -----------------
st.subheader("📈 Crash-Probability Trend")
st.line_chart(hist.set_index("date"))

# ----------------- Debug / Audit panel -----------------
with st.expander("🛠 Debug / Audit (raw values)"):
    st.json(data["audit"])
    st.write("Known signals in score:", len(known), "/ 10")
    st.write("Amber:", int(amber), "Red:", int(red), "Raw score:", raw_score, "Scale:", round(scale,2))
    st.dataframe(signals, use_container_width=True)

st.caption(
    f"Last updated {today} | Live sources (Yahoo Finance, FRED CSV, IMF scrape, ETF.com, news cues). "
    f"Yield threshold={yield_threshold:.2f}%. Cache={CACHE_TTL}s. Use 'Refresh now' for a fresh pull."
)
