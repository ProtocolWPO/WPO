import os
import json
import hashlib
import random
import time
from datetime import datetime, timezone

import requests
from requests_oauthlib import OAuth1Session


# ================= CONFIG =================

OUT_DIR = "out"
STATE_FILE = os.path.join(OUT_DIR, "last_post.json")

X_POST_URL = "https://api.x.com/2/tweets"
CMC_PRO_BASE = "https://pro-api.coinmarketcap.com"

MAX_RETRIES = 3
RETRY_DELAY = 20


# ================= TEXT VARIATIONS =================

OPENERS = [
    "🚨 Smart money is rotating...",
    "🔥 Momentum is building fast...",
    "👀 Traders are watching closely...",
    "📊 Capital is flowing into...",
    "⚡ Volatility is rising around...",
    "💎 Accumulation phase detected..."
]

CLOSERS = [
    "Whale Protocol tracks the moves before the breakout. 🐋",
    "Stay ahead. Follow the flow. 🚀",
    "Liquidity tells the story — we decode it.",
    "Position smart. Move early.",
    "The next wave starts before the crowd sees it.",
    "Data > Hype. Always."
]


# ================= HELPERS =================

def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}


def save_state(state):
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def fetch_trending():
    cmc_key = os.getenv("CMC_KEY")

    if cmc_key:
        url = f"{CMC_PRO_BASE}/v1/cryptocurrency/trending/latest"
        headers = {"X-CMC_PRO_API_KEY": cmc_key}
        r = requests.get(url, headers=headers, timeout=30)
        if r.status_code == 200:
            data = r.json().get("data", [])
            return [x["symbol"] for x in data if "symbol" in x][:10]

    url = "https://api.coingecko.com/api/v3/search/trending"
    r = requests.get(url, timeout=30)
    if r.status_code == 200:
        data = r.json().get("coins", [])
        out = []
        for c in data:
            sym = (c.get("item") or {}).get("symbol")
            if sym:
                out.append(sym.upper())
        return out[:10]

    return []


# ================= BUILD SMART TWEET =================

def build_tweet():

    symbols = []

    for _ in range(MAX_RETRIES):
        symbols = fetch_trending()
        if symbols:
            break
        time.sleep(RETRY_DELAY)

    if not symbols:
        return None

    random.shuffle(symbols)

    opener = random.choice(OPENERS)
    closer = random.choice(CLOSERS)

    body = " | ".join([f"${s}" for s in symbols[:5]])

    tweet = f"""{opener}

Trending Now:
{body}

{closer}
"""

    return tweet.strip()


# ================= POST =================

def post_to_x(text):

    oauth = OAuth1Session(
        os.getenv("X_API_KEY"),
        client_secret=os.getenv("X_API_SECRET"),
        resource_owner_key=os.getenv("X_ACCESS_TOKEN"),
        resource_owner_secret=os.getenv("X_ACCESS_TOKEN_SECRET"),
    )

    r = oauth.post(X_POST_URL, json={"text": text})

    if r.status_code in (200, 201):
        return r.json()

    print(f"Post failed: {r.status_code} | {r.text}")
    return None


# ================= MAIN =================

def main():

    os.makedirs(OUT_DIR, exist_ok=True)

    tweet = build_tweet()

    if not tweet:
        print("No trending data.")
        return

    state = load_state()
    h = sha(tweet)

    if state.get("last_hash") == h:
        print("Duplicate detected. Skipping.")
        return

    resp = post_to_x(tweet)
    tweet_id = (resp or {}).get("data", {}).get("id")

    state.update({
        "last_hash": h,
        "last_tweet_id": tweet_id,
        "posted_at_utc": datetime.now(timezone.utc).isoformat()
    })

    save_state(state)

    print("Posted successfully.")


if __name__ == "__main__":
    main()

