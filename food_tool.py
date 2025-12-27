import os
import requests
from typing import List, Dict
import re


class Tools:
    """
    Food recommendation tool using Google Maps APIs:
    - Geocoding API
    - Places Text Search API
    - Distance Matrix API
    - Place Details API
    """

    GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")

    GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
    PLACES_TEXT_SEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    DISTANCE_MATRIX_URL = "https://maps.googleapis.com/maps/api/distancematrix/json"
    PLACE_DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"

    def __init__(self):
        if not self.GOOGLE_API_KEY:
            raise RuntimeError("GOOGLE_API_KEY not set in environment variables")

    # ------------------------------------------------------------
    # 基礎工具
    # ------------------------------------------------------------
    def _geocode(self, location: str) -> str:
        """把地點轉成 lat,lng 字串"""
        params = {
            "address": location,
            "key": self.GOOGLE_API_KEY,
            "language": "zh-TW",
        }
        r = requests.get(self.GEOCODE_URL, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()

        if not data.get("results"):
            raise ValueError(f"Geocode failed for location: {location}")

        loc = data["results"][0]["geometry"]["location"]
        return f"{loc['lat']},{loc['lng']}"

    def _distance_minutes(self, origin: str, destination: str, mode: str = "walking") -> int:
        """回傳行程時間（分鐘）"""
        params = {
            "origins": origin,
            "destinations": destination,
            "mode": mode,
            "key": self.GOOGLE_API_KEY,
            "language": "zh-TW",
        }
        r = requests.get(self.DISTANCE_MATRIX_URL, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()

        element = data["rows"][0]["elements"][0]
        if element["status"] != "OK":
            return 999

        return int(element["duration"]["value"] / 60)

    def _place_details(self, place_id: str) -> Dict:
        params = {
            "place_id": place_id,
            "fields": (
                "name,rating,user_ratings_total,price_level,formatted_address,"
                "reviews,opening_hours,opening_hours.weekday_text,url"
            ),
            "key": self.GOOGLE_API_KEY,
            "language": "zh-TW",
            "review_sort": "newest",
        }
        r = requests.get(self.PLACE_DETAILS_URL, params=params, timeout=10)
        r.raise_for_status()
        return r.json().get("result", {})

    def _extract_recommended_items(self, reviews: List[Dict]) -> List[str]:
        """
        從評論中抓出推薦/必點的菜名（簡單 regex，最多 5 個）
        """
        # e.g. 推薦牛肉麵 / 牛肉麵必點 / 魯肉飯好吃
        patterns = [
            re.compile(r"(推薦|必點|招牌|必吃|超推)\s*([^\s，。.!！?？]{1,10})"),
            re.compile(r"([^\s，。.!！?？]{1,10})(好吃|好喝|很推|值得)"),
        ]
        generic_words = {"好吃", "好喝", "很推", "值得", "推薦", "必點", "招牌", "必吃", "超推"}
        items: List[str] = []
        for rev in reviews or []:
            text = rev.get("text", "") or ""
            for p in patterns:
                for m in p.finditer(text):
                    # pattern1: 取推薦後的菜名；pattern2: 取菜名本身（前段）
                    dish = (m.group(2) if m.re is patterns[0] else m.group(1)) or ""
                    dish = dish.strip("：:，。.!！?？ 、「」[]()（）")
                    if not dish or dish in generic_words:
                        continue
                    if dish not in items:
                        items.append(dish)
            if len(items) >= 5:
                break
        return items[:5]

    def _top_review_snippet(self, reviews: List[Dict]) -> str:
        for rev in reviews or []:
            text = rev.get("text", "") or ""
            if text:
                return (text[:80] + "…") if len(text) > 80 else text
        return ""

    # ------------------------------------------------------------
    # 主要對外工具
    # ------------------------------------------------------------
    def find_food(
        self,
        keyword: str,
        location: str = "國立成功大學",
        max_travel_time: int = 20,
        min_rating: float = 3.5,
        min_reviews: int = 0,
        travel_mode: str = "walking",
    ) -> str:
        """
        搜尋餐廳並回傳給 LLM 使用的推薦資料（文字格式）
        """
        if travel_mode not in {"walking", "driving", "bicycling", "transit"}:
            travel_mode = "walking"

        origin = self._geocode(location)

        params = {
            "query": f"{keyword} 餐廳",
            "location": origin,
            "radius": 2000,
            "key": self.GOOGLE_API_KEY,
            "language": "zh-TW",
        }
        r = requests.get(self.PLACES_TEXT_SEARCH_URL, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()

        results: List[Dict] = []

        for item in data.get("results", []):
            place_id = item.get("place_id")
            details = self._place_details(place_id)

            rating = details.get("rating", 0)
            reviews = details.get("user_ratings_total", 0)
            raw_reviews = details.get("reviews", []) or []
            rec_items = self._extract_recommended_items(raw_reviews)
            review_snippet = self._top_review_snippet(raw_reviews)

            if rating < min_rating or reviews < min_reviews:
                continue

            dest = f"{item['geometry']['location']['lat']},{item['geometry']['location']['lng']}"
            travel_time = self._distance_minutes(origin, dest, travel_mode)

            if travel_time > max_travel_time:
                continue

            results.append({
                "name": details.get("name"),
                "rating": rating,
                "reviews": reviews,
                "price_level": details.get("price_level"),
                "address": details.get("formatted_address"),
                "travel_time_min": travel_time,
                "recommended_items": rec_items,
                "review_snippet": review_snippet,
                "opening_hours": (details.get("opening_hours") or {}).get("weekday_text", []),
                "map_url": details.get("url") or f"https://www.google.com/maps/place/?q=place_id:{place_id}",
            })

            if len(results) >= 5:
                break

        # --------------------------------------------------------
        # 回傳給 LLM 的文字（你原本 tool 的用途）
        # --------------------------------------------------------
        if not results:
            return (
                f"在 {location} 附近找不到符合條件的「{keyword}」餐廳。\n"
                "請放寬條件或更換關鍵字。"
            )

        output = [
            f"以下是 {location} 附近推薦的「{keyword}」餐廳：",
            "",
        ]

        mode_label = {
            "walking": "步行",
            "driving": "車程",
            "bicycling": "騎車",
            "transit": "大眾運輸",
        }.get(travel_mode, "移動")

        for i, r in enumerate(results, 1):
            hours = r["opening_hours"]
            hours_text = hours[0] if hours else "營業時間未提供"
            rec_text = ', '.join(r['recommended_items']) if r['recommended_items'] else '暫無明確推薦'
            output.append(
                f"{i}. {r['name']}\n"
                f"   ⏱️ 約 {r['travel_time_min']} 分鐘{mode_label}\n"
                f"   ⭐ 評分 {r['rating']}（{r['reviews']} 則評論）\n"
                f"   💰 價位等級：{r['price_level'] if r['price_level'] is not None else '未知'}\n"
                f"   ⏰ 營業：{hours_text}\n"
                f"   🍽️ 必點：{rec_text}\n"
                f"   💬 精選評論：{r['review_snippet'] or '（評論過少，暫無精選）'}\n"
                f"   📍 地址：{r['address']}\n"
                f"   🗺️ 地圖：{r['map_url']}\n"
            )

        output.append(
            "請根據天氣、距離與價位，選出 3–5 家最適合的並給出簡短推薦理由。"
        )

        return "\n".join(output)
