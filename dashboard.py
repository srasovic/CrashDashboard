# ============================================================
# 🌍 AI + Global Risk Dashboard
# Identical logic to Replit version, safe I/O, consistent results
# ============================================================
import streamlit as st
import pandas as pd
import yfinance as yf
import datetime, requests, os, json

# ---------- CONFIG ----------
HISTORY_FILE = "crash_history.csv"
LAST_FILE = "last_snapshot.json"
CRITICAL_THRESHOLD = 50        # % threshold for red alert
CACHE_TTL = 900                # 15 minutes
YIELD_RED_THRESHOLD = 0.50     # 10Y–2Y threshold for Red

st.set_page_config(page_title="AI + Global Risk Dashboard", layout="wide")
st.title("🌍 AI + Global Risk Dashboard")

# ---------- UTILS ----------
def safe_float(x):
    """Convert safely to float or return None."""
    try:
        if isinstance(x, pd.Series):
            x = x.dropna()
            if len(x) == 0: return None
            x = x.iloc[-1]
        return round(float(x), 2)
    except Exception:
        return None

def safe_load_json(path):
    """Safe JSON read: returns empty default if file broken."""
    if not os.path.exists(path):
        return {"crash_probability": None, "statuses": {}}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        # corrupt or empty file → reset
        return {"crash_probability": None, "statuses": {}}

def safe_save_json(path, data):
    """Safe JSON write."""
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception as e:
        st.warning(f"⚠️ Could not save snapshot: {e}")

def append_history(date_str, prob):
    """Append to history CSV safely."""
    new = pd.DataFrame([[date_str, prob]], columns=["date", "crash_probability"])
    if os.path.exists(HISTORY_FILE):
        try:
            hist = pd.read_csv(HISTORY_FILE)
        except Exception:
            hist = pd.DataFrame(columns=["date", "crash_probability"])
        hist = hist[hist["date"] != date_str]
        hist = pd.concat([hist, new], ignore_index=True)
    else:
        hist = new
    hist.to_csv(HISTORY_FILE, index=False)
    return hist

# ---------- SIDEBAR ----------
with st.sidebar:
    st.markdown("### ⚙️ Controls")
    force = st.button("🔄 Refresh now (clear cache)")
    st.caption("Forces full live re-fetch (Yahoo, FRED, ETF.com).")
    manual_capex = st.slider("Hyperscaler CapEx growth (%)", 0, 50, 35)
    st.caption("Default 35%. Only change if new data available.")
    man_china_us = st.selectbox("China–US tension", ["Amber", "Green", "Red"], index=0)
    man_critical = st.selectbox("Critical resources restrictions", ["Amber", "Green", "Red"], index=0)
    man_ukraine = st.selectbox("Ukraine / Europe escalation", ["Amber", "Green", "Red"], index=0)

if force:
    st.cache_data.clear()

# ---------- FETCH LIVE ----------
@st.cache_data(ttl=CACHE_TTL)
def fetch_live(capex_default):
    # 1️⃣ NVIDIA P/E (exactly like Replit: trailingPE)
    try:
        nvda = yf.Ticker("NVDA")
        nvda_pe = nvda.info.get("trailingPE", None)
        nvda_pe = round(float(nvda_pe), 2) if nvda_pe else None
    except Exception:
        nvda_pe = None

    # 2️⃣ Hyperscaler CapEx (manual)
    capex_growth = float(capex_default)

    # 3️⃣ Yield curve (10Y–2Y)
    try:
        fred = pd.read_csv("https://fred.stlouisfed.org/graph/fredgraph.csv?id=T10Y2Y")
        yield_spread = safe_float(fred["T10Y2Y"])
    except Exception:
        yield_spread = None

    # 4️⃣ VIX
    try:
        vix = yf.download("^VIX", period="5d", progress=False)["Close"].dropna()
        vix_val = safe_float(vix)
    except Exception:
        vix_val = None

    # 5️⃣ AI ETF flows
    try:
        page = requests.get("https://www.etf.com/channels/artificial-intelligence-etfs", timeout=12).text.lower()
        ai_flows = "Inflows" if "inflows" in page else "Outflows" if "outflows" in page else "Inflows"
    except Exception:
        ai_flows = "Inflows"

    # 9️⃣ Defense spending (ITA)
    try:
        ita = yf.download("ITA", period="1mo", progress=False)["Close"].dropna()
        def_spend = round(((ita.iloc[-1] - ita.iloc[0]) / ita.iloc[0]) * 100, 2)
    except Exception:
        def_spend = 12.0

    # 🔟 USD reserve share (static fallback)
    usd_share = 58.0

    return {
        "nvda_pe": nvda_pe,
        "capex_growth": capex_growth,
        "yield_spread": yield_spread,
        "vix": vix_val,
        "ai_flows": ai_flows,
        "def_spend_trend": def_spend,
        "usd_share": usd_share,
    }

data = fetch_live(manual_capex)

# ---------- CLASSIFIERS (identical to Replit logic) ----------
def c_nvda(v):
    if v is None: return "Amber"
    return "Green" if v < 40 else "Amber" if v <= 55 else "Red"

def c_capex(v): return "Green" if v > 10 else "Amber"
def c_yield(v):
    if v is None: return "Amber"
    return "Red" if v >= YIELD_RED_THRESHOLD else "Amber"
def c_vix(v):
    if v is None: return "Amber"
    return "Green" if v < 20 else "Amber" if v <= 25 else "Red"
def c_ai(v): return "Green" if v == "Inflows" else "Red"
def c_fixed(v): return v  # manual from sidebar
def c_def(v):
    try:
        v = float(v)
    except Exception:
        return "Green"
    return "Green" if v < 20 else "Red"
def c_usd(v): return "Green" if v >= 57 else "Red"

# ---------- SIGNALS ----------
signals = pd.DataFrame([
    ["NVIDIA P/E ratio", data["nvda_pe"], c_nvda(data["nvda_pe"])],
    ["Hyperscaler Datacenter CapEx growth", f"{data['capex_growth']}%", c_capex(data["capex_growth"])],
    ["Yield-curve slope (10Y–2Y)", data["yield_spread"], c_yield(data["yield_spread"])],
    ["VIX (Volatility Index)", data["vix"], c_vix(data["vix"])],
    ["AI/Tech ETF fund flows", data["ai_flows"], c_ai(data["ai_flows"])],
    ["China–US tension", man_china_us, man_china_us],
    ["Critical resources restrictions", man_critical, man_critical],
    ["Ukraine / Europe escalation", man_ukraine, man_ukraine],
    ["Global defense spending (proxy: ITA %/mo)", f"{data['def_spend_trend']}%", c_def(data["def_spend_trend"])],
    ["USD reserve share", f"{data['usd_share']}%", c_usd(data["usd_share"])],
], columns=["Signal", "Current", "Status"])

# ---------- SCORING ----------
amb = (signals["Status"] == "Amber").sum()
red = (signals["Status"] == "Red").sum()
crash_prob = min(10 + amb*5 + red*10, 100)

# ---------- LAST SNAPSHOT ----------
last = safe_load_json(LAST_FILE)
last_prob = last.get("crash_probability")
last_map = last.get("statuses", {})

def mark(prev, curr):
    order = {"Green":0, "Amber":1, "Red":2}
    if prev not in order or curr not in order: return "•"
    if order[curr] > order[prev]: return "▲"
    if order[curr] < order[prev]: return "▼"
    return "•"

signals["Last Status"] = [last_map.get(s, None) for s in signals["Signal"]]
signals["Change"] = [mark(p, c) for p, c in zip(signals["Last Status"], signals["Status"])]

# ---------- HEADER ----------
delta_txt = ""
if last_prob is not None:
    diff = crash_prob - int(round(float(last_prob)))
    arrow = "↑" if diff > 0 else "↓" if diff < 0 else "→"
    delta_txt = f" (Prev {int(round(float(last_prob)))}% {arrow} {abs(diff)}pp)"

if crash_prob >= CRITICAL_THRESHOLD:
    st.error(f"🚨 **CRITICAL RISK — Crash Probability {crash_prob}%**{delta_txt} — **ACTION REQUIRED**")
else:
    st.success(f"✅ System Stable — Crash Probability {crash_prob}%{delta_txt}")

# ---------- TABLE ----------
color_map = {"Green":"#00b050","Amber":"#ffc000","Red":"#c00000"}
st.dataframe(
    signals.style
    .applymap(lambda s: f"color:{color_map.get(s,'black')}", subset=["Status"])
    .applymap(lambda s: f"color:{color_map.get(s,'black')}", subset=["Last Status"])
    .applymap(lambda s: "font-weight:bold", subset=["Change"]),
    use_container_width=True
)

# ---------- SAVE & HISTORY (fixed state sync + serialization) ----------

today = datetime.date.today().isoformat()

# Force cache clear so that next run reloads updated "Last Status"
st.cache_data.clear()

# Append new entry and re-read to refresh chart
hist = append_history(today, int(crash_prob))
try:
    hist = pd.read_csv(HISTORY_FILE)
except Exception:
    hist = pd.DataFrame(columns=["date", "crash_probability"])

# Convert crash_prob to plain int for JSON serialization
try:
    safe_save_json(
        LAST_FILE,
        {
            "crash_probability": int(crash_prob),
            "statuses": {
                str(r["Signal"]): str(r["Status"]) for _, r in signals.iterrows()
            },
        },
    )
except Exception as e:
    st.warning(f"⚠️ Could not save snapshot (serialization): {e}")

# ---------- TREND (always live) ----------
st.subheader("📈 Crash-Probability Trend")

# Always reload from file to avoid cached dataframe
try:
    latest_hist = pd.read_csv(HISTORY_FILE)
    latest_hist = latest_hist.drop_duplicates(subset=["date"], keep="last").sort_values("date")
except Exception:
    latest_hist = pd.DataFrame(columns=["date", "crash_probability"])

if not latest_hist.empty:
    st.line_chart(latest_hist.set_index("date"))
else:
    st.info("No history yet — refresh once to start tracking trend.")
