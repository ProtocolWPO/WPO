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


# ================= TEXT VARIATIONS (50 sentences each) =================

LANG_TEMPLATES = {
    "ar": {
        "open": [
            "سوق الكريبتو لا ينتظر المترددين.",
            "الفرصة في الكريبتو تأتي مرة… ومن يلتقطها يربح.",
            "المال يتدفق لمن يقرأ الاتجاه قبل الجميع.",
            "التحركات الصغيرة اليوم تصنع ثروات الغد.",
            "لا تتبع القطيع… السوق يكافئ التفكير المستقل.",
            "الكريبتو لعبة سرعة، وليس مجرد انتظار.",
            "من يفهم السوق اليوم، يسبق العالم غدًا.",
            "لا ضجيج… الأرقام هي التي تتكلم.",
            "الاتجاه يصنع الثروة، لا الأمنيات.",
            "الفرص موجودة، لكن العيون الذكية فقط تراها.",
            "السوق يتحرك… فهل تتحرك معه؟",
            "كل يوم تأخير قد يعني فرصة مفقودة.",
            "المال يحب من يقرأ الإشارات مبكرًا.",
            "ليس المهم أن تعرف… المهم أن تتصرف.",
            "الكريبتو ليس حظًا، بل فهم وتحليل.",
            "التحليل يسبق القرار… والقرار يسبق الربح.",
            "لا تنتظر القاع… ركّز على الاتجاه.",
            "الأسواق تكافئ الصبر… لكن تكافئ الفهم أكثر.",
            "الذكي لا يلاحق السعر، بل يقرأ الاتجاه.",
            "الثروات تُبنى بالقرارات… لا بالمشاعر."
        ],
        "close": [
            "تحرك مبكرًا… السوق لا يمنح فرصًا متكررة.",
            "الفرصة لا تنتظر أحدًا. من يتحرك أولًا يسبق.",
            "خطوة صغيرة اليوم قد تصنع فرقًا كبيرًا.",
            "السوق لا يرحم المترددين.",
            "القرار اليوم قد يغير مستقبلك المالي.",
            "النجاح في الكريبتو لمن يفهم، لا لمن يتمنى.",
            "السوق يعطي… لكن لمن يستحق.",
            "استثمر بعقل… لا بعاطفة.",
            "الفرص تأتي… لكن الفائز هو من يلتقطها.",
            "استثمر بذكاء، وراقب الاتجاه.",
            "لا تتأخر… الفرصة تتحرك بسرعة.",
            "من يسبق السوق، يسبق الأرباح.",
            "القرار اليوم = نتيجة الغد.",
            "الاستثمار رحلة… وليست مقامرة.",
            "المعرفة قوة… والقرار هو الفارق.",
            "الفرصة موجودة… لكن تحتاج عينًا ترى.",
            "الصبر يصنع الفارق.",
            "لا ربح بدون فهم.",
            "الذكاء في التوقيت.",
            "النجاح قرار."
        ]
    },
    "en": {
        "open": [
            "The crypto market rewards preparation, not hesitation.",
            "Opportunities come once. Those who act win.",
            "Capital flows to those who read the trend early.",
            "Small moves today build big wins tomorrow.",
            "Markets reward independent thinking.",
            "Crypto is speed and strategy, not waiting.",
            "Understanding the trend beats guessing.",
            "Data drives success, not emotions.",
            "The market moves. Are you moving?",
            "Opportunity favors the prepared.",
            "Smart money acts first.",
            "Trends shape wealth.",
            "Timing matters more than perfection.",
            "Knowledge beats hype.",
            "Markets reward discipline.",
            "Invest in understanding.",
            "Decisions create results.",
            "Growth comes from action.",
            "Patience and strategy win.",
            "Crypto rewards those who learn."
        ],
        "close": [
            "Move early. Opportunities don’t wait.",
            "The next wave favors the prepared.",
            "Data and action beat hope.",
            "Position smart. Stay ahead.",
            "Crypto rewards understanding, not guessing.",
            "Opportunities reward decisive action.",
            "The market respects preparation.",
            "Strategy beats emotion.",
            "Timing creates advantage.",
            "Invest with purpose.",
            "Growth comes from action.",
            "Markets reward discipline.",
            "The future favors the prepared.",
            "Success is a choice.",
            "Stay informed. Stay ahead.",
            "Smart decisions build wealth.",
            "Patience creates opportunity.",
            "Knowledge is power.",
            "Action defines winners.",
            "Results come from discipline."
        ]
    },
    "ko": {
        "open": [
            "암호화폐 시장은 준비된 자에게 기회를 준다.",
            "기회는 한 번 온다. 먼저 움직이는 사람이 승리한다.",
            "자본은 흐름을 읽는 사람에게 향한다.",
            "작은 움직임이 큰 결과를 만든다.",
            "시장보다 먼저 생각하라.",
            "암호화폐는 속도와 전략이다.",
            "데이터가 결정을 만든다.",
            "트렌드를 이해하는 사람이 앞선다.",
            "기회는 준비된 자의 것이다.",
            "시장에 맞춰 움직여라.",
            "스마트 머니는 먼저 움직인다.",
            "흐름을 읽어라.",
            "행동이 결과를 만든다.",
            "지식이 힘이다.",
            "시장보다 앞서 생각하라.",
            "투자는 이해에서 시작된다.",
            "성장은 행동에서 나온다.",
            "기회는 배우는 자의 것이다.",
            "전략이 중요하다.",
            "결정이 차이를 만든다."
        ],
        "close": [
            "먼저 움직이는 사람이 시장을 지배한다.",
            "기회는 기다리지 않는다.",
            "데이터와 행동이 승리를 만든다.",
            "현명하게 투자하고 앞서가라.",
            "시장에 맞춰 움직여야 살아남는다.",
            "기회는 준비된 자의 것이다.",
            "전략이 성공을 만든다.",
            "데이터가 답이다.",
            "행동이 중요하다.",
            "지식이 차이를 만든다.",
            "결정이 결과를 만든다.",
            "시장을 이해하라.",
            "스마트하게 투자하라.",
            "성공은 선택이다.",
            "배움이 경쟁력이다.",
            "전략이 승리한다.",
            "흐름을 읽어라.",
            "기회는 행동하는 자의 것.",
            "시장보다 앞서라.",
            "결과는 준비에서 온다."
        ]
    },
    "zh": {
        "open": [
            "加密市场奖励准备充分的人。",
            "机会稍纵即逝，先行动才能赢。",
            "资金流向能够读懂趋势的人。",
            "小行动创造大机会。",
            "趋势比预测更重要。",
            "加密市场属于行动者。",
            "数据胜过猜测。",
            "机会属于准备好的人。",
            "趋势决定财富。",
            "市场不会等待。",
            "聪明资金先行。",
            "理解趋势更重要。",
            "行动创造结果。",
            "知识就是力量。",
            "机会需要准备。",
            "投资需要策略。",
            "数据驱动成功。",
            "市场奖励纪律。",
            "时间创造价值。",
            "未来属于准备者."
        ],
        "close": [
            "机会属于先行动的人。",
            "市场不会等待犹豫者。",
            "数据胜过猜测。",
            "聪明交易，保持领先。",
            "趋势决定财富方向。",
            "行动创造机会。",
            "策略胜过情绪。",
            "数据是答案。",
            "投资需要纪律。",
            "知识创造优势。",
            "时间创造机会。",
            "市场奖励准备。",
            "未来属于行动者。",
            "成功来自选择。",
            "理解市场。",
            "保持领先。",
            "决策决定结果。",
            "机会属于准备者。",
            "趋势胜过预测。",
            "结果来自行动."
        ]
    },
    "id": {
        "open": [
            "Pasar kripto memberi peluang bagi yang siap.",
            "Peluang datang sekali. Bergeraklah lebih cepat.",
            "Modal mengalir ke yang memahami tren.",
            "Langkah kecil hari ini, hasil besar besok.",
            "Keputusan cerdas membangun kesuksesan.",
            "Kripto butuh strategi, bukan keberuntungan.",
            "Data lebih penting dari tebakan.",
            "Peluang milik yang bertindak.",
            "Tren membangun kekayaan.",
            "Pasar tidak menunggu.",
            "Uang pintar bergerak dulu.",
            "Pahami arus pasar.",
            "Tindakan menciptakan hasil.",
            "Pengetahuan adalah kekuatan.",
            "Strategi mengalahkan emosi.",
            "Investasi butuh pemahaman.",
            "Keputusan menciptakan peluang.",
            "Kesuksesan dari tindakan.",
            "Pasar memberi hadiah pada disiplin.",
            "Waktu menciptakan nilai."
        ],
        "close": [
            "Peluang tidak menunggu.",
            "Bertindak cepat memberi keuntungan.",
            "Pasar menghargai persiapan.",
            "Berinvestasi dengan cerdas.",
            "Keputusan hari ini menentukan masa depan.",
            "Strategi lebih penting dari keberuntungan.",
            "Data membawa hasil.",
            "Tindakan menciptakan peluang.",
            "Disiplin membawa sukses.",
            "Pemahaman pasar penting.",
            "Waktu adalah aset.",
            "Keputusan menentukan hasil.",
            "Peluang milik yang bertindak.",
            "Belajar membawa keunggulan.",
            "Pasar memberi hadiah pada kesiapan.",
            "Hasil datang dari usaha.",
            "Investasi dengan strategi.",
            "Pahami tren.",
            "Kesuksesan dari keputusan.",
            "Peluang dari tindakan."
        ]
    }
}

HASHTAGS = [
    "#Crypto", "#Bitcoin", "#Ethereum", "#DeFi", "#Web3",
    "#Altcoins", "#Trading", "#Blockchain", "#CryptoNews", "#Investing",
    "#BullRun", "#HODL", "#Token", "#NFT", "#ProtocolWPO",
    "#CryptoMarket", "#SmartMoney", "#Layer2", "#BullMarket", "#CryptoTrends"
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

last_lang = None  # منع تكرار اللغة مرتين

def build_tweet():

    global last_lang

    symbols = []

    for _ in range(MAX_RETRIES):
        symbols = fetch_trending()
        if symbols:
            break
        time.sleep(RETRY_DELAY)

    if not symbols:
        return None

    random.shuffle(symbols)

    # اختيار لغة عشوائية لا تتكرر مرتين
    available_langs = list(LANG_TEMPLATES.keys())
    if last_lang in available_langs:
        available_langs.remove(last_lang)

    lang = random.choice(available_langs)
    last_lang = lang

    template = LANG_TEMPLATES[lang]

    opener = random.choice(template["open"])
    closer = random.choice(template["close"])

    # أفضل 10 عملات
    body = " | ".join([f"${s}" for s in symbols[:10]])

    # هاشتاج واحد فقط
    hashtag = random.choice(HASHTAGS)

    tweet = f"""{opener}

Trending Now:
{body}

{closer} {hashtag}
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
