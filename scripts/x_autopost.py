import os
import json
import hashlib
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
EXTRA_HASHTAGS = ["#Trending", "#Altcoins"]

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

LABELS_BY_LANG = {
    "EN": {"top": "Top 15", "source": "Source", "submit": "Submit", "site": "Site"},
    "AR": {"top": "أفضل 15", "source": "المصدر", "submit": "إرسال", "site": "الموقع"},
    "ZH": {"top": "前15", "source": "来源", "submit": "提交", "site": "站点"},
    "ID": {"top": "Top 15", "source": "Sumber", "submit": "Kirim", "site": "Situs"},
}


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(state: dict) -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def save_debug(obj: dict) -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(DEBUG_FILE, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def fetch_trending_top15_public():
    """
    Uses CoinMarketCap public data-api endpoint (no CMC_KEY needed).
    This endpoint is used by the website and may change over time.
    """
    url = "https://api.coinmarketcap.com/data-api/v3/cryptocurrency/listing"
    params = {
        "start": 1,
        "limit": 15,
        "sortBy": "trendingScore",
        "sortType": "desc",
        "timeframe": "1h",
        "cryptoType": "all",
        "tagType": "all",
        "convertId": 2781,  # USD
    }
    headers = {
        "Accept": "application/json",
        "User-Agent": "WPO-trending-bot/1.0",
        "Referer": "https://coinmarketcap.com/",
        "Origin": "https://coinmarketcap.com",
    }

    try:
        r = requests.get(url, params=params, headers=headers, timeout=30)
    except Exception as e:
        return [], {"source": "public_data_api", "status": -1, "error": f"request_error: {e}"}

    status = r.status_code
    snip = (r.text or "")[:700]

    if status != 200:
        return [], {"source": "public_data_api", "status": status, "error": snip}

    try:
        j = r.json()
    except Exception as e:
        return [], {"source": "public_data_api", "status": status, "error": f"json_parse_error: {e} :: {snip}"}

    data = (((j or {}).get("data") or {}).get("cryptoCurrencyList")) or []
    out = []
    for it in data:
        sym = (it.get("symbol") or "").strip()
        if sym:
            out.append(sym)

    return out[:15], {"source": "public_data_api", "status": status, "error": ""}


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
    labels = LABELS_BY_LANG.get(lang, LABELS_BY_LANG["EN"])

    symbols, dbg = fetch_trending_top15_public()

    debug_payload = {
        "utc": datetime.now(timezone.utc).isoformat(),
        "run_count": run_count,
        "lang": lang,
        "trending_debug": dbg,
        "selected_count": len(symbols),
        "symbols": symbols,
    }
    save_debug(debug_payload)

    state["run_count"] = run_count
    save_state(state)

    if not symbols:
        return None

    list_text = ", ".join(symbols)
    tags = " ".join(FIXED_HASHTAGS + EXTRA_HASHTAGS)

    uniq = f"• {datetime.now(timezone.utc).strftime('%H:%M:%SZ')} • run#{run_count}"

    tweet = (
        f"{hook}\n"
        f"{labels['top']}: {list_text}\n"
        f"{labels['source']}: {TRENDING_URL}\n"
        f"{labels['submit']}: {FORM_URL}\n"
        f"{labels['site']}: {SITE_URL}\n"
        f"{tags} {uniq}"
    )

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
    print("X post response:", str(resp)[:500])

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
