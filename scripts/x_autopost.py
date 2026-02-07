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
TRENDING_URL = "https://coinmarketcap.com/?tableRankBy=trending_all_1h"

FIXED_HASHTAGS = ["#ProtocolWPO", "#CryptoNews"]
LANGS = ["EN", "AR", "ZH", "ID"]

HOOKS_BY_LANG = {
    "EN": [
        "🔥 CMC Trending (1H) — Top 15",
        "📈 Trending now (1H) — Top 15",
        "🧭 Attention map (1H) — Top 15",
    ],
    "AR": [
        "🔥 ترند CMC (ساعة) — أفضل 15",
        "📈 الترند الآن (ساعة) — أفضل 15",
        "🧭 خريطة الانتباه (ساعة) — أفضل 15",
    ],
    "ZH": [
        "🔥 CMC 1小时趋势榜 — 前15",
        "📈 当前热门（1小时）— 前15",
        "🧭 关注度地图（1小时）— 前15",
    ],
    "ID": [
        "🔥 Trending CMC (1J) — Top 15",
        "📈 Lagi trending (1J) — Top 15",
        "🧭 Peta perhatian (1J) — Top 15",
    ],
}

EXTRA_LINES_BY_LANG = {
    "EN": "Report suspicious wallets:",
    "AR": "بلّغ عن محافظ مشبوهة:",
    "ZH": "举报可疑钱包：",
    "ID": "Laporkan dompet mencurigakan:",
}

TEMPLATES = {
    "EN": ["{hook}\nTop 15: {list}\nSource: {cmc}\n{site}\n{tags} {uniq}\n{extra} {form}"],
    "AR": ["{hook}\nأفضل 15: {list}\nالمصدر: {cmc}\n{site}\n{tags} {uniq}\n{extra} {form}"],
    "ZH": ["{hook}\n前15：{list}\n来源：{cmc}\n{site}\n{tags} {uniq}\n{extra} {form}"],
    "ID": ["{hook}\nTop 15: {list}\nSumber: {cmc}\n{site}\n{tags} {uniq}\n{extra} {form}"],
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
    text_snip = (r.text or "")[:600]

    if status in (401, 403, 429):
        return None, status, text_snip

    try:
        r.raise_for_status()
        return r.json(), status, ""
    except Exception as e:
        return None, status, f"parse_or_http_error: {e} :: {text_snip}"


def fetch_trending_top15():
    j, status, err = cmc_get(
        "/v1/cryptocurrency/trending/latest",
        {"start": 1, "limit": 15, "convert": "USD"},
    )

    debug = {
        "endpoint": "/v1/cryptocurrency/trending/latest",
        "status": status,
        "error": err,
    }

    if not j or "data" not in j:
        return [], debug

    data = j.get("data")
    if isinstance(data, dict):
        items = data.get("data") or data.get("list") or []
    else:
        items = data or []

    out = []
    for it in items:
        if not isinstance(it, dict):
            continue
        symbol = (it.get("symbol") or "").strip()
        name = (it.get("name") or "").strip()
        if symbol:
            out.append({"symbol": symbol, "name": html.unescape(name) if name else ""})

    return out[:15], debug


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
    hook_list = HOOKS_BY_LANG.get(lang, HOOKS_BY_LANG["EN"])
    hook = hook_list[run_count % len(hook_list)]
    tpl = TEMPLATES[lang][0]

    items, dbg = fetch_trending_top15()
    if not items:
        save_debug({
            "utc": datetime.now(timezone.utc).isoformat(),
            "run_count": run_count,
            "lang": lang,
            "trending_debug": dbg,
            "selected_count": 0,
        })
        state["run_count"] = run_count
        save_state(state)
        return None

    symbols = [it["symbol"] for it in items]
    list_text = ", ".join(symbols)

    tags_extra = ["#Trending", "#Altcoins"]
    tags = " ".join(FIXED_HASHTAGS + tags_extra)

    uniq = datetime.now(timezone.utc).strftime("• %H:%MZ")
    extra = EXTRA_LINES_BY_LANG.get(lang, EXTRA_LINES_BY_LANG["EN"])

    tweet = tpl.format(
        hook=hook,
        list=list_text,
        cmc=TRENDING_URL,
        site=SITE_URL,
        tags=tags,
        uniq=uniq,
        extra=extra,
        form=FORM_URL,
    )

    save_debug({
        "utc": datetime.now(timezone.utc).isoformat(),
        "run_count": run_count,
        "lang": lang,
        "trending_debug": dbg,
        "selected_count": len(items),
        "symbols": symbols,
        "tweet_len": len(tweet),
    })

    state["run_count"] = run_count
    save_state(state)

    return tweet


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    tweet = build_tweet()
    if not tweet:
        with open(TWEET_FILE, "w", encoding="utf-8") as f:
            f.write("NO_TRENDING_DATA")
        print("No trending data; skipping.")
        return

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
