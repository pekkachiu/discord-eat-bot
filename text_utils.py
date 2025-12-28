import re
from datetime import datetime
from typing import Optional, Tuple

MD_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^\s)]+)\)")
BARE_URL = re.compile(r"(?<!<)(https?://[^\s<>()]+)")

MEAL_KEYWORDS = {
    "早餐": ["早餐", "早午餐", "brunch", "早安"],
    "午餐": ["午餐", "中午", "午飯", "午餐飯", "午餐吃", "午餐點"],
    "下午茶": ["下午茶", "點心", "甜點", "咖啡廳"],
    "晚餐": ["晚餐", "晚飯", "晚點吃", "晚上吃", "晚間"],
    "宵夜": ["宵夜", "消夜", "夜宵", "半夜", "凌晨"],
}


def make_urls_clickable(text: str) -> str:
    # Keep all bare URLs so Discord converts them to clickable links.
    def md_repl(match: re.Match) -> str:
        label, url = match.groups()
        label_clean = label.strip()
        if label_clean == url:
            return url
        return f"{label_clean}：{url}"

    text = MD_LINK.sub(md_repl, text)
    def bare_repl(match: re.Match) -> str:
        url = match.group(1)
        # Trim trailing punctuation so the URL doesn't absorb following text.
        return url.rstrip("。！？!?，,；;：:）)」』")

    text = BARE_URL.sub(bare_repl, text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_nutrition_target(text: str) -> str:
    cleaned = re.sub(r"(請問|請幫我|幫我|想知道|查詢|查|一下|可以|嗎|？|\?)", "", text)
    cleaned = re.sub(r"(營養成分|營養|熱量|卡路里|蛋白質|碳水|脂肪|多少)", "", cleaned)
    cleaned = cleaned.strip()
    return cleaned or text


def extract_city(text: str) -> str:
    mapping = {
        "基隆": "Keelung",
        "新北": "New Taipei",
        "新北市": "New Taipei",
        "台南": "Tainan",
        "臺南": "Tainan",
        "台北": "Taipei",
        "臺北": "Taipei",
        "桃園": "Taoyuan",
        "新竹": "Hsinchu",
        "新竹市": "Hsinchu",
        "新竹縣": "Hsinchu",
        "苗栗": "Miaoli",
        "高雄": "Kaohsiung",
        "台中": "Taichung",
        "臺中": "Taichung",
        "彰化": "Changhua",
        "南投": "Nantou",
        "雲林": "Yunlin",
        "嘉義": "Chiayi",
        "嘉義市": "Chiayi",
        "嘉義縣": "Chiayi",
        "屏東": "Pingtung",
        "宜蘭": "Yilan",
        "花蓮": "Hualien",
        "台東": "Taitung",
        "臺東": "Taitung",
        "澎湖": "Penghu",
        "金門": "Kinmen",
        "連江": "Lienchiang",
    }
    for k, v in mapping.items():
        if k in text:
            return v
    eng_loc = extract_english_location(text)
    if eng_loc:
        return eng_loc
    return "Tainan"


def extract_english_location(text: str) -> str:
    prep = re.search(r"\b(?:in|near|at|around)\s+([A-Za-z][A-Za-z .,'-]{1,50})", text, re.IGNORECASE)
    match = prep.group(1) if prep else None
    if not match:
        eng = re.search(r"[A-Za-z][A-Za-z .,'-]{1,50}", text)
        match = eng.group(0) if eng else ""
    if not match:
        return ""
    cleaned = re.sub(r"[^\w\s'-]", " ", match)
    words = cleaned.strip().split()
    stop = {
        "weather", "forecast", "temperature", "temp", "now", "today",
        "please", "check", "in", "at", "for", "the", "a", "an",
        "near", "around",
    }
    kept = [w for w in words if w.lower() not in stop]
    food_words = {
        "ramen", "sushi", "pizza", "burger", "steak", "noodle", "noodles",
        "bbq", "coffee", "tea", "brunch", "breakfast", "lunch", "dinner",
        "hotpot", "noodles", "noodle",
    }
    while kept and kept[-1].lower() in food_words:
        kept.pop()
    if not kept:
        return ""
    return " ".join(kept)


# Find user mentioned city, return (English city, search location label)
def detect_food_location(text: str) -> Tuple[str, str]:
    station_match = re.search(r"([\u4e00-\u9fffA-Za-z0-9]+(?:火車站|車站|捷運站))", text)
    if station_match:
        label = station_match.group(1)
        city_keywords = [
            (["台北", "臺北", "松山", "信義", "大安", "中山", "士林", "內湖", "文山", "北投", "南港", "萬華", "中正", "大同"], "Taipei"),
            (["新北", "新北市", "板橋", "三重", "新莊", "中和", "永和", "新店", "土城", "蘆洲", "汐止"], "New Taipei"),
            (["桃園", "中壢", "龜山", "蘆竹", "大園", "八德"], "Taoyuan"),
            (["台中", "臺中"], "Taichung"),
            (["台南", "臺南", "成大", "成功大學"], "Tainan"),
            (["高雄"], "Kaohsiung"),
        ]
        for keywords, city in city_keywords:
            if any(k in text for k in keywords):
                return (city, label)
        return ("Tainan", label)

    mapping = [
        (["台北", "臺北", "台北市"], ("Taipei", "台北市")),
        (["新北", "新北市"], ("New Taipei", "新北市")),
        (["桃園", "桃園市"], ("Taoyuan", "桃園市")),
        (["台中", "臺中", "台中市"], ("Taichung", "台中市")),
        (["高雄", "高雄市"], ("Kaohsiung", "高雄市")),
        (["台南", "臺南", "台南市", "成功大學", "成大"], ("Tainan", "國立成功大學")),
    ]
    for keywords, result in mapping:
        if any(k in text for k in keywords):
            return result
    eng_loc = extract_english_location(text)
    if eng_loc:
        return (eng_loc, eng_loc)
    return ("Tainan", "國立成功大學")


def detect_meal_from_text(text: str) -> Optional[str]:
    for meal, kws in MEAL_KEYWORDS.items():
        if any(k in text for k in kws):
            return meal
    return None


def infer_meal_by_time(now: datetime) -> str:
    # 05:00-10:30 breakfast; 10:30-13:30 lunch; 13:30-17:00 tea; 17:00-21:00 dinner; 21:00-05:00 late night
    hour = now.hour + now.minute / 60
    if 5 <= hour < 10.5:
        return "早餐"
    if 10.5 <= hour < 13.5:
        return "午餐"
    if 13.5 <= hour < 17:
        return "下午茶"
    if 17 <= hour < 21:
        return "晚餐"
    return "宵夜"


def extract_food_filters(
    text: str,
    default_max_travel_time: int = 20,
    default_min_rating: float = 3.5,
    default_min_reviews: int = 0,
    default_travel_mode: str = "walking",
) -> Tuple[int, float, int, str]:
    max_travel_time = default_max_travel_time
    min_rating = default_min_rating
    min_reviews = default_min_reviews
    travel_mode = default_travel_mode

    if re.search(r"(車程|開車|駕車|行車|車行|汽車)", text):
        travel_mode = "driving"
    elif re.search(r"(步行|走路)", text):
        travel_mode = "walking"
    elif re.search(r"(騎車|自行車|腳踏車|單車)", text):
        travel_mode = "bicycling"

    time_match = re.search(
        r"(?:車程|開車|駕車|行車|車行|步行|走路|騎車|自行車|腳踏車|單車)?\s*(\d{1,3})\s*分(?:鐘)?\s*(?:內|以內|左右)?",
        text,
    )
    if time_match:
        try:
            max_travel_time = int(time_match.group(1))
        except ValueError:
            pass

    rating_match = re.search(
        r"(?:評分|評價)?\s*([0-5](?:\.\d)?)\s*星?\s*(?:以上|起|或以上)",
        text,
    )
    if rating_match:
        try:
            min_rating = float(rating_match.group(1))
        except ValueError:
            pass

    reviews_match = re.search(
        r"(?:至少|最少)?\s*(\d{2,6})\s*(?:則|个|個)?\s*評?論(?:數量)?\s*(?:以上|起|或以上)?",
        text,
    )
    if reviews_match:
        try:
            min_reviews = int(reviews_match.group(1))
        except ValueError:
            pass

    return max_travel_time, min_rating, min_reviews, travel_mode
