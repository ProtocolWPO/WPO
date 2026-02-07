import os
import json
import hashlib
import html
from datetime import datetime, timezone

import requests
from requests_oauthlib import OAuth1Session

OUT_DIR = "out"
TWEET_FILE = os.path.join(OUT_DIR, "tweet.txt")
STATE_FILE = os.path.join(OUT_DIR, "last_post.json")
DEBUG_FILE = os.path.join(OUT_DIR, "cmc_debug.json")

X_POST_URL = "https://api.x.com/2/tweets"

SITE_URL = "https://protocolwpo.github.io/WPO/"
FORM_URL = "https://protocolwpo.github.io/WPO/#submit"

FIXED_HASHTAGS = ["#ProtocolWPO", "#CryptoNews"]

LANGS = ["EN", "AR", "ZH", "ID"]

HOOKS_BY_LANG = {
    "EN": [
        "🚨 Don’t trade blind. Verify first.",
        "🔎 News moves markets. Evidence moves smart traders.",
        "🛡️ Protect capital: read the signal, not the noise.",
    ],
    "AR": [
        "🚨 لا تتداول أعمى… تحقق أولًا.",
        "🔎 الأخبار تحرّك السوق… والأدلة تحمي رأس مالك.",
        "🛡️ احمِ رأس مالك: اقرأ الإشارة لا الضجيج.",
    ],
    "ZH": [
        "🚨 别盲目交易，先核实。",
        "🔎 新闻会带动市场，证据保护资金。",
        "🛡️ 保护本金：看信号，不看噪音。",
    ],
    "ID": [
        "🚨 Jangan trading buta. Verifikasi dulu.",
        "🔎 Berita menggerakkan market. Bukti melindungi modal.",
        "🛡️ Lindungi modal: baca sinyal, bukan noise.",
    ],
}

EXTRA_LINES_BY_LANG = {
    "EN": "Report scams/suspicious wallets (evidence-based):",
    "AR": "بلّغ عن الاحتيال/المحافظ المشبوهة (بالأدلة):",
    "ZH": "举报骗局/可疑钱包（基于证据）：",
    "ID": "Laporkan scam/dompet mencurigakan (berbasis bukti):",
}

TEMPLATES = {
    "EN": [
        "{hook}\n📰 {news}\nMore: {site}\n{tags} {uniq}",
        "{hook}\nHeadline: {news}\n{site}\n{tags} {uniq}",
    ],
    "AR": [
        "{hook}\n📰 {news}\nالمزيد: {site}\n{tags} {uniq}",
        "{hook}\nآخر خبر: {news}\n{site}\n{tags} {uniq}",
    ],
    "ZH": [
        "{hook}\n📰 {news}\n更多：{site}\n{tags} {uniq}",
        "{hook}\n最新：{news}\n{site}\n{tags} {uniq}",
    ],
    "ID": [
        "{hook}\n📰 {news}\nSelengkapnya: {site}\n{tags} {uniq}",
        "{hook}\nHeadline: {news}\n{site}\n{tags} {uniq}",
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


def save_debug(obj):
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(DEBUG_FILE, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def shorten(s: str, max_len: int) -> str:
    s = " ".join((s or "").split())
    if len(s) <= max_len:
        return s
    return s[: max(0, max_len - 1)].rstrip() + "…"


def cmc_get(path: str, params: dict | None = None):
    cmc_key = os.getenv("CMC_KEY")
    if not cmc_key:
        return None, 0, "CMC_KEY missing"

    url = f"{CMC_BASE}{path}"
    headers = {
        "X-CMC_PRO_API_KEY": cmc_key,
        "Accept": "application/json",
        "User-Agent": "WPO-bot/1.0",
    }

    try:
        r = requests.get(url, headers=headers, params=params or {}, timeout=30)
    except Exception as e:
        return None, -1, f"request_error: {e}"

    status = r.status_code
    text_snip = (r.text or "")[:400]

    if status in (401, 403, 429):
        return None, status, text_snip

    try:
        r.raise_for_status()
        return r.json(), status, ""
    except Exception as e:
        return None, status, f"parse_or_http_error: {e} :: {text_snip}"


def fetch_cmc_latest_news(limit=8):
    endpoints = [
        ("/v1/content/latest", {"start": 1, "limit": limit, "sort": "published_at", "sort_dir": "desc"}),
        ("/v1/content/posts/latest", {"start": 1, "limit": limit}),
        ("/v1/content/posts/top", {"start": 1, "limit": limit}),
    ]

    debug = {"tried": []}

    for path, params in endpoints:
        j, status, err = cmc_get(path, params)
        debug["tried"].append({"path": path, "status": status, "error": err})

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
            debug["selected"] = {"path": path, "count": len(out)}
            return out, debug

    debug["selected"] = None
    return [], debug


def pick_dynamic_hashtags(news_title: str | None):
    pool_general = [
        "#Bitcoin", "#Ethereum", "#Crypto", "#DeFi", "#Web3", "#Altcoins",
        "#Blockchain", "#CryptoMarket", "#BTC", "#ETH", "#Trading"
    ]
    pool_reg = ["#SEC", "#Regulation", "#ETF", "#Macro", "#Fed", "#Markets"]
    pool_risk = ["#OnChain", "#Security", "#ScamAlert", "#RugPull", "#DYOR"]

    title = (news_title or "").lower()
    candidates = set(pool_general)

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

    candidates.discard("#ProtocolWPO")
    candidates.discard("#CryptoNews")

    ordered = sorted(candidates)
    if not ordered:
        return ["#Crypto", "#Bitcoin"]

    seed = sha((news_title or "") + datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M"))
    i = int(seed[:8], 16)

    tag1 = ordered[i % len(ordered)]
    tag2 = ordered[(i // 7) % len(ordered)]
    if tag2 == tag1 and len(ordered) > 1:
        tag2 = ordered[(i // 13) % len(ordered)]
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

    if r.status_code in (200, 201):
        return r.json()

    if r.status_code == 403:
        try:
            j = r.json()
        except Exception:
            j = {"detail": r.text}
        detail = str(j.get("detail", "")).lower()
        if "duplicate" in detail:
            print("X rejected duplicate content — skipping without failure.")
            return {"skipped": True, "reason": "duplicate"}

    raise SystemExit(f"X post failed: {r.status_code} {r.text}")


def build_tweet():
    state = load_state()
    run_count = int(state.get("run_count", 0)) + 1

    lang = LANGS[run_count % len(LANGS)]
    tpl_list = TEMPLATES[lang]
    tpl = tpl_list[run_count % len(tpl_list)]

    hooks = HOOKS_BY_LANG.get(lang, HOOKS_BY_LANG["EN"])
    hook = hooks[run_count % len(hooks)]

    used_ids = set(state.get("news_ids", []))
    news_items, news_dbg = fetch_cmc_latest_news(limit=8)

    chosen = None
    for src, title, url, nid in news_items:
        if nid not in used_ids:
            chosen = (src, title, url, nid)
            break
    if not chosen and news_items:
        chosen = news_items[0]

    if chosen:
        src, title, url, nid = chosen
        news_title = title
        news = f"{src}: {shorten(title, 90)}\n{url}"
    else:
        news_title = None
        news = "CMC update: market moving fast."

    dyn_tags = pick_dynamic_hashtags(news_title)
    tags = " ".join(FIXED_HASHTAGS + dyn_tags)

    uniq = datetime.now(timezone.utc).strftime("• %H:%MZ")

    tweet = tpl.format(
        hook=hook,
        news=news,
        site=SITE_URL,
        tags=tags,
        uniq=uniq,
    )

    extra_line = EXTRA_LINES_BY_LANG.get(lang, EXTRA_LINES_BY_LANG["EN"])
    extra = f"{extra_line} {FORM_URL}"
    if len(tweet) + 1 + len(extra) <= 280:
        tweet = tweet + "\n" + extra

    if len(tweet) > 280 and chosen:
        tweet = tweet.replace(shorten(chosen[1], 90), shorten(chosen[1], 70))
    if len(tweet) > 280 and chosen:
        tweet = tweet.replace(shorten(chosen[1], 70), shorten(chosen[1], 58))
    if len(tweet) > 280:
        tweet = shorten(tweet, 280)

    debug = {
        "utc": datetime.now(timezone.utc).isoformat(),
        "run_count": run_count,
        "lang": lang,
        "news_debug": news_dbg,
        "chosen": {
            "src": chosen[0] if chosen else None,
            "id": chosen[3] if chosen else None,
        },
    }
    save_debug(debug)

    state["run_count"] = run_count
    if chosen:
        ids = state.get("news_ids", [])
        ids.append(chosen[3])
        state["news_ids"] = ids[-80:]
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

    if isinstance(resp, dict) and resp.get("skipped"):
        state.update({
            "last_hash": h,
            "last_tweet_id": None,
            "last_text": tweet,
            "posted_at_utc": datetime.now(timezone.utc).isoformat(),
            "skipped_reason": resp.get("reason"),
        })
        save_state(state)
        print("Skipped posting to X due to duplicate content.")
        return

    tweet_id = (resp or {}).get("data", {}).get("id")

    state.update({
        "last_hash": h,
        "last_tweet_id": tweet_id,
        "last_text": tweet,
        "posted_at_utc": datetime.now(timezone.utc).isoformat(),
    })
    save_state(state)

    print("Posted to X. id=", tweet_id)


if __name__ == "__main__":
    main()
