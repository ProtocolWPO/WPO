import os, json, hashlib, html
from datetime import datetime, timezone
import xml.etree.ElementTree as ET

import requests
from requests_oauthlib import OAuth1Session

OUT_DIR = "out"
TWEET_FILE = os.path.join(OUT_DIR, "tweet.txt")
STATE_FILE = os.path.join(OUT_DIR, "last_post.json")

X_POST_URL = "https://api.x.com/2/tweets"

SITE_URL = "https://protocolwpo.github.io/WPO/"
FORM_URL = "https://protocolwpo.github.io/WPO/#submit"

# ثابتة دائمًا
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

# RSS News feeds (latest headlines)
NEWS_FEEDS = [
    ("CD", "https://www.coindesk.com/arc/outboundfeeds/rss/?outputType=xml"),
    ("CT", "https://cointelegraph.com/rss"),
]

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

def hashtag_for_symbol(sym: str) -> str:
    sym = (sym or "").upper().strip()
    sym = "".join(ch for ch in sym if ch.isalnum())
    return f"#{sym}" if sym else ""

def shorten(s: str, max_len: int) -> str:
    s = " ".join((s or "").split())
    if len(s) <= max_len:
        return s
    return s[: max(0, max_len - 1)].rstrip() + "…"

# -------------------------
# NEWS (RSS)
# -------------------------
def fetch_rss_top_title(url: str) -> str | None:
    try:
        r = requests.get(url, timeout=20, headers={"User-Agent": "WPO-bot/1.0"})
        r.raise_for_status()
        root = ET.fromstring(r.content)

        # RSS: channel/item/title
        channel = root.find("channel")
        if channel is None:
            # Sometimes namespaces appear; try a fallback search
            for ch in root.iter():
                if ch.tag.endswith("channel"):
                    channel = ch
                    break
        if channel is None:
            return None

        item = None
        for it in channel:
            if it.tag.endswith("item"):
                item = it
                break
        if item is None:
            return None

        title = None
        for t in item:
            if t.tag.endswith("title"):
                title = t.text
                break
        if not title:
            return None

        return html.unescape(title).strip()
    except Exception:
        return None

def fetch_latest_headlines(max_items=2):
    headlines = []
    for tag, url in NEWS_FEEDS:
        title = fetch_rss_top_title(url)
        if title:
            headlines.append((tag, title))
        if len(headlines) >= max_items:
            break
    return headlines

# -------------------------
# MARKET DATA
# -------------------------
def fetch_market_snapshot():
    """
    Uses CMC if CMC_KEY exists; otherwise CoinGecko free.
    Returns: btc_price, btc_pct24, eth_price, eth_pct24, gainers(list), losers(list)
    Each mover: (symbol, pct24)
    """
    cmc_key = os.getenv("CMC_KEY")

    if cmc_key:
        url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest"
        headers = {"X-CMC_PRO_API_KEY": cmc_key}
        params = {
            "start": 1,
            "limit": 200,
            "convert": "USD",
            "sort": "volume_24h",
            "sort_dir": "desc",
        }
        r = requests.get(url, headers=headers, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()["data"]

        def find(sym):
            for c in data:
                if c.get("symbol") == sym:
                    q = c["quote"]["USD"]
                    return q.get("price"), q.get("percent_change_24h")
            return None, None

        btc_price, btc_pct = find("BTC")
        eth_price, eth_pct = find("ETH")

        top = data[:100]
        gainers = sorted(top, key=lambda c: (c["quote"]["USD"].get("percent_change_24h") or -999), reverse=True)[:3]
        losers  = sorted(top, key=lambda c: (c["quote"]["USD"].get("percent_change_24h") or 999))[:3]

        g = [(c["symbol"], c["quote"]["USD"].get("percent_change_24h")) for c in gainers]
        l = [(c["symbol"], c["quote"]["USD"].get("percent_change_24h")) for c in losers]
        return btc_price, btc_pct, eth_price, eth_pct, g, l

    # CoinGecko free
    price_url = "https://api.coingecko.com/api/v3/simple/price"
    price_params = {
        "ids": "bitcoin,ethereum",
        "vs_currencies": "usd",
        "include_24hr_change": "true"
    }
    r1 = requests.get(price_url, params=price_params, timeout=30)
    r1.raise_for_status()
    p = r1.json()
    btc_price = p["bitcoin"]["usd"]
    btc_pct = p["bitcoin"].get("usd_24h_change")
    eth_price = p["ethereum"]["usd"]
    eth_pct = p["ethereum"].get("usd_24h_change")

    markets_url = "https://api.coingecko.com/api/v3/coins/markets"
    markets_params = {
        "vs_currency": "usd",
        "order": "volume_desc",
        "per_page": 100,
        "page": 1,
        "price_change_percentage": "24h",
    }
    r2 = requests.get(markets_url, params=markets_params, timeout=30)
    r2.raise_for_status()
    m = r2.json()

    gainers = sorted(m, key=lambda x: (x.get("price_change_percentage_24h") or -999), reverse=True)[:3]
    losers  = sorted(m, key=lambda x: (x.get("price_change_percentage_24h") or 999))[:3]

    g = [(x.get("symbol", "").upper(), x.get("price_change_percentage_24h")) for x in gainers]
    l = [(x.get("symbol", "").upper(), x.get("price_change_percentage_24h")) for x in losers]
    return btc_price, btc_pct, eth_price, eth_pct, g, l

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

def build_tweet():
    now_dt = datetime.now(timezone.utc)
    now = now_dt.strftime("%Y-%m-%d %H:%M UTC")
    slot = (now_dt.hour // 4)

    hook = HOOKS[slot % len(HOOKS)]
    extra_line = EXTRA_LINES[slot % len(EXTRA_LINES)]

    btc_price, btc_pct, eth_price, eth_pct, gainers, losers = fetch_market_snapshot()
    headlines = fetch_latest_headlines(max_items=2)

    # هاشتاجات العملات المذكورة
    symbols = set(["BTC", "ETH"])
    symbols.update([s for s, _ in gainers if s])
    symbols.update([s for s, _ in losers if s])

    coin_tags = [hashtag_for_symbol(s) for s in sorted(symbols)]
    coin_tags = [t for t in coin_tags if t]

    def movers_line(prefix, arr):
        return prefix + " " + " | ".join([f"{sym} {fmt_pct(pct)}" for sym, pct in arr])

    def make_news_line(items, title_len=52):
        if not items:
            return None
        parts = [f"{tag}: {shorten(title, title_len)}" for tag, title in items]
        return "News: " + " | ".join(parts)

    # نبني نسخة “مضغوطة” من البداية لتضمن 280
    news_line = make_news_line(headlines, title_len=52)

    # جرّب نسخ متعددة لحد ما تدخل في 280
    for coin_tag_count, use_two_news, title_len in [
        (10, True, 52),
        (8, True, 46),
        (6, True, 42),
        (6, False, 50),
        (4, False, 44),
        (0, False, 44),
    ]:
        news_items = headlines[:2] if use_two_news else headlines[:1]
        news_line_try = make_news_line(news_items, title_len=title_len)

        hashtags_line = " ".join(FIXED_HASHTAGS + coin_tags[:coin_tag_count])

        lines = []
        lines.append(hook)
        lines.append(f"Snapshot • {now}")
        if btc_price is not None and btc_pct is not None:
            lines.append(f"BTC ${btc_price:,.0f} ({fmt_pct(btc_pct)})")
        if eth_price is not None and eth_pct is not None:
            lines.append(f"ETH ${eth_price:,.0f} ({fmt_pct(eth_pct)})")

        lines.append("Movers 24h:")
        lines.append(movers_line("▲", gainers))
        lines.append(movers_line("▼", losers))

        if news_line_try:
            lines.append(news_line_try)

        # CTA + سطر اللغة المتغيّرة
        lines.append(f"Report (proof): {FORM_URL}")
        lines.append(f"{extra_line} {FORM_URL}")

        if hashtags_line.strip():
            lines.append(hashtags_line)

        tweet = "\n".join(lines)

        if len(tweet) <= 280:
            return tweet

    # fallback قصير جدًا
    tweet = f"{hook}\n{FORM_URL}\n" + " ".join(FIXED_HASHTAGS)
    return tweet[:280]

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
