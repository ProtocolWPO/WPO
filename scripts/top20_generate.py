#!/usr/bin/env python3
import os, json, datetime, time, math, re
import requests

CMC_KEY = os.getenv("CMC_KEY")

MIN_MCAP = float(os.getenv("MIN_MCAP", "200000000"))          # 200M
MIN_VOL  = float(os.getenv("MIN_VOL",  "20000000"))           # 20M
MAX_SPREAD_PCT = float(os.getenv("MAX_SPREAD_PCT", "0.3"))    # 0.3%
TOP_N = int(os.getenv("TOP_N", "20"))

USE_DEX = os.getenv("USE_DEX", "0").strip() == "1"
DEX_MIN_LIQ = float(os.getenv("DEX_MIN_LIQ", "300000"))       # 300k USD

BINANCE_BOOK_URL = "https://api.binance.com/api/v3/ticker/bookTicker"
BINANCE_24H_URL  = "https://api.binance.com/api/v3/ticker/24hr"
DEX_SEARCH_URL   = "https://api.dexscreener.com/latest/dex/search"

STABLE_SYMBOLS = {
    "USDT","USDC","DAI","BUSD","TUSD","USDP","FDUSD","FRAX","USDE","USDD","PYUSD",
    "GUSD","LUSD","EURC","EURT","USTC"
}

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

WRAPPED_EXCEPTIONS = {"WIF","WAVES","WOO","WAXP","WLD"}
WRAPPED_KNOWN = {"WBTC","WETH","WBNB","WMATIC","WAVAX"}

def http_get(url, params=None, headers=None, timeout=25, retries=3, backoff=1.3):
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
    if ("STABLE" in nm or "USD" in nm) and ("USD" in nm or "EURO" in nm) and ("COIN" in nm or "TOKEN" in nm):
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
    if sym.startswith("W") and len(sym) >= 4 and sym not in WRAPPED_EXCEPTIONS:
        if sym in {"WBTC","WETH","WBNB"}:
            return True
    return False

def fetch_listings(fetch_limit=600):
    if not CMC_KEY:
        raise SystemExit("Missing CMC_KEY")
    url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest"
    headers = {
        "Accepts": "application/json",
        "X-CMC_PRO_API_KEY": CMC_KEY,
        "User-Agent": "top20-bot/2.0"
    }
    params = {
        "start": 1,
        "limit": fetch_limit,
        "convert": "USD",
        "sort": "volume_24h",
        "sort_dir": "desc",
    }
    r = http_get(url, headers=headers, params=params, timeout=30)
    j = r.json()
    if "data" not in j:
        raise RuntimeError(f"Unexpected CMC response shape: {j}")
    return j["data"]

def fetch_binance_maps():
    book = http_get(BINANCE_BOOK_URL, timeout=25).json()
    book_map = {x.get("symbol"): x for x in book if x.get("symbol")}

    t24 = http_get(BINANCE_24H_URL, timeout=25).json()
    t24_map = {x.get("symbol"): x for x in t24 if x.get("symbol")}

    return book_map, t24_map

def calc_spread_pct(bid, ask):
    bid = float(bid); ask = float(ask)
    if bid <= 0 or ask <= 0:
        return None
    mid = (bid + ask) / 2.0
    if mid == 0:
        return None
    return (ask - bid) / mid * 100.0

def dex_best_pair(symbol: str):
    try:
        js = http_get(DEX_SEARCH_URL, params={"q": symbol}, timeout=20, retries=2).json()
        pairs = js.get("pairs") or []
        best = None
        for p in pairs:
            base = (p.get("baseToken") or {}).get("symbol") or ""
            if base.upper() != symbol.upper():
                continue
            liq = (p.get("liquidity") or {}).get("usd")
            volh24 = (p.get("volume") or {}).get("h24")
            if liq is None:
                continue
            liq = float(liq)
            volh24 = float(volh24) if volh24 is not None else 0.0
            sc = liq * 1.0 + volh24 * 0.2
            if best is None or sc > best["score"]:
                best = {
                    "chain": p.get("chainId"),
                    "dex": p.get("dexId"),
                    "pairAddress": p.get("pairAddress"),
                    "liquidity_usd": liq,
                    "volume_h24": volh24,
                    "fdv": p.get("fdv"),
                    "score": sc
                }
        return best
    except Exception:
        return None

def score(vol_24h, mcap, binance_qv, spread_pct):
    ratio = (vol_24h / mcap) if mcap > 0 else 0.0
    ratio_clamped = max(0.02, min(ratio, 0.8))
    penalty = 0.0
    if ratio > 1.2:
        penalty = (ratio - 1.2) * 2.0

    sp_pen = 0.0
    if spread_pct is not None and MAX_SPREAD_PCT > 0:
        sp_pen = 0.8 * (spread_pct / MAX_SPREAD_PCT)

    return (
        math.log10(max(vol_24h, 1.0)) +
        0.7 * math.log10(max(mcap, 1.0)) +
        0.6 * math.log10(max(binance_qv, 1.0)) +
        0.8 * ratio_clamped -
        penalty -
        sp_pen
    )

def build_top(rows, book_map, t24_map, limit=20):
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

        pair = f"{symbol}USDT"
        book = book_map.get(pair)
        t24 = t24_map.get(pair)
        if not book or not t24:
            continue

        bid = book.get("bidPrice")
        ask = book.get("askPrice")
        if not bid or not ask:
            continue

        sp = calc_spread_pct(bid, ask)
        if sp is None or sp > MAX_SPREAD_PCT:
            continue

        binance_qv = float(t24.get("quoteVolume") or 0.0)
        binance_last = float(t24.get("lastPrice") or 0.0)

        dex_info = None
        if USE_DEX:
            dex_info = dex_best_pair(symbol)
            if dex_info and float(dex_info.get("liquidity_usd") or 0.0) < DEX_MIN_LIQ:
                continue

        items.append({
            "symbol": symbol,
            "name": name,
            "price": price,
            "volume_24h": vol,
            "market_cap": mcap,
            "vol_mcap_ratio": (vol / mcap) if mcap > 0 else 0.0,
            "binance_pair": pair,
            "binance_last": binance_last,
            "binance_quote_volume_24h": binance_qv,
            "spread_pct": sp,
            "dex": dex_info,
            "_score": score(vol, mcap, binance_qv, sp),
        })

    items.sort(key=lambda x: x["_score"], reverse=True)
    items = items[:limit]

    for i, it in enumerate(items, 1):
        it["rank"] = i
        it.pop("_score", None)

    return items

def main():
    os.makedirs("data", exist_ok=True)

    rows = fetch_listings(fetch_limit=600)
    book_map, t24_map = fetch_binance_maps()

    top = build_top(rows, book_map, t24_map, limit=TOP_N)

    payload = {
        "updated_utc": datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "criteria": (
            f"mcap>={int(MIN_MCAP)}, vol24>={int(MIN_VOL)}, "
            f"exclude stable/wrapped, binance spread<={MAX_SPREAD_PCT}%"
            + (f", dex liq>={int(DEX_MIN_LIQ)}" if USE_DEX else "")
        ),
        "items": top
    }

    with open("data/top20.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"Saved data/top20.json with {len(top)} items")

if __name__ == "__main__":
    main()
