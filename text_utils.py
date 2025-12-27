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
    text = BARE_URL.sub(lambda m: m.group(1), text)
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
        "台南": "Tainan",
        "臺南": "Tainan",
        "台北": "Taipei",
        "臺北": "Taipei",
        "高雄": "Kaohsiung",
        "台中": "Taichung",
        "臺中": "Taichung",
    }
    for k, v in mapping.items():
        if k in text:
            return v
    return "Tainan"


# Find user mentioned city, return (English city, search location label)
def detect_food_location(text: str) -> Tuple[str, str]:
    mapping = [
        (["台北", "臺北", "台北市"], ("Taipei", "台北市")),
        (["新北", "新北市"], ("New Taipei", "新北市")),
        (["台中", "臺中", "台中市"], ("Taichung", "台中市")),
        (["高雄", "高雄市"], ("Kaohsiung", "高雄市")),
        (["台南", "臺南", "台南市", "成功大學", "成大"], ("Tainan", "國立成功大學")),
    ]
    for keywords, result in mapping:
        if any(k in text for k in keywords):
            return result
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
