import os
import json
import hashlib
import html
from datetime import datetime, timezone, timedelta

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

POST_MODE = os.getenv("POST_MODE", "X").upper()  # "X" or "LONG"

SAFE_MIN_MARKET_CAP_USD = float(os.getenv("SAFE_MIN_MARKET_CAP_USD", "200000000"))
SAFE_MIN_VOLUME_24H_USD = float(os.getenv("SAFE_MIN_VOLUME_24H_USD", "10000000"))
SAFE_MAX_CMC_RANK = int(os.getenv("SAFE_MAX_CMC_RANK", "300"))
SAFE_MIN_AGE_DAYS = int(os.getenv("SAFE_MIN_AGE_DAYS", "180"))
SAFE_EXCLUDE_TAGS = set(
    t.strip().lower()
    for t in os.getenv(
        "SAFE_EXCLUDE_TAGS",
        "memes,memecoin,ai memes,shitcoins,scam,ponzi",
    ).split(",")
    if t.strip()
)

HOOKS_BY_LANG = {
    "EN": [
        "🔥 CMC Trending (1H) — safe list only.",
        "🧭 Trending now (1H) — filtered for safer assets.",
        "🛡️ Attention map (1H) — safer picks only.",
    ],
    "AR": [
        "🔥 ترند CMC (ساعة) — قائمة آمنة فقط.",
        "🧭 الترند الآن (ساعة) — مُرشّحة للأصول الأكثر أمانًا.",
        "🛡️ خريطة الانتباه (ساعة) — اختيارات أكثر أمانًا فقط.",
    ],
    "ZH": [
        "🔥 CMC 1小时趋势榜 — 仅安全列表。",
        "🧭 当前热门（1小时）— 已过滤更安全资产。",
        "🛡️ 关注度地图（1小时）— 仅更安全选择。",
    ],
    "ID": [
        "🔥 Trending CMC (1J) — daftar aman saja.",
        "🧭 Trending sekarang (1J) — difilter lebih aman.",
        "🛡️ Peta perhatian (1J) — pilihan lebih aman saja.",
    ],
}

EXTRA_LINES_BY_LANG = {
    "EN": "Report suspicious wallets:",
    "AR": "بلّغ عن محافظ مشبوهة:",
    "ZH": "举报可疑钱包：",
    "ID": "Laporkan dompet mencurigakan:",
}

TEMPLATES = {
    "EN": [
        "{hook}\nTop safe (max 15): {list}\nSource: {cmc}\nSubmit: {form}\n{site}\n{tags} {uniq}",
    ],
    "AR": [
        "{hook}\nأفضل الآمن (حتى 15): {list}\nالمصدر: {cmc}\nإرسال: {form}\n{site}\n{tags} {uniq}",
    ],
    "ZH": [
        "{hook}\n安全前15（最多）：{list}\n来源：{cmc}\n提交：{form}\n{site}\n{tags} {uniq}",
    ],
    "ID": [
        "{hook}\nTop aman (maks 15): {list}\nSumber: {cmc}\nKirim: {form}\n{site}\n{tags} {uniq}",
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


def fetch_cmc_trending_latest(limit=40):
    j, status, err = cmc_get(
        "/v1/cryptocurrency/trending/latest",
        {"start": 1, "limit": limit, "convert": "USD"},
    )
    debug = {"endpoint": "cryptocurrency/trending/latest", "status": status, "error": err}

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
        name = (it.get("name") or "").strip()
        symbol = (it.get("symbol") or "").strip()
        cid = it.get("id")
        if name and symbol and cid:
            out.append({"name": html.unescape(name), "symbol": symbol, "id": int(cid)})
    return out, debug


def fetch_quotes_by_ids(ids):
    if not ids:
        return {}, {"endpoint": "quotes/latest", "status": 0, "error": "no_ids"}

    j, status, err = cmc_get(
        "/v2/cryptocurrency/quotes/latest",
        {"id": ",".join(str(i) for i in ids), "convert": "USD"},
    )
    debug = {"endpoint": "quotes/latest", "status": status, "error": err}
    if not j or "data" not in j:
        return {}, debug

    data = j["data"]
    out = {}
    for k, v in (data or {}).items():
        obj = v[0] if isinstance(v, list) and v else v
        if not isinstance(obj, dict):
            continue
        cid = obj.get("id")
        q = (obj.get("quote") or {}).get("USD", {}) or {}
        out[int(cid)] = {
            "cmc_rank": obj.get("cmc_rank"),
            "market_cap": q.get("market_cap"),
            "volume_24h": q.get("volume_24h"),
        }
    return out, debug


def fetch_info_by_ids(ids):
    if not ids:
        return {}, {"endpoint": "info", "status": 0, "error": "no_ids"}

    j, status, err = cmc_get(
        "/v2/cryptocurrency/info",
        {"id": ",".join(str(i) for i in ids)},
    )
    debug = {"endpoint": "info", "status": status, "error": err}
    if not j or "data" not in j:
        return {}, debug

    data = j["data"]
    out = {}
    for k, v in (data or {}).items():
        obj = v[0] if isinstance(v, list) and v else v
        if not isinstance(obj, dict):
            continue
        cid = obj.get("id")
        date_added = obj.get("date_added") or obj.get("dateAdded")
        tags = obj.get("tags") or []
        out[int(cid)] = {
            "date_added": date_added,
            "tags": [str(t) for t in tags] if isinstance(tags, list) else [],
        }
    return out, debug


def parse_date_added(s: str | None):
    if not s:
        return None
    try:
        if s.endswith("Z"):
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        return datetime.fromisoformat(s)
    except Exception:
        return None


def is_safe_token(cid: int, quotes: dict, info: dict):
    q = quotes.get(cid) or {}
    i = info.get(cid) or {}

    rank = q.get("cmc_rank")
    mcap = q.get("market_cap")
    vol = q.get("volume_24h")

    if not isinstance(rank, int):
        return False
    if rank <= 0 or rank > SAFE_MAX_CMC_RANK:
        return False

    if not isinstance(mcap, (int, float)) or mcap < SAFE_MIN_MARKET_CAP_USD:
        return False
    if not isinstance(vol, (int, float)) or vol < SAFE_MIN_VOLUME_24H_USD:
        return False

    dt = parse_date_added(i.get("date_added"))
    if not dt:
        return False
    if dt > datetime.now(timezone.utc) - timedelta(days=SAFE_MIN_AGE_DAYS):
        return False

    tags = [t.lower().strip() for t in (i.get("tags") or [])]
    if any(t in SAFE_EXCLUDE_TAGS for t in tags):
        return False

    return True


def pick_dynamic_hashtags(seed_text: str):
    pool = [
        "#Bitcoin", "#Ethereum", "#Crypto", "#DeFi", "#Web3", "#Altcoins",
        "#Blockchain", "#CryptoMarket", "#BTC", "#ETH", "#Trading", "#OnChain",
        "#Security", "#DYOR", "#ETF", "#Markets"
    ]
    candidates = [t for t in pool if t not in FIXED_HASHTAGS]
    if not candidates:
        return ["#Crypto", "#Bitcoin"]

    h = sha(seed_text + datetime.now(timezone.utc).strftime("%Y-%m-%dT%H"))
    i = int(h[:8], 16)

    tag1 = candidates[i % len(candidates)]
    tag2 = candidates[(i // 7) % len(candidates)]
    if tag2 == tag1 and len(candidates) > 1:
        tag2 = candidates[(i // 13) % len(candidates)]
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


def format_list(items, mode: str):
    if not items:
        return ""
    if mode == "LONG":
        return "\n".join([f"{idx}) {it['name']} ({it['symbol']})" for idx, it in enumerate(items, start=1)])
    return ", ".join([it["symbol"] for it in items])


def build_tweet():
    state = load_state()
    run_count = int(state.get("run_count", 0)) + 1

    lang = LANGS[run_count % len(LANGS)]
    hook_list = HOOKS_BY_LANG.get(lang, HOOKS_BY_LANG["EN"])
    hook = hook_list[run_count % len(hook_list)]
    tpl = TEMPLATES[lang][0]

    trending, trending_dbg = fetch_cmc_trending_latest(limit=60)
    ids = [t["id"] for t in trending]

    quotes, quotes_dbg = fetch_quotes_by_ids(ids)
    info, info_dbg = fetch_info_by_ids(ids)

    safe = []
    for t in trending:
        if is_safe_token(t["id"], quotes, info):
            safe.append(t)
        if len(safe) >= 15:
            break

    list_text = format_list(safe, POST_MODE)
    ok = bool(safe)

    seed = safe[0]["symbol"] if safe else (trending[0]["symbol"] if trending else "WPO")
    dyn_tags = pick_dynamic_hashtags(seed_text=seed)
    tags = " ".join(FIXED_HASHTAGS + dyn_tags)

    uniq = datetime.now(timezone.utc).strftime("• %H:%MZ")

    if not ok:
        tweet = f"{hook}\nNO_SAFE_TRENDING_DATA\nSource: {TRENDING_URL}\nSubmit: {FORM_URL}\n{SITE_URL}\n{tags} {uniq}"
    else:
        tweet = tpl.format(
            hook=hook,
            list=list_text,
            cmc=TRENDING_URL,
            form=FORM_URL,
            site=SITE_URL,
            tags=tags,
            uniq=uniq,
        )

    extra_line = EXTRA_LINES_BY_LANG.get(lang, EXTRA_LINES_BY_LANG["EN"])
    tweet = tweet + "\n" + f"{extra_line} {FORM_URL}".strip()

    debug = {
        "utc": datetime.now(timezone.utc).isoformat(),
        "run_count": run_count,
        "lang": lang,
        "post_mode": POST_MODE,
        "safe_rules": {
            "min_mcap": SAFE_MIN_MARKET_CAP_USD,
            "min_vol_24h": SAFE_MIN_VOLUME_24H_USD,
            "max_rank": SAFE_MAX_CMC_RANK,
            "min_age_days": SAFE_MIN_AGE_DAYS,
            "exclude_tags": sorted(list(SAFE_EXCLUDE_TAGS)),
        },
        "trending_debug": trending_dbg,
        "quotes_debug": quotes_dbg,
        "info_debug": info_dbg,
        "counts": {
            "trending_total": len(trending),
            "safe_selected": len(safe),
        },
        "safe_symbols": [t["symbol"] for t in safe],
    }
    save_debug(debug)

    state["run_count"] = run_count
    save_state(state)

    return tweet, ok


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    tweet, ok = build_tweet()

    with open(TWEET_FILE, "w", encoding="utf-8") as f:
        f.write(tweet)

    if POST_MODE == "LONG":
        print("POST_MODE=LONG: wrote out/tweet.txt only (no X post).")
        return

    if not ok:
        print("No safe trending data; skipping X post.")
        return

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
