import os, json, hashlib, html
from datetime import datetime, timezone

import requests
from requests_oauthlib import OAuth1Session

OUT_DIR = "out"
TWEET_FILE = os.path.join(OUT_DIR, "tweet.txt")
STATE_FILE = os.path.join(OUT_DIR, "last_post.json")

X_POST_URL = "https://api.x.com/2/tweets"

SITE_URL = "https://protocolwpo.github.io/WPO/"
FORM_URL = "https://protocolwpo.github.io/WPO/#submit"

# ثابتة دائمًا (خليها قليلة لتجنب spam signals)
FIXED_HASHTAGS = ["#ProtocolWPO", "#WPO", "#CryptoNews"]

# Hooks (يتغيّر تلقائيًا كل 4 ساعات)
HOOKS = [
    "🚨 Don’t trade blind. Verify first.",
    "⚠️ Hype fades. On-chain facts stay.",
    "🔎 Before you buy, check the moves + news.",
    "🧭 Fast market. Smarter evidence.",
    "🛡️ Protect capital: verify, then trade.",
    "📉 Pumps happen. Proof matters more.",
]

# سطر إضافي بلغة متغيّرة (Chinese / Indonesian / Arabic)
EXTRA_LINES = [
    "举报骗局/可疑钱包（基于证据）：",                      # Chinese
    "Laporkan scam/dompet mencurigakan (berbasis bukti):",   # Indonesian
    "بلّغ عن الاحتيال/المحافظ المشبوهة (بالأدلة):",         # Arabic
]

# -------------------------
# Helpers
# -------------------------
def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_state(state):
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def fmt_pct(x):
    if x is None:
        return "n/a"
    sign = "+" if x >= 0 else ""
    return f"{sign}{x:.1f}%"

def shorten(s: str, max_len: int) -> str:
    s = " ".join((s or "").split())
    if len(s) <= max_len:
        return s
    return s[: max(0, max_len - 1)].rstrip() + "…"

# -------------------------
# CoinMarketCap (Price + News)
# -------------------------
CMC_BASE = "https://pro-api.coinmarketcap.com"

def cmc_get(path: str, params: dict | None = None):
    cmc_key = os.getenv("CMC_KEY")
    if not cmc_key:
        return None
    url = f"{CMC_BASE}{path}"
    headers = {
        "X-CMC_PRO_API_KEY": cmc_key,
        "Accept": "application/json",
        "User-Agent": "WPO-bot/1.0",
    }
    r = requests.get(url, headers=headers, params=params or {}, timeout=30)

    # بعض الخطط لا تدعم content/latest أو ممكن rate limit
    if r.status_code in (401, 403, 429):
        return None

    r.raise_for_status()
    return r.json()

def fetch_cmc_quotes(symbols=("BTC", "ETH")):
    """
    Uses CoinMarketCap quotes/latest (v2).
    Returns dict: { "BTC": {"price":..., "pct24":...}, "ETH": {...} }
    """
    j = cmc_get("/v2/cryptocurrency/quotes/latest", {
        "symbol": ",".join(symbols),
        "convert": "USD",
    })
    if not j or "data" not in j:
        return {}

    out = {}
    data = j["data"]
    for sym in symbols:
        arr = data.get(sym)
        if not arr:
            continue
        obj = arr[0] if isinstance(arr, list) and arr else arr
        q = obj.get("quote", {}).get("USD", {})
        out[sym] = {
            "price": q.get("price"),
            "pct24": q.get("percent_change_24h"),
        }
    return out

def fetch_cmc_latest_news(limit=5):
    """
    Fetches latest CMC content/news.
    Returns list of tuples: (source, title, url, id)
    """
    j = cmc_get("/v1/content/latest", {
        "start": 1,
        "limit": limit,
        "sort": "published_at",
        "sort_dir": "desc",
    })
    if not j or "data" not in j:
        return []

    out = []
    for it in j["data"]:
        title = (it.get("title") or "").strip()
        url = (it.get("url") or "").strip()
        src = (it.get("source_name") or it.get("sourceName") or "CMC").strip()
        nid = it.get("id") or sha((title + url)[:200])
        if title and url:
            out.append((src, html.unescape(title), url, str(nid)))
    return out

# -------------------------
# X Posting
# -------------------------
def post_to_x(text: str):
    for k in ["X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET"]:
        if not os.getenv(k):
            raise SystemExit(f"Missing secret: {k}")

    oauth = OAuth1Session(
        client_key=os.getenv("X_API_KEY"),
        client_secret=os.getenv("X_API_SECRET"),
        resource_owner_key=os.getenv("X_ACCESS_TOKEN"),
        resource_owner_secret=os.getenv("X_ACCESS_TOKEN_SECRET"),
    )

    r = oauth.post(X_POST_URL, json={"text": text}, timeout=30)
    if r.status_code not in (200, 201):
        raise SystemExit(f"X post failed: {r.status_code} {r.text}")
    return r.json()

# -------------------------
# Tweet Builder (<= 280 chars)
# -------------------------
LANGS = ["EN", "AR", "ZH", "ID"]

TEMPLATES = {
    "EN": [
        "{hook} BTC {btc} ({btcchg}) • ETH {eth} ({ethchg}). Headline: {news} {cta} {tags}",
        "Market pulse: BTC {btc} {btcchg} | ETH {eth} {ethchg}. {news} {cta} {tags}",
    ],
    "AR": [
        "{hook} BTC {btc} ({btcchg}) | ETH {eth} ({ethchg}). آخر خبر: {news} {cta} {tags}",
        "نبض السوق: BTC {btc} {btcchg} • ETH {eth} {ethchg}. خبر CMC: {news} {cta} {tags}",
    ],
    "ZH": [
        "{hook} BTC {btc}（{btcchg}）/ ETH {eth}（{ethchg}）。最新：{news} {cta} {tags}",
        "市场：BTC {btc} {btcchg}｜ETH {eth} {ethchg}。新闻：{news} {cta} {tags}",
    ],
    "ID": [
        "{hook} BTC {btc} ({btcchg}) • ETH {eth} ({ethchg}). Berita: {news} {cta} {tags}",
        "Pulse: BTC {btc} {btcchg} | ETH {eth} {ethchg}. Headline: {news} {cta} {tags}",
    ],
}

def build_tweet():
    now_dt = datetime.now(timezone.utc)
    slot = (now_dt.hour // 4)

    hook = HOOKS[slot % len(HOOKS)]
    extra_line = EXTRA_LINES[slot % len(EXTRA_LINES)]

    lang = LANGS[slot % len(LANGS)]
    tpl_list = TEMPLATES[lang]
    tpl = tpl_list[slot % len(tpl_list)]

    # Price quotes (CMC)
    q = fetch_cmc_quotes(("BTC", "ETH"))
    btc_p = q.get("BTC", {}).get("price")
    btc_c = q.get("BTC", {}).get("pct24")
    eth_p = q.get("ETH", {}).get("price")
    eth_c = q.get("ETH", {}).get("pct24")

    btc = f"${btc_p:,.0f}" if isinstance(btc_p, (int, float)) else "n/a"
    eth = f"${eth_p:,.0f}" if isinstance(eth_p, (int, float)) else "n/a"
    btcchg = fmt_pct(btc_c) if isinstance(btc_c, (int, float)) else "n/a"
    ethchg = fmt_pct(eth_c) if isinstance(eth_c, (int, float)) else "n/a"

    # News (CMC)
    state = load_state()
    used_ids = set(state.get("news_ids", []))

    news_items = fetch_cmc_latest_news(limit=6)

    chosen = None
    for src, title, url, nid in news_items:
        if nid not in used_ids:
            chosen = (src, title, url, nid)
            break
    if not chosen and news_items:
        chosen = news_items[0]

    if chosen:
        src, title, url, nid = chosen
        # عنوان + رابط الخبر (قص قوي لتفادي 280)
        news_title = shorten(title, 64)
        news = f"{src}: {news_title} {url}"
    else:
        news = "No CMC news available"

    tags = " ".join(FIXED_HASHTAGS)

    # CTA (سطر واحد فقط لتجنب الطول)
    cta = f"{FORM_URL}"

    tweet = tpl.format(
        hook=hook,
        btc=btc, btcchg=btcchg,
        eth=eth, ethchg=ethchg,
        news=news,
        cta=cta,
        tags=tags,
    )

    # إضافة السطر المتغيّر بشرط ما يكسر 280
    extra = f"{extra_line} {FORM_URL}"
    if len(tweet) + 1 + len(extra) <= 280:
        tweet = tweet + "\n" + extra

    # قص ذكي لو تعدى 280
    if len(tweet) > 280 and chosen:
        # قلل عنوان الخبر
        tweet = tweet.replace(shorten(chosen[1], 64), shorten(chosen[1], 45))
    if len(tweet) > 280:
        # قلل الهاشتاقات
        tweet = tweet.replace(tags, "#WPO #CryptoNews")
    if len(tweet) > 280:
        tweet = shorten(tweet, 280)

    # حفظ خبر مستخدم لمنع التكرار
    if chosen:
        ids = state.get("news_ids", [])
        ids.append(chosen[3])
        state["news_ids"] = ids[-50:]
        save_state(state)

    return tweet

def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    tweet = build_tweet()

    with open(TWEET_FILE, "w", encoding="utf-8") as f:
        f.write(tweet)

    state = load_state()
    h = sha(tweet)

    # منع تكرار نفس التغريدة
    if state.get("last_hash") == h:
        print("Same content as last post — skipping.")
        return

    resp = post_to_x(tweet)
    tweet_id = resp.get("data", {}).get("id")

    state.update({
        "last_hash": h,
        "last_tweet_id": tweet_id,
        "last_text": tweet,
        "posted_at_utc": datetime.now(timezone.utc).isoformat()
    })
    save_state(state)

    print("Posted to X. id=", tweet_id)

if __name__ == "__main__":
    main()
