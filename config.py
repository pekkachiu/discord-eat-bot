import os
from dotenv import load_dotenv

# Ensure env vars are loaded before other modules import them.
load_dotenv(dotenv_path=".env")

DISCORD_TOKEN = os.environ["DISCORD_BOT_TOKEN"]

LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://api-gateway.netdb.csie.ncku.edu.tw")
LLM_API_KEY = os.environ.get("LLM_API_KEY", os.environ.get("OPENAI_API_KEY", ""))
USDA_API_KEY = os.environ.get("USDA_API_KEY", "")

WISHLIST_PATH = "wishlist.json"

DEFAULT_SPIN_CANDIDATES = [
    "炒飯", "拉麵", "蔥抓餅/蛋餅", "麻油雞麵線", "鍋貼/水餃", "火鍋", "蒙古烤肉", "牛肉麵",
    "燴飯", "小籠包/蒸餃", "泡麵", "烤肉飯", "炒河粉", "綠咖哩雞飯", "石鍋拌飯", "蛋包飯",
    "陽春麵", "雞排", "大阪燒", "麥當勞", "焗烤麵/焗烤飯", "雞腿便當", "涼麵", "叉燒飯",
    "排骨酥麵", "咖喱飯", "丼飯", "水煎包", "熱炒店", "義大利麵", "排骨便當", "鰻魚飯",
    "墨西哥捲餅", "滷肉飯", "大腸包小腸", "沙威瑪", "炒麵麵包", "西班牙燉飯", "控肉飯", "牛排",
    "自助餐", "鐵板燒", "燒肉吃到飽", "辣炒年糕", "鹽酥雞", "海南雞飯", "肯德基", "蚵仔麵線",
    "鴨肉飯", "豆腐煲", "皮蛋瘦肉粥", "飯卷", "麻婆豆腐拌飯", "米苔目", "漢堡王", "健康餐盒",
    "刈包", "米漢堡", "麻辣燙", "總匯三明治", "炒烏龍麵", "臭豆腐", "披薩", "米粉湯",
    "海鮮烏龍麵", "擔仔麵", "IKEA肉丸", "迴轉壽司", "鱔魚意麵", "虱目魚肚粥", "魚丸麵", "牛肉捲餅",
    "甜不辣", "關東煮", "豬血糕", "肉圓", "滷味", "碗粿", "餛飩麵", "韓式炸雞", "印度烤餅",
    "章魚燒", "豬肝炒麵", "港式飲茶", "日本料理店", "炸蝦飯", "雞肉飯", "炒米粉", "蝦仁羹麵",
    "粿仔條", "炭烤串", "肉包", "豬肉餡餅", "御飯糰", "鮭魚飯", "吃到飽餐廳", "北平烤鴨",
    "螺獅粉", "健康沙拉餐", "鬆餅",
]
