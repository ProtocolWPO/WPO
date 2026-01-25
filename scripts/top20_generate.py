import os, json, datetime
import requests

CMC_KEY = os.getenv("CMC_KEY")

def fetch_listings(fetch_limit=200):
    url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest"
    headers = {"X-CMC_PRO_API_KEY": CMC_KEY}
    params = {
        "start": 1,
        "limit": fetch_limit,
        "convert": "USD",
        "sort": "volume_24h",
        "sort_dir": "desc",
    }
    r = requests.get(url, headers=headers, params=params, timeout=30)
    r.raise_for_status()
    return r.json()["data"]

def score(volume_24h, market_cap):
    # مؤشر سيولة/نشاط بسيط: Volume + نسبة Volume/MarketCap
    # يعطي توازن بين الحجم والسيولة النسبية
    if market_cap and market_cap > 0:
        ratio = volume_24h / market_cap
    else:
        ratio = 0.0
    return (volume_24h * 0.8) + (ratio * 0.2 * 1e9)  # وزن بسيط، قابل للتعديل

def build_top20(rows, limit=20):
    items = []
    for row in rows:
        q = row.get("quote", {}).get("USD", {})
        vol = float(q.get("volume_24h") or 0.0)
        mcap = float(q.get("market_cap") or 0.0)
        price = float(q.get("price") or 0.0)

        if vol <= 0 or mcap <= 0:
            continue

        items.append({
            "symbol": row.get("symbol", ""),
            "name": row.get("name", ""),
            "price": price,
            "volume_24h": vol,
            "market_cap": mcap,
            "vol_mcap_ratio": vol / mcap if mcap > 0 else 0,
            "score": score(vol, mcap),
        })

    items.sort(key=lambda x: x["score"], reverse=True)
    items = items[:limit]

    # أضف ترتيب
    for i, it in enumerate(items, 1):
        it["rank"] = i
        it.pop("score", None)

    return items

def main():
    if not CMC_KEY:
        raise SystemExit("Missing CMC_KEY")

    os.makedirs("data", exist_ok=True)

    rows = fetch_listings(fetch_limit=200)
    top20 = build_top20(rows, limit=20)

    payload = {
        "updated_utc": datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "criteria": "Ranked by combined score: 24h Volume + (Volume/MarketCap ratio)",
        "items": top20
    }

    with open("data/top20.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
