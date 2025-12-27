import asyncio
import json
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
    ) -> str:
    return await asyncio.to_thread(
        food.find_food,
        keyword,
        location,
        max_travel_time,
        min_rating,
        min_reviews,
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


async def run_food_agent(user_text: str, guild_id: Optional[int] = None) -> str:
    dish, location_label = await llm_extract_food_query(user_text)
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

    weather = None
    if location_label:
        weather = await get_weather_by_location(location_label)
    if not weather:
        weather = await get_current_weather(city_en)
    keyword = dish or user_text
    search_kw = keyword if meal_by_text else f"{meal_guess} {keyword}"
    food_text = await find_food(keyword=search_kw, location=location_label)

    prompt = "".join([
        "你是成大附近的美食推薦助理。\n",
        _style_hint(guild_id),
        f"使用者需求：{user_text}\n",
        f"搜尋地點：{location_label}\n",
        f"餐別：{meal_guess}（來源：{meal_src}）\n",
        f"現在時間（台灣）：{local_time}\n",
        f"天氣資料：{json.dumps(weather, ensure_ascii=False)}\n",
        "搜尋結果（包含距離/評分/評論數/價位/必點/評論摘要）：\n",
        f"{food_text}\n\n",
        "請用繁中給 3~5 家推薦，格式示例：\n",
        "1. 店名\n",
        "   距離/時間：xx\n",
        "   價位：xx\n",
        "   評分：xx\n",
        "   必點：菜名1；菜名2；菜名3（若沒有必點請寫：暫無明確推薦）\n",
        "   地圖：直接貼上 Google Maps 連結（必填，不可省略）\n",
        "   推薦理由：一句話\n",
        "   營業：營業時間或未提供\n",
        "必須把「必點」欄位列出具體菜名，避免只寫“推薦招牌”；每家都要附 Google Maps 連結。",
    ])

    try:
        answer = await llm_generate(prompt)
        answer = await _apply_style(answer, guild_id)
        return debug_prefix + "\n" + answer
    except Exception as e:
        return f"{debug_prefix}\n抱歉，呼叫 LLM 失敗：{e}"


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
        return await _apply_style(answer, guild_id)
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
    return await _apply_style(result, guild_id)
