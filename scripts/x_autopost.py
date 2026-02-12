import os
import json
import hashlib
import random
import time
from datetime import datetime, timezone

import requests
from requests_oauthlib import OAuth1Session
from PIL import Image, ImageDraw, ImageFont


# ================= CONFIG =================

OUT_DIR = "out"
TWEET_FILE = os.path.join(OUT_DIR, "tweet.txt")
STATE_FILE = os.path.join(OUT_DIR, "last_post.json")
DEBUG_FILE = os.path.join(OUT_DIR, "cmc_debug.json")
IMAGE_FILE = os.path.join(OUT_DIR, "top15.png")

X_POST_URL = "https://api.x.com/2/tweets"
MEDIA_UPLOAD_URL = "https://upload.twitter.com/1.1/media/upload.json"
CMC_PRO_BASE = "https://pro-api.coinmarketcap.com"

MAX_RETRIES = 3
RETRY_DELAY = 20


# ================= HELPERS =================

def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_state(state):
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def save_debug(data):
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(DEBUG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _req_json(url, params=None, headers=None):
    try:
        r = requests.get(url, params=params or {}, headers=headers or {}, timeout=30)
        if r.status_code != 200:
            print(f"Request failed {url} -> {r.status_code} | {r.text}")
            return None
        return r.json()
    except Exception as e:
        print(f"Request exception {url} -> {e}")
        return None


# ================= FETCH DATA =================

def fetch_trending_top15():
    cmc_key = os.getenv("CMC_KEY")

    if cmc_key:
        url = f"{CMC_PRO_BASE}/v1/cryptocurrency/trending/latest"
        headers = {"X-CMC_PRO_API_KEY": cmc_key}
        j = _req_json(url, params={"start": 1, "limit": 15}, headers=headers)
        if j and isinstance(j.get("data"), list):
            return [x["symbol"] for x in j["data"] if "symbol" in x][:15]

    url = "https://api.coingecko.com/api/v3/search/trending"
    j = _req_json(url)
    if j and isinstance(j.get("coins"), list):
        out = []
        for c in j["coins"]:
            sym = (c.get("item") or {}).get("symbol")
            if sym:
                out.append(sym.upper())
            if len(out) >= 15:
                break
        return out

    return []


# ================= IMAGE =================

def generate_image(symbols):
    width, height = 900, 900
    bg = (random.randint(15, 40), random.randint(15, 40), random.randint(15, 40))

    img = Image.new("RGB", (width, height), bg)
    draw = ImageDraw.Draw(img)

    try:
        font_title = ImageFont.truetype("DejaVuSans-Bold.ttf", 60)
        font_text = ImageFont.truetype("DejaVuSans.ttf", 40)
    except:
        font_title = ImageFont.load_default()
        font_text = ImageFont.load_default()

    draw.text((width // 2, 90), "Top 15 Market Movers",
              font=font_title, fill="white", anchor="mm")

    y = 180
    for i, sym in enumerate(symbols, 1):
        draw.text((150, y), f"{i}. ${sym}", font=font_text, fill="white")
        y += 45

    os.makedirs(OUT_DIR, exist_ok=True)
    img.save(IMAGE_FILE)


# ================= POST TO X =================

def post_to_x(text, image_path=None):
    required = ["X_API_KEY", "X_API_SECRET",
                "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET"]

    for k in required:
        if not os.getenv(k):
            print(f"Missing env key: {k}")
            return None

    oauth = OAuth1Session(
        os.getenv("X_API_KEY"),
        client_secret=os.getenv("X_API_SECRET"),
        resource_owner_key=os.getenv("X_ACCESS_TOKEN"),
        resource_owner_secret=os.getenv("X_ACCESS_TOKEN_SECRET"),
    )

    media_id = None

    if image_path and os.path.exists(image_path):
        with open(image_path, "rb") as f:
            r = oauth.post(MEDIA_UPLOAD_URL, files={"media": f})

        if r.status_code == 200:
            media_id = r.json().get("media_id_string")
        else:
            print(f"Media upload failed: {r.status_code} | {r.text}")

    payload = {"text": text}
    if media_id:
        payload["media"] = {"media_ids": [media_id]}

    r = oauth.post(X_POST_URL, json=payload)

    if r.status_code in (200, 201):
        return r.json()

    print(f"Tweet failed: {r.status_code} | {r.text}")
    return None


# ================= BUILD =================

def build_tweet():
    symbols = []

    for attempt in range(MAX_RETRIES):
        symbols = fetch_trending_top15()
        if symbols:
            break
        print(f"Retry {attempt+1}...")
        time.sleep(RETRY_DELAY)

    save_debug({
        "utc": datetime.now(timezone.utc).isoformat(),
        "symbols": symbols
    })

    if not symbols:
        return None

    generate_image(symbols)
    return "🚀 Top 15 Market Movers"


# ================= MAIN =================

def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    tweet = build_tweet()
    if not tweet:
        print("No data fetched. Skipping post.")
        return

    state = load_state()
    h = sha(tweet)

    if state.get("last_hash") == h:
        print("Duplicate content. Skipping.")
        return

    with open(TWEET_FILE, "w", encoding="utf-8") as f:
        f.write(tweet)

    resp = post_to_x(tweet, IMAGE_FILE)
    tweet_id = (resp or {}).get("data", {}).get("id")

    state.update({
        "last_hash": h,
        "last_tweet_id": tweet_id,
        "last_text": tweet,
        "posted_at_utc": datetime.now(timezone.utc).isoformat()
    })

    save_state(state)

    print("Done.")


if __name__ == "__main__":
    main()
