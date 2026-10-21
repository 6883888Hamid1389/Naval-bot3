import os
import json
import logging
import asyncpg
import httpx
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_ID = 8849773822
DATABASE_URL = os.environ.get("DATABASE_URL", "")
CHANNEL_ID = os.environ.get("CHANNEL_ID", "") # آیدی کانال عمومی
CLOUDFLARE_API_TOKEN = os.environ.get("CLOUDFLARE_API_TOKEN", "")
CLOUDFLARE_ACCOUNT_ID = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")

# --- ساختار عمیق حکومت‌ها ---
GOVERNMENTS = {
    "communist": {
        "name": "☭ کمونیستی",
        "subs": {
            "marxist": "مارکسیسم-لنینیسم", "stalinist": "استالینیسم", 
            "maoist": "مائوئیسم", "trotskyist": "تروتسکیسم",
            "titoist": "تیتوئیسم", "castrist": "کاستروئیسم", "council": "کمونیسم شورایی"
        }
    },
    "dictator": {
        "name": "✊ دیکتاتوری",
        "subs": {
            "military": "دیکتاتوری نظامی", "personal": "دیکتاتوری فردی",
            "party": "دیکتاتوری حزبی", "oligarchy": "الیگارشی", "technocracy": "تکنوکراسی"
        }
    },
    "democracy": {
        "name": "🗳️ دموکراسی",
        "subs": {
            "parliamentary": "پارلمانی", "presidential": "ریاستی",
            "semi_presidential": "نیمه‌ریاستی", "federal": "فدرال",
            "direct": "مستقیم", "social_democracy": "سوسیال دموکراسی"
        }
    },
    "monarchy": {
        "name": "👑 سلطنتی",
        "subs": {
            "absolute": "مطلقه", "constitutional": "مشروطه",
            "federal": "فدرال", "elective": "انتخابی", "empire": "امپراتوری"
        }
    },
    "republic": {
        "name": "🏛️ جمهوری",
        "subs": {
            "secular": "سکولار", "islamic": "اسلامی", "theocratic": "تئوکراتیک",
            "socialist": "سوسیالیستی", "federal_rep": "فدرال", "liberal": "لیبرال"
        }
    },
    "religious": {
        "name": "🕌 دینی",
        "subs": {
            "shia_theo": "تئوکراسی شیعه", "suni_theo": "تئوکراتیک سنی",
            "caliphate": "خلافتی", "velayat": "ولایت فقیه",
            "confucian": "کنفوسیوسی", "buddhist": "بودایی"
        }
    }
}

pool = None

async def init_db():
    global pool
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
    async with pool.acquire() as conn:
        # جدول کشورها
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS countries (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                name TEXT,
                leader TEXT,
                gov_main TEXT,
                gov_sub TEXT,
                status TEXT DEFAULT 'pending',
                treasury BIGINT DEFAULT 100000,
                gdp BIGINT DEFAULT 500000,
                army INT DEFAULT 10000,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        # جدول دستورات (قلب سیستم)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                order_text TEXT,
                category TEXT, -- economic, political, military
                status TEXT DEFAULT 'pending', 
                admin_note TEXT,
                ai_analysis_raw TEXT,
                final_text TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                published_at TIMESTAMP DEFAULT NULL
            )
        """)
    logger.info("Database initialized.")

# --- توابع کمکی ---
async def get_country(uid):
    async with pool.acquire() as conn:
        r = await conn.fetchrow("SELECT * FROM countries WHERE user_id = $1", uid)
        return dict(r) if r else None

async def get_order(order_id):
    async with pool.acquire() as conn:
        r = await conn.fetchrow("SELECT * FROM orders WHERE id = $1", order_id)
        return dict(r) if r else None

def kb(rows):
    return InlineKeyboardMarkup(rows)

def fmt_money(amount):
    return f"{amount:,.0f} دلار" if amount < 1000000 else f"{amount/1000000:.1f} میلیون دلار"

# --- ارتباط با هوش مصنوعی (Cloudflare) ---
async def ask_ai(prompt: str, system_prompt: str = "You are a game master AI for a geopolitical strategy game.") -> str:
    url = f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/ai/run/@cf/meta/llama-3-8b-instruct"
    headers = {"Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}"}
    payload = {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]
    }
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload, timeout=40)
            res_data = response.json()
            if res_data.get("success"):
                return res_data["result"]["response"]
            return "⚠️ خطا در تحلیل AI."
    except Exception as e:
        logger.error(f"AI Error: {e}")
        return "⚠️ ارتباط با مرکز فرماندهی قطع شد."

# --- تحلیل دستور توسط AI و ثبت در دیتابیس ---
async def analyze_and_apply_order(order_id: int):
    order = await get_order(order_id)
    country = await get_country(order["user_id"])
    
    # پرامپت برای تحلیل (اجبار به خروجی JSON)
    prompt = f"""
    Country: {country['name']}
    Current Treasury: {country['treasury']}
    Current Army: {country['army']}
    Current GDP: {country['gdp']}
    
    Player's Order: "{order['order_text']}"
    Category: {order['category']}
    
    Analyze this order and respond ONLY with a JSON object in Persian (Farsi) format:
    {{
        "success": true/false,
        "reason": "دلیل موفقیت یا شکست",
        "treasury_change": integer (negative for cost, positive for gain),
        "army_change": integer,
        "gdp_change": integer,
        "narrative": "یک توضیح کوتاه و هیجان‌انگیز به زبان فارسی درباره اتفاقی که افتاد."
    }}
    """
    
    ai_response = await ask_ai(prompt)
    
    # استخراج JSON از پاسخ
    try:
        import re
        json_match = re.search(r'\{.*\}', ai_response, re.DOTALL)
        data = json.loads(json_match.group(0)) if json_match else {}
    except:
        data = {"success": False, "reason": "خطای پردازش", "narrative": "فرماندهی نتوانست دستور را اجرا کند."}

    # آپدیت دیتابیس
    async with pool.acquire() as conn:
        if data.get("success"):
            new_treasury = max(0, country['treasury'] + data.get("treasury_change", 0))
            new_army = max(0, country['army'] + data.get("army_change", 0))
            new_gdp = max(1000, country['gdp'] + data.get("gdp_change", 0))
            
            await conn.execute("UPDATE countries SET treasury=$1, army=$2, gdp=$3 WHERE user_id=$4", 
                               new_treasury, new_army, new_gdp, order["user_id"])
            
        await conn.execute("UPDATE orders SET status='ai_analyzed', ai_analysis_raw=$1 WHERE id=$2", 
                           json.dumps(data, ensure_ascii=False), order_id)
    
    return data
