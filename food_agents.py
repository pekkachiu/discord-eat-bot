import asyncio
import json
import re
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional

import httpx

import config  # Load .env before food_tool import.
from food_tool import Tools as FoodTools
from llm_client import llm_generate
from nutrition import llm_translate_list, usda_food_nutrition
from style_store import get_guild_style
from text_utils import (
    detect_food_location,
    detect_meal_from_text,
    extract_city,
    extract_food_filters,
    extract_nutrition_target,
    infer_meal_by_time,
)

food = FoodTools()


async def get_current_weather(city: str) -> dict:
    async with httpx.AsyncClient(timeout=15) as http:
        geo = await http.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city, "count": 1, "language": "zh", "format": "json"},
        )
        geo.raise_for_status()
        g = geo.json()
        if "results" not in g or not g["results"]:
            return {"city": city, "error": "找不到城市"}

        lat = g["results"][0]["latitude"]
        lon = g["results"][0]["longitude"]

        w = await http.get(
            "https://api.open-meteo.com/v1/forecast",
            params={"latitude": lat, "longitude": lon, "current_weather": True},
        )
        w.raise_for_status()
        cw = w.json().get("current_weather", {})
        return {
            "city": city,
            "temperature_c": cw.get("temperature"),
            "windspeed": cw.get("windspeed"),
            "weathercode": cw.get("weathercode"),
        }

async def get_weather_by_location(location: str) -> Optional[dict]:
    try:
        latlon = await asyncio.to_thread(food._geocode, location)
    except Exception:
        return None
    try:
        lat_str, lon_str = latlon.split(",", 1)
        lat = float(lat_str)
        lon = float(lon_str)
    except Exception:
        return None
    async with httpx.AsyncClient(timeout=15) as http:
        w = await http.get(
            "https://api.open-meteo.com/v1/forecast",
            params={"latitude": lat, "longitude": lon, "current_weather": True},
        )
        w.raise_for_status()
        cw = w.json().get("current_weather", {})
        return {
            "city": location,
            "temperature_c": cw.get("temperature"),
            "windspeed": cw.get("windspeed"),
            "weathercode": cw.get("weathercode"),
        }


async def find_food(
    keyword: str,
    location: str = "國立成功大學",
    max_travel_time: int = 20,
    min_rating: float = 3.5,
    min_reviews: int = 0,
    travel_mode: str = "walking",
    ) -> str:
    return await asyncio.to_thread(
        food.find_food,
        keyword,
        location,
        max_travel_time,
        min_rating,
        min_reviews,
        travel_mode,
    )

async def llm_extract_food_query(user_text: str) -> tuple[str, str]:
    prompt = (
        "請從使用者句子中抽出「地點」與「餐點」。\n"
        "只輸出 JSON，格式：{\"location\": \"...\", \"dish\": \"...\"}\n"
        "若未提到地點或餐點，請用空字串。\n"
        f"使用者：{user_text}"
    )
    try:
        raw = (await llm_generate(prompt)).strip()
    except Exception:
        return ("", "")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        try:
            start = raw.find("{")
            end = raw.rfind("}")
            if start != -1 and end != -1 and end > start:
                data = json.loads(raw[start:end + 1])
            else:
                return ("", "")
        except Exception:
            return ("", "")

    location = str(data.get("location", "") or "").strip()
    dish = str(data.get("dish", "") or "").strip()
    return (dish, location)


async def llm_extract_food_filters(
    user_text: str,
    default_max_travel_time: int = 20,
    default_min_rating: float = 3.5,
    default_min_reviews: int = 0,
    default_travel_mode: str = "walking",
) -> tuple[int, float, int, str]:
    prompt = (
        "請從使用者句子中抽出餐廳篩選條件，只輸出 JSON：\n"
        "{\"max_travel_time\": 15, \"min_rating\": 4.2, "
        "\"min_reviews\": 1000, \"travel_mode\": \"driving\"}\n"
        "欄位說明：\n"
        "- max_travel_time: 分鐘（整數）\n"
        "- min_rating: 星等（浮點數）\n"
        "- min_reviews: 評論數量（整數）\n"
        "- travel_mode: walking / driving / bicycling / transit\n"
        "若未提到某條件，該欄位請省略或設為 null。\n"
        f"使用者：{user_text}"
    )
    try:
        raw = (await llm_generate(prompt)).strip()
    except Exception:
        return extract_food_filters(
            user_text,
            default_max_travel_time,
            default_min_rating,
            default_min_reviews,
            default_travel_mode,
        )

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        try:
            start = raw.find("{")
            end = raw.rfind("}")
            if start != -1 and end != -1 and end > start:
                data = json.loads(raw[start:end + 1])
            else:
                raise ValueError("no json")
        except Exception:
            return extract_food_filters(
                user_text,
                default_max_travel_time,
                default_min_rating,
                default_min_reviews,
                default_travel_mode,
            )

    max_travel_time = default_max_travel_time
    min_rating = default_min_rating
    min_reviews = default_min_reviews
    travel_mode = default_travel_mode

    if isinstance(data, dict):
        if data.get("max_travel_time") is not None:
            try:
                max_travel_time = int(data["max_travel_time"])
            except (TypeError, ValueError):
                pass
        if data.get("min_rating") is not None:
            try:
                min_rating = float(data["min_rating"])
            except (TypeError, ValueError):
                pass
        if data.get("min_reviews") is not None:
            try:
                min_reviews = int(data["min_reviews"])
            except (TypeError, ValueError):
                pass
        if data.get("travel_mode") is not None:
            mode = str(data["travel_mode"]).strip().lower()
            if mode in {"walking", "driving", "bicycling", "transit"}:
                travel_mode = mode

    return max_travel_time, min_rating, min_reviews, travel_mode


def _fallback_extract_dish(text: str) -> str:
    matches = list(re.finditer(r"([\u4e00-\u9fffA-Za-z0-9]+?)(店|餐廳)", text))
    if not matches:
        return ""
    last = matches[-1]
    return (last.group(1) or "").strip()

def _strip_location_suffix(text: str) -> str:
    suffixes = ("附近", "周邊", "周圍", "附近的", "週邊", "週圍")
    for s in suffixes:
        if text.endswith(s):
            return text[: -len(s)].strip()
    return text

def _fallback_extract_location(text: str) -> str:
    keywords = [
        "火車站", "車站", "捷運站", "公車站", "機場", "港", "碼頭",
        "大學", "學校", "中學", "國小", "醫院", "診所", "公司", "工廠",
        "科技園區", "工業區", "園區", "商圈", "市場", "夜市", "公園",
        "百貨", "購物中心", "體育場", "圖書館", "寺", "廟", "教會",
        "美術館", "博物館", "展覽館", "車行", "汽車", "門市",
    ]
    for kw in keywords:
        if kw in text:
            start = text.find(kw)
            if start == -1:
                continue
            left = text[: start]
            for sep in (" ", "，", "。", ",", ".", "、", "：", ":", "！", "?", "？"):
                if sep in left:
                    left = left.split(sep)[-1]
            candidate = (left + kw).strip()
            return _strip_location_suffix(candidate)
    return ""


def _style_hint(guild_id: Optional[int]) -> str:
    if guild_id is None:
        return ""
    style = get_guild_style(guild_id)
    if not style:
        return ""
    return f"回覆風格：{style}\n"


async def _apply_style(text: str, guild_id: Optional[int]) -> str:
    if guild_id is None:
        return text
    style = get_guild_style(guild_id)
    if not style or not config.LLM_API_KEY:
        return text
    prompt = (
        "請用以下風格改寫內容，保留原本資訊與數值，不要刪減重要細節。\n"
        f"風格：{style}\n"
        "內容：\n"
        f"{text}"
    )
    try:
        return (await llm_generate(prompt)).strip() or text
    except Exception:
        return text


async def run_food_agent(user_text: str, guild_id: Optional[int] = None) -> tuple[str, str]:
    dish, location_label = await llm_extract_food_query(user_text)
    if not dish:
        dish = _fallback_extract_dish(user_text)
    if not location_label:
        location_label = _fallback_extract_location(user_text)
    if not location_label:
        city_en, location_label = detect_food_location(user_text)
    else:
        city_en = extract_city(location_label)
    debug_prefix = f"（解析：地點：{location_label or '未提供'}；餐點：{dish or '未提供'}）"
    meal_by_text = detect_meal_from_text(user_text)
    now = datetime.now(ZoneInfo("Asia/Taipei"))
    meal_guess = meal_by_text or infer_meal_by_time(now)
    meal_src = "使用者描述" if meal_by_text else "當前時間推測"
    local_time = now.strftime("%H:%M")
    max_travel_time, min_rating, min_reviews, travel_mode = await llm_extract_food_filters(user_text)
    travel_mode_label = {
        "walking": "步行",
        "driving": "車程",
        "bicycling": "騎車",
    }.get(travel_mode, "移動")

    weather = None
    if location_label:
        weather = await get_weather_by_location(location_label)
    if not weather:
        weather = await get_current_weather(city_en)
    keyword = dish or user_text
    search_kw = keyword if meal_by_text else f"{meal_guess} {keyword}"
    food_text = await find_food(
        keyword=search_kw,
        location=location_label,
        max_travel_time=max_travel_time,
        min_rating=min_rating,
        min_reviews=min_reviews,
        travel_mode=travel_mode,
    )
    if ("找不到符合條件" in food_text) or ("找不到" in food_text and "餐廳" in food_text):
        tips = [
            "把評論數門檻降低（例如 2000+ 改 500+ / 1000+）。",
            "放寬移動時間或評分門檻（例如 20 分鐘改 30 分鐘）。",
            "改用更一般的關鍵字或指定區域（例如「早午餐、拉麵、小吃、台南東區」）。",
        ]
        tip_text = "\n".join([f"- {t}" for t in tips])
        message = (
            f"{food_text}\n"
            "建議你可以這樣調整搜尋方向：\n"
            f"{tip_text}"
        )
        return debug_prefix + "\n" + message, message

    prompt = "".join([
        "你是成大附近的美食推薦助理，回覆要有人情味、口吻自然、資訊完整。\n",
        _style_hint(guild_id),
        f"使用者需求：{user_text}\n",
        f"搜尋地點：{location_label}\n",
        f"條件：{max_travel_time} 分鐘內、評分 {min_rating}+、評論數 {min_reviews}+、交通方式 {travel_mode_label}\n",
        f"餐別：{meal_guess}（來源：{meal_src}）\n",
        f"現在時間（台灣）：{local_time}\n",
        f"天氣資料：{json.dumps(weather, ensure_ascii=False)}\n",
        "搜尋結果（包含距離/評分/評論數/價位/必點/評論摘要）：\n",
        f"{food_text}\n\n",
        "請用繁中給 3~5 家推薦，內容要更豐富、有情感，但避免冗長。\n",
        f"每家請包含：店名（可加簡短亮點標語）、評分與評論數、{travel_mode_label}時間、地圖連結、營業時間、推薦菜品（至少 2 道），以及一段「推薦理由」（1~2 句）。\n",
        "可以補充 1 句貼心提示（例如適合的場合或天氣）。\n",
        "推薦菜品必須是名詞短語，且只能從搜尋結果的「必點/推薦菜品清單」挑選；若清單為空，請寫「暫無明確推薦」。\n",
        "避免產生像句子的菜名或奇怪語法。\n",
        "格式示例：\n",
        "[1️⃣] 店名（亮點）\n",
        "   評分：x.x（xxxx 則評論）\n",
        f"   {travel_mode_label}：xx 分鐘\n",
        "   地圖：Google Maps 連結\n",
        "   營業時間：xx\n",
        "   推薦菜品：\n",
        "   • 菜名1 — 亮點描述\n",
        "   • 菜名2 — 亮點描述\n",
        "   推薦理由：一句到兩句\n",
        "   小提醒：一句話\n",
        "必須把「推薦菜品」寫成具體菜名，避免只寫“推薦招牌”；每家都要附 Google Maps 連結。",
    ])

    try:
        answer = await llm_generate(prompt)
        return debug_prefix + "\n" + answer, answer
    except Exception as e:
        err = f"{debug_prefix}\n抱歉，呼叫 LLM 失敗：{e}"
        return err, err


async def run_weather_agent(user_text: str, guild_id: Optional[int] = None) -> str:
    city = extract_city(user_text)
    try:
        weather = await get_current_weather(city)
    except Exception as e:
        return f"抱歉，查天氣失敗：{e}"

    prompt = "".join([
        "你是一個簡潔的天氣小幫手，使用繁體中文回答。",
        _style_hint(guild_id),
        f"\n城市：{city}",
        f"\n天氣資料：{json.dumps(weather, ensure_ascii=False)}",
        "\n請告訴使用者目前溫度、風速，並給穿著或出門建議。",
    ])
    try:
        answer = await llm_generate(prompt)
        return answer
    except Exception as e:
        return f"抱歉，呼叫 LLM 失敗：{e}"


async def run_chat_agent(user_text: str, guild_id: Optional[int] = None) -> str:
    prompt = "".join([
        "你是一個友善的聊天夥伴，使用繁體中文，簡潔自然地回覆。",
        "如果使用者主動問吃什麼，才進入美食推薦；否則就是閒聊。",
        _style_hint(guild_id),
        f"\n使用者：{user_text}\n",
        "請直接回覆，不要多餘的系統訊息。",
    ])
    try:
        answer = await llm_generate(prompt)
        return await _apply_style(answer, guild_id)
    except Exception as e:
        return f"抱歉，呼叫 LLM 失敗：{e}"


async def run_nutrition_agent(user_text: str, guild_id: Optional[int] = None) -> str:
    target = extract_nutrition_target(user_text)
    converted = await llm_translate_list([target])
    target = converted[0] if converted else target
    result = await usda_food_nutrition(target)
    return result
