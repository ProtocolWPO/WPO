import os
import json
import hashlib
import random
from datetime import datetime, timezone

import requests
from requests_oauthlib import OAuth1Session
from PIL import Image, ImageDraw, ImageFont

OUT_DIR = "out"
TWEET_FILE = os.path.join(OUT_DIR, "tweet.txt")
STATE_FILE = os.path.join(OUT_DIR, "last_post.json")
DEBUG_FILE = os.path.join(OUT_DIR, "cmc_debug.json")
IMAGE_FILE = os.path.join(OUT_DIR, "top15.png")

X_POST_URL = "https://api.x.com/2/tweets"
MEDIA_UPLOAD_URL = "https://upload.twitter.com/1.1/media/upload.json"

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
        if r.status_code != 200:
            return None
        return r.json()
    except:
        return None


def fetch_trending_top15():
    cmc_key = os.getenv("CMC_KEY")

    if cmc_key:
        url = f"{CMC_PRO_BASE}/v1/cryptocurrency/trending/latest"
        headers = {"X-CMC_PRO_API_KEY": cmc_key}
        j = _req_json(url, params={"start": 1, "limit": 15}, headers=headers)
        if j and isinstance(j.get("data"), list):
            return [it.get("symbol") for it in j["data"] if it.get("symbol")][:15]

    url = "https://api.coinmarketcap.com/data-api/v3/cryptocurrency/listing"
    params = {
        "start": 1,
        "limit": 15,
        "sortBy": "trendingScore",
        "sortType": "desc",
        "timeframe": "1h",
    }
    j = _req_json(url, params=params)
    if j:
        lst = (j.get("data") or {}).get("cryptoCurrencyList") or []
        return [it.get("symbol") for it in lst if it.get("symbol")][:15]

    url = "https://api.coingecko.com/api/v3/search/trending"
    j = _req_json(url)
    if j and isinstance(j.get("coins"), list):
        out = []
        for it in j["coins"]:
            sym = (it.get("item") or {}).get("symbol")
            if sym:
                out.append(sym.upper())
            if len(out) >= 15:
                break
        return out

    return []


# ================= IMAGE GENERATOR =================

def generate_image(symbols):
    width = 900
    height = 900

    bg_color = (
        random.randint(10, 40),
        random.randint(10, 40),
        random.randint(10, 40),
    )

    img = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    try:
        font_title = ImageFont.truetype("arial.ttf", 60)
        font_text = ImageFont.truetype("arial.ttf", 40)
    except:
        font_title = ImageFont.load_default()
        font_text = ImageFont.load_default()

    draw.text((width // 2, 80), "Top 15 Market Movers",
              font=font_title, fill="white", anchor="mm")

    y = 180
    for i, sym in enumerate(symbols, start=1):
        line = f"{i}. ${sym}"
        draw.text((150, y), line, font=font_text, fill="white")
        y += 45

    img.save(IMAGE_FILE)


# ================= POST TO X =================

def post_to_x(text: str, image_path=None):
    for k in ["X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET"]:
        if not os.getenv(k):
            return {"skipped": True}

    oauth = OAuth1Session(
        client_key=os.getenv("X_API_KEY"),
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

    payload = {"text": text}
    if media_id:
        payload["media"] = {"media_ids": [media_id]}

    r = oauth.post(X_POST_URL, json=payload)

    if r.status_code in (200, 201):
        return r.json()

    return {"skipped": True}


# ================= BUILD TWEET =================

def build_tweet():
    symbols = fetch_trending_top15()

    save_debug({
        "utc": datetime.now(timezone.utc).isoformat(),
        "symbols": symbols,
    })

    if symbols:
        generate_image(symbols)
        return "Top 15 Market Movers"

    return "Trending data temporarily unavailable."


# ================= MAIN =================

def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    tweet = build_tweet()

    with open(TWEET_FILE, "w", encoding="utf-8") as f:
        f.write(tweet)

    state = load_state()
    h = sha(tweet)

    resp = post_to_x(tweet, IMAGE_FILE)

    tweet_id = (resp or {}).get("data", {}).get("id")

    state.update({
        "last_hash": h,
        "last_tweet_id": tweet_id,
        "last_text": tweet,
        "posted_at_utc": datetime.now(timezone.utc).isoformat(),
    })
    save_state(state)

    print("Done.")


if __name__ == "__main__":
    main()
