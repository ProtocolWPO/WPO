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
    "EN": ["🔥 Trending (1H) — Top 15", "📈 Trending now (1H) — Top 15", "🧭 Attention map (1H) — Top 15"],
    "AR": ["🔥 الترند (ساعة) — أفضل 15", "📈 الترند الآن (ساعة) — أفضل 15", "🧭 خريطة الانتباه (ساعة) — أفضل 15"],
    "ZH": ["🔥 1小时趋势榜 — 前15", "📈 当前热门（1小时）— 前15", "🧭 关注度地图（1小时）— 前15"],
    "ID": ["🔥 Trending (1J) — Top 15", "📈 Lagi trending (1J) — Top 15", "🧭 Peta perhatian (1J) — Top 15"],
}

LABELS_BY_LANG = {
    "EN": {"top": "Top 15", "site": "More", "fallback": "Trending data temporarily unavailable."},
    "AR": {"top": "أفضل 15", "site": "المزيد", "fallback": "بيانات الترند غير متاحة مؤقتًا."},
    "ZH": {"top": "前15", "site": "更多", "fallback": "趋势数据暂不可用。"},
    "ID": {"top": "Top 15", "site": "Selengkapnya", "fallback": "Data trending sementara tidak tersedia."},
}

REPORT_LINES_BY_LANG = {
    "EN": [
        "🚨 Saw suspicious movement or a scam project? Report here:",
        "🛡️ Protect traders — report suspicious wallets/projects here:",
        "🔎 Submit evidence of suspicious activity here:",
    ],
    "AR": [
        "🚨 لاحظت حركة مشبوهة أو مشروع احتيالي؟ بلّغ هنا:",
        "🛡️ احمِ المتداولين — بلّغ عن محافظ/مشاريع مشبوهة هنا:",
        "🔎 أرسل الأدلة عن نشاط مشبوه هنا:",
    ],
    "ZH": [
        "🚨 发现可疑动向或诈骗项目？在此举报：",
        "🛡️ 保护交易者：在此举报可疑钱包/项目：",
        "🔎 在此提交可疑活动证据：",
    ],
    "ID": [
        "🚨 Lihat pergerakan mencurigakan atau proyek scam? Laporkan di sini:",
        "🛡️ Lindungi trader — laporkan dompet/proyek mencurigakan di sini:",
        "🔎 Kirim bukti aktivitas mencurigakan di sini:",
    ],
}

CMC_PRO_BASE = "https://pro-api.coinmarketcap.com"


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


def _req_json(url: str, params=None, headers=None, timeout=30):
    try:
        r = requests.get(url, params=params or {}, headers=headers or {}, timeout=timeout)
        status = r.status_code
        text_snip = (r.text or "")[:800]
        if status != 200:
            return None, status, text_snip
        try:
            return r.json(), status, ""
        except Exception as e:
            return None, status, f"json_parse_error: {e} :: {text_snip}"
    except Exception as e:
        return None, -1, f"request_error: {e}"


def fetch_trending_top15():
    dbg = {"tried": []}

    cmc_key = os.getenv("CMC_KEY")
    if cmc_key:
        url = f"{CMC_PRO_BASE}/v1/cryptocurrency/trending/latest"
        headers = {
            "X-CMC_PRO_API_KEY": cmc_key,
            "Accept": "application/json",
            "User-Agent": "WPO-trending-bot/1.0",
        }
        j, status, err = _req_json(url, params={"start": 1, "limit": 15}, headers=headers, timeout=30)
        dbg["tried"].append({"source": "cmc_pro", "status": status, "error": err})
        if j and isinstance(j.get("data"), list):
            out = []
            for it in j["data"]:
                sym = (it.get("symbol") or "").strip()
                if sym:
                    out.append(sym)
            if out:
                dbg["selected"] = "cmc_pro"
                return out[:15], dbg

    url = "https://api.coinmarketcap.com/data-api/v3/cryptocurrency/listing"
    params = {
        "start": 1,
        "limit": 15,
        "sortBy": "trendingScore",
        "sortType": "desc",
        "timeframe": "1h",
        "cryptoType": "all",
        "tagType": "all",
        "convertId": 2781,
    }
    headers = {
        "Accept": "application/json",
        "User-Agent": "WPO-trending-bot/1.0",
        "Referer": "https://coinmarketcap.com/",
        "Origin": "https://coinmarketcap.com",
    }
    j, status, err = _req_json(url, params=params, headers=headers, timeout=30)
    dbg["tried"].append({"source": "cmc_public", "status": status, "error": err})
    if j:
        data = (j.get("data") or {})
        lst = data.get("cryptoCurrencyList") or data.get("list") or []
        out = []
        if isinstance(lst, list):
            for it in lst:
                sym = (it.get("symbol") or "").strip()
                if sym:
                    out.append(sym)
        if out:
            dbg["selected"] = "cmc_public"
            return out[:15], dbg

    url = "https://api.coingecko.com/api/v3/search/trending"
    headers = {"Accept": "application/json", "User-Agent": "WPO-trending-bot/1.0"}
    j, status, err = _req_json(url, headers=headers, timeout=20)
    dbg["tried"].append({"source": "coingecko", "status": status, "error": err})
    if j and isinstance(j.get("coins"), list):
        out = []
        for it in j["coins"]:
            item = it.get("item") or {}
            sym = item.get("symbol")
            if sym:
                out.append(str(sym).upper())
            if len(out) >= 15:
                break
        if out:
            dbg["selected"] = "coingecko"
            return out[:15], dbg

    dbg["selected"] = None
    return [], dbg


def post_to_x(text: str):
    for k in ["X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET"]:
        if not os.getenv(k):
            return {"skipped": True, "reason": f"missing_secret:{k}"}

    oauth = OAuth1Session(
        client_key=os.getenv("X_API_KEY"),
        client_secret=os.getenv("X_API_SECRET"),
        resource_owner_key=os.getenv("X_ACCESS_TOKEN"),
        resource_owner_secret=os.getenv("X_ACCESS_TOKEN_SECRET"),
    )

    r = oauth.post(X_POST_URL, json={"text": text}, timeout=30)

    if r.status_code in (200, 201):
        return r.json()

    try:
        j = r.json()
    except Exception:
        j = {"detail": r.text}

    detail = str(j.get("detail", "")).lower()

    if r.status_code == 403 and "duplicate" in detail:
        return {"skipped": True, "reason": "duplicate", "status": 403, "detail": j}

    # IMPORTANT: do not crash the workflow on 401/403/429
    if r.status_code in (401, 403, 429):
        return {"skipped": True, "reason": "x_forbidden_or_limited", "status": r.status_code, "detail": j}

    return {"skipped": True, "reason": "x_post_failed", "status": r.status_code, "detail": j}


def build_tweet():
    state = load_state()
    run_count = int(state.get("run_count", 0)) + 1

    lang = LANGS[run_count % len(LANGS)]
    hook_list = HOOKS_BY_LANG.get(lang, HOOKS_BY_LANG["EN"])
    hook = hook_list[run_count % len(hook_list)]
    labels = LABELS_BY_LANG.get(lang, LABELS_BY_LANG["EN"])

    symbols, dbg = fetch_trending_top15()

    report_lines = REPORT_LINES_BY_LANG.get(lang, REPORT_LINES_BY_LANG["EN"])
    report_line = report_lines[run_count % len(report_lines)]

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

    tags = " ".join(FIXED_HASHTAGS + EXTRA_HASHTAGS)
    uniq = f"• {datetime.now(timezone.utc).strftime('%H:%M:%SZ')} • run#{run_count}"

    if symbols:
        list_text = ", ".join([f"${s}" for s in symbols])
        tweet = (
            f"{hook}\n"
            f"{labels['top']}: {list_text}\n"
            f"{report_line} {FORM_URL}\n"
            f"{tags} {uniq}"
        )
        return tweet

    tweet = (
        f"{hook}\n"
        f"{labels['fallback']}\n"
        f"{report_line} {FORM_URL}\n"
        f"{tags} {uniq}"
    )
    return tweet


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    tweet = build_tweet()

    with open(TWEET_FILE, "w", encoding="utf-8") as f:
        f.write(tweet)

    state = load_state()
    h = sha(tweet)

    # Ensure uniqueness to avoid "duplicate" even if content repeats
    uniq_suffix = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    if state.get("last_hash") == h:
        tweet = tweet + f"\n{uniq_suffix}"
        h = sha(tweet)
        with open(TWEET_FILE, "w", encoding="utf-8") as f:
            f.write(tweet)

    resp = post_to_x(tweet)

    if isinstance(resp, dict) and resp.get("skipped"):
        state.update({
            "last_hash": h,
            "last_tweet_id": None,
            "last_text": tweet,
            "posted_at_utc": datetime.now(timezone.utc).isoformat(),
            "skipped_reason": resp.get("reason"),
            "x_status": resp.get("status"),
            "x_detail": resp.get("detail"),
        })
        save_state(state)
        save_debug({
            "utc": datetime.now(timezone.utc).isoformat(),
            "event": "x_post_skipped",
            "skipped": resp,
        })
        print("X post skipped:", resp.get("reason"), resp.get("status"))
        return

    tweet_id = (resp or {}).get("data", {}).get("id")

    state.update({
        "last_hash": h,
        "last_tweet_id": tweet_id,
        "last_text": tweet,
        "posted_at_utc": datetime.now(timezone.utc).isoformat(),
        "skipped_reason": None,
        "x_status": 200,
        "x_detail": None,
    })
    save_state(state)

    print("Posted to X. id=", tweet_id)


if __name__ == "__main__":
    main()
