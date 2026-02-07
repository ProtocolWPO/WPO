import os
import json
import hashlib
import html
import re
from datetime import datetime, timezone

import requests
from requests_oauthlib import OAuth1Session

OUT_DIR = "out"
TWEET_FILE = os.path.join(OUT_DIR, "tweet.txt")
STATE_FILE = os.path.join(OUT_DIR, "last_post.json")

X_POST_URL = "https://api.x.com/2/tweets"

SITE_URL = "https://protocolwpo.github.io/WPO/"
FORM_URL = "https://protocolwpo.github.io/WPO/#submit"

# Fixed hashtags (always)
FIXED_HASHTAGS = ["#ProtocolWPO", "#CryptoNews"]

# Hooks (rotates by 4-hour slot)
HOOKS = [
    "🚨 Don’t trade blind. Verify first.",
    "⚠️ Hype fades. On-chain facts stay.",
    "🔎 Before you buy, check the moves + news.",
    "🧭 Fast market. Smarter evidence.",
    "🛡️ Protect capital: verify, then trade.",
    "📉 Pumps happen. Proof matters more.",
]

# Extra rotating line (language flavor)
EXTRA_LINES = [
    "举报骗局/可疑钱包（基于证据）：",                      # Chinese
    "Laporkan scam/dompet mencurigakan (berbasis bukti):",   # Indonesian
    "بلّغ عن الاحتيال/المحافظ المشبوهة (بالأدلة):",         # Arabic
]

# Language rotation
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

CMC_BASE = "https://pro-api.coinmarketcap.com"


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


def cmc_get(path: str, params: dict | None = None):
    cmc_key = os.getenv("CMC_KEY")
    if not cmc_key:
        return None, None

    url = f"{CMC_BASE}{path}"
    headers = {
        "X-CMC_PRO_API_KEY": cmc_key,
        "Accept": "application/json",
        "User-Agent": "WPO-bot/1.0",
    }
    r = requests.get(url, headers=headers, params=params or {}, timeout=30)

    # Do not crash on plan/permission/rate limits; allow fallbacks
    if r.status_code in (401, 403, 429):
        return None, r.status_code

    r.raise_for_status()
    return r.json(), r.status_code


def fetch_cmc_quotes(symbols=("BTC", "ETH")):
    j, _ = cmc_get(
        "/v2/cryptocurrency/quotes/latest",
        {"symbol": ",".join(symbols), "convert": "USD"},
    )
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


def fetch_cmc_latest_news(limit=6):
    """
    Tries multiple CMC Content endpoints.
    Returns list of tuples: (source, title, url, id)
    """
    endpoints = [
        ("/v1/content/latest", {"start": 1, "limit": limit, "sort": "published_at", "sort_dir": "desc"}),
        ("/v1/content/posts/latest", {"start": 1, "limit": limit}),
        ("/v1/content/posts/top", {"start": 1, "limit": limit}),
    ]

    for path, params in endpoints:
        j, _ = cmc_get(path, params)
        if not j or "data" not in j:
            continue

        out = []
        for it in j["data"]:
            title = (it.get("title") or "").strip()
            url = (it.get("url") or "").strip()
            src = (it.get("source_name") or it.get("sourceName") or "CMC").strip()
            nid = it.get("id") or sha((title + url)[:200])
            if title and url:
                out.append((src, html.unescape(title), url, str(nid)))

        if out:
            return out

    return []


def pick_dynamic_hashtags(news_title: str | None):
    pool_general = [
        "#Bitcoin", "#Ethereum", "#Crypto", "#DeFi", "#Web3", "#Altcoins",
        "#Blockchain", "#CryptoMarket", "#BTC", "#ETH", "#Trading"
    ]
    pool_reg = ["#SEC", "#Regulation", "#ETF", "#Macro", "#Fed", "#Markets"]
    pool_risk = ["#OnChain", "#Security", "#ScamAlert", "#RugPull", "#DYOR"]
    pool_ai = ["#AI", "#AIcrypto"]

    title = (news_title or "").lower()

    candidates = set()

    # Keyword-based picks
    if any(k in title for k in ["bitcoin", "btc"]):
        candidates.update(["#Bitcoin", "#BTC"])
    if any(k in title for k in ["ethereum", "eth"]):
        candidates.update(["#Ethereum", "#ETH"])
    if "etf" in title:
        candidates.update(["#ETF", "#Bitcoin"])
    if any(k in title for k in ["sec", "regulat", "law", "ban", "court"]):
        candidates.update(pool_reg)
    if any(k in title for k in ["hack", "exploit", "scam", "rug", "phish", "drain"]):
        candidates.update(pool_risk)
    if "defi" in title:
        candidates.update(["#DeFi", "#OnChain"])
    if "web3" in title:
        candidates.update(["#Web3", "#Blockchain"])
    if "ai" in title or "artificial intelligence" in title:
        candidates.update(pool_ai)

    # Always keep some general options
    candidates.update(pool_general)

    # Remove fixed tags if present
    candidates.discard("#ProtocolWPO")
    candidates.discard("#CryptoNews")

    # Deterministic rotation using hash of title+day
    seed = sha((news_title or "") + datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    ordered = sorted(list(candidates))
    if not ordered:
        return ["#Crypto", "#Bitcoin"]

    i = int(seed[:8], 16)
    tag1 = ordered[i % len(ordered)]
    tag2 = ordered[(i // 7) % len(ordered)]
    if tag2 == tag1 and len(ordered) > 1:
        tag2 = ordered[(i // 13) % len(ordered)]

    # Ensure two
    if tag1 == tag2:
        tag2 = "#Crypto"

    return [tag1, tag2]


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
    slot = now_dt.hour // 4

    hook = HOOKS[slot % len(HOOKS)]
    extra_line = EXTRA_LINES[slot % len(EXTRA_LINES)]

    lang = LANGS[slot % len(LANGS)]
    tpl_list = TEMPLATES[lang]
    tpl = tpl_list[slot % len(tpl_list)]

    # Prices from CMC (required)
    q = fetch_cmc_quotes(("BTC", "ETH"))
    btc_p = q.get("BTC", {}).get("price")
    btc_c = q.get("BTC", {}).get("pct24")
    eth_p = q.get("ETH", {}).get("price")
    eth_c = q.get("ETH", {}).get("pct24")

    btc = f"${btc_p:,.0f}" if isinstance(btc_p, (int, float)) else "n/a"
    eth = f"${eth_p:,.0f}" if isinstance(eth_p, (int, float)) else "n/a"
    btcchg = fmt_pct(btc_c) if isinstance(btc_c, (int, float)) else "n/a"
    ethchg = fmt_pct(eth_c) if isinstance(eth_c, (int, float)) else "n/a"

    # News from CMC (best-effort)
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

    news_title = None
    if chosen:
        src, title, url, nid = chosen
        news_title = title
        news_title_short = shorten(title, 70)
        news = f"{src}: {news_title_short} {url}"
    else:
        # If CMC content endpoints are unavailable, omit news gracefully
        news = "CMC update: market moving fast."

    # Two fixed + two dynamic (varies each run)
    dyn_tags = pick_dynamic_hashtags(news_title)
    tags = " ".join(FIXED_HASHTAGS + dyn_tags)

    cta = FORM_URL

    tweet = tpl.format(
        hook=hook,
        btc=btc, btcchg=btcchg,
        eth=eth, ethchg=ethchg,
        news=news,
        cta=cta,
        tags=tags,
    )

    # Add extra line only if still within limit
    extra = f"{extra_line} {FORM_URL}"
    if len(tweet) + 1 + len(extra) <= 280:
        tweet = tweet + "\n" + extra

    # Smart trimming to enforce 280
    if len(tweet) > 280 and chosen:
        tweet = tweet.replace(shorten(chosen[1], 70), shorten(chosen[1], 48))
    if len(tweet) > 280:
        tags2 = " ".join(FIXED_HASHTAGS + dyn_tags[:2])
        tweet = re.sub(r"(#\w+\s*)+$", tags2, tweet).strip()
    if len(tweet) > 280:
        tweet = shorten(tweet, 280)

    # Persist used news ids to reduce repeats
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
