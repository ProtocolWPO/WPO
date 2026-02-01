#!/usr/bin/env python3
import os, json, datetime, math, re, time
import requests

CMC_KEY = os.getenv("CMC_KEY")

MIN_MCAP = float(os.getenv("MIN_MCAP", "200000000"))   # 200M
MIN_VOL  = float(os.getenv("MIN_VOL",  "20000000"))    # 20M
TOP_N    = int(os.getenv("TOP_N", "20"))
FETCH_LIMIT = int(os.getenv("FETCH_LIMIT", "600"))

CMC_URL = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest"

STABLE_SYMBOLS = {
    "USDT","USDC","DAI","BUSD","TUSD","USDP","FDUSD","FRAX","USDE","USDD","PYUSD",
    "GUSD","LUSD","EURC","EURT","USTC"
}

WRAPPED_KNOWN = {"WBTC","WETH","WBNB","WMATIC","WAVAX"}
WRAPPED_EXCEPTIONS = {"WIF","WAVES","WOO","WAXP","WLD"}

WRAPPED_PATTERNS = [
    r"\bWRAPPED\b",
    r"\bBRIDGE\b",
    r"\bBRIDGED\b",
    r"\bWORMHOLE\b",
    r"\bPORTAL\b",
    r"\bREN\b",
    r"\bstETH\b",
    r"\bcbETH\b",
]
WRAPPED_REGEX = [re.compile(p, re.IGNORECASE) for p in WRAPPED_PATTERNS]

def http_get(url, params=None, headers=None, timeout=30, retries=3, backoff=1.4):
    last = None
    for i in range(retries):
        try:
            r = requests.get(url, params=params, headers=headers, timeout=timeout)
            r.raise_for_status()
            return r
        except Exception as e:
            last = e
            time.sleep(backoff * (i + 1))
    raise last

def is_stable(symbol: str, name: str) -> bool:
    sym = (symbol or "").upper().strip()
    nm = (name or "").upper()
    if sym in STABLE_SYMBOLS:
        return True
    if "STABLE" in nm and ("USD" in nm or "EURO" in nm):
        return True
    return False

def is_wrapped_or_bridged(symbol: str, name: str) -> bool:
    sym = (symbol or "").upper().strip()
    nm  = (name or "").strip()

    if sym in WRAPPED_EXCEPTIONS:
        return False
    if sym in WRAPPED_KNOWN:
        return True

    txt = f"{sym} {nm}"
    for rgx in WRAPPED_REGEX:
        if rgx.search(txt):
            return True

    # Conservative: treat WBTC/WETH/WBNB as wrapped, avoid auto-killing all "W*"
    if sym in {"WBTC","WETH","WBNB"}:
        return True

    return False

def fetch_listings(fetch_limit=600):
    if not CMC_KEY:
        raise SystemExit("Missing CMC_KEY")

    headers = {
        "Accepts": "application/json",
        "X-CMC_PRO_API_KEY": CMC_KEY,
        "User-Agent": "top20-bot/1.0"
    }
    params = {
        "start": 1,
        "limit": fetch_limit,
        "convert": "USD",
        "sort": "volume_24h",
        "sort_dir": "desc",
    }

    r = http_get(CMC_URL, headers=headers, params=params, timeout=30)
    j = r.json()
    if "data" not in j:
        raise RuntimeError(f"Unexpected response shape: {j}")
    return j["data"]

def score(volume_24h, market_cap):
    # Robust score using logs + ratio clamp + penalty for suspiciously high ratio
    vol = max(float(volume_24h or 0.0), 1.0)
    mcap = max(float(market_cap or 0.0), 1.0)

    ratio = vol / mcap
    ratio_clamped = max(0.02, min(ratio, 0.8))

    penalty = 0.0
    if ratio > 1.2:
        penalty = (ratio - 1.2) * 2.0

    return (
        math.log10(vol) +
        0.7 * math.log10(mcap) +
        0.8 * ratio_clamped -
        penalty
    )

def build_top(rows, limit=20):
    items = []
    for row in rows:
        symbol = (row.get("symbol") or "").upper().strip()
        name = row.get("name") or ""
        q = (row.get("quote") or {}).get("USD") or {}

        vol = float(q.get("volume_24h") or 0.0)
        mcap = float(q.get("market_cap") or 0.0)
        price = float(q.get("price") or 0.0)

        if not symbol or vol <= 0 or mcap <= 0:
            continue

        if is_stable(symbol, name):
            continue
        if is_wrapped_or_bridged(symbol, name):
            continue

        if mcap < MIN_MCAP:
            continue
        if vol < MIN_VOL:
            continue

        items.append({
            "symbol": symbol,
            "name": name,
            "price": price,
            "volume_24h": vol,
            "market_cap": mcap,
            "vol_mcap_ratio": (vol / mcap) if mcap > 0 else 0.0,
            "_score": score(vol, mcap),
        })

    items.sort(key=lambda x: x["_score"], reverse=True)
    items = items[:limit]

    for i, it in enumerate(items, 1):
        it["rank"] = i
        it.pop("_score", None)

    return items

def main():
    os.makedirs("data", exist_ok=True)

    rows = fetch_listings(fetch_limit=FETCH_LIMIT)
    top = build_top(rows, limit=TOP_N)

    payload = {
        "updated_utc": datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "criteria": (
            f"CMC-only | Exclude stable/wrapped | MarketCap>={int(MIN_MCAP)} | "
            f"Volume24h>={int(MIN_VOL)} | Score=log(vol)+0.7log(mcap)+ratio(clamped)-penalty"
        ),
        "items": top
    }

    with open("data/top20.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"Saved data/top20.json with {len(top)} items")

if __name__ == "__main__":
    main()
