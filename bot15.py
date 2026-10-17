import os
import time
import logging
import asyncpg
from collections import defaultdict
from datetime import time as dt_time, timezone as dt_timezone

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_ID = 8849773822
DATABASE_URL = os.environ.get("DATABASE_URL", "")

if not TOKEN or not DATABASE_URL:
    raise SystemExit("TOKEN or DB NOT SET!")

REGIONS_19 = ["III", "GGG", "YYY", "OOO", "TTT", "FFF", "SSS", "AAA", "HHH", "KKK",
              "LLL", "RRR", "DDD", "WWW", "QQQ", "UUU", "PPP", "EEE", "MMM"]

RESOURCES = {
    "water": "💧 آب", "wheat": "🌾 گندم", "iron_ore": "⛏ سنگ آهن", "bauxite": "🪨 بوکسیت",
    "copper_ore": "🟤 سنگ مس", "titanium_ore": "⚙️ سنگ تیتانیوم", "gold": "🏵 طلا",
    "uranium": "☢ اورانیوم", "rare_earth": "💎 خاک کمیاب", "crude_oil": "🛢 نفت خام",
    "steel": "🏗 فولاد", "aluminum": "🔩 آلومینیوم", "copper": "🔌 مس",
    "titanium": "🛡 تیتانیوم", "power": "⚡️ برق", "chemicals": "🧪 مواد شیمیایی",
    "explosives_base": "💥 مواد منفجره پایه", "car_parts": "⚙️ قطعات خودرو",
    "aero_parts": "🚀 قطعات هوافضا", "electronics": "📟 الکترونیک", "tnt": "🧨 TNT",
}

START_RES = {
    "power": 1000, "crude_oil": 1000, "steel": 1000, "iron_ore": 1000, "water": 2000, "wheat": 2000,
}

BUILDINGS = {
    "iron_mine": {"name": "⛏ معدن آهن", "type": "mining", "cost": 10000, "workers": 50, "input": {"power": 10}, "output": {"iron_ore": 10}},
    "bauxite_mine": {"name": "🪨 معدن بوکسیت", "type": "mining", "cost": 12000, "workers": 50, "input": {"power": 10}, "output": {"bauxite": 10}},
    "copper_mine": {"name": "🟤 معدن مس", "type": "mining", "cost": 11000, "workers": 50, "input": {"power": 10}, "output": {"copper_ore": 10}},
    "titanium_mine": {"name": "⚙️ معدن تیتانیوم", "type": "mining", "cost": 15000, "workers": 60, "input": {"power": 15}, "output": {"titanium_ore": 10}},
    "gold_mine": {"name": "🏵 معدن طلا", "type": "mining", "cost": 20000, "workers": 50, "input": {"power": 20}, "output": {"gold": 5}},
    "uranium_mine": {"name": "☢ معدن اورانیوم", "type": "mining", "cost": 25000, "workers": 60, "input": {"power": 25}, "output": {"uranium": 5}},
    "rare_earth_mine": {"name": "💎 معدن خاک کمیاب", "type": "mining", "cost": 30000, "workers": 60, "input": {"power": 30}, "output": {"rare_earth": 5}},
    "oil_well": {"name": "🛢 چاه نفت", "type": "extractive", "cost": 8000, "workers": 30, "input": {"power": 5}, "output": {"crude_oil": 20}},
    "power_plant": {"name": "⚡️ نیروگاه برق", "type": "industrial", "cost": 15000, "workers": 80, "input": {"crude_oil": 5, "steel": 2}, "output": {"power": 100}},
    "steel_mill": {"name": "🏗 کارخانه فولاد", "type": "industrial", "cost": 20000, "workers": 100, "input": {"iron_ore": 10, "power": 20}, "output": {"steel": 10}},
    "aluminum_smelter": {"name": "🔩 کارخانه آلومینیوم", "type": "industrial", "cost": 22000, "workers": 100, "input": {"bauxite": 10, "power": 30}, "output": {"aluminum": 10}},
    "copper_refinery": {"name": "🔌 پالایشگاه مس", "type": "industrial", "cost": 18000, "workers": 90, "input": {"copper_ore": 10, "power": 20}, "output": {"copper": 10}},
    "titanium_refinery": {"name": "🛡 پالایشگاه تیتانیوم", "type": "industrial", "cost": 25000, "workers": 120, "input": {"titanium_ore": 10, "power": 30}, "output": {"titanium": 10}},
    "oil_refinery": {"name": "🛢 پالایشگاه نفت", "type": "industrial", "cost": 30000, "workers": 150, "input": {"crude_oil": 20, "power": 30}, "output": {"chemicals": 10, "explosives_base": 5}},
    "chemical_plant": {"name": "🧪 کارخانه شیمیایی", "type": "industrial", "cost": 25000, "workers": 120, "input": {"chemicals": 10, "power": 20}, "output": {"explosives_base": 10}},
    "car_parts_factory": {"name": "⚙️ قطعات خودرو", "type": "industrial", "cost": 35000, "workers": 200, "input": {"steel": 5, "aluminum": 5, "copper": 2}, "output": {"car_parts": 5}},
    "aero_parts_factory": {"name": "🚀 قطعات هوافضا", "type": "industrial", "cost": 45000, "workers": 250, "input": {"titanium": 5, "aluminum": 5, "copper": 2}, "output": {"aero_parts": 5}},
    "electronics_factory": {"name": "📟 قطعات الکترونیک", "type": "industrial", "cost": 40000, "workers": 200, "input": {"copper": 5, "gold": 2, "rare_earth": 2}, "output": {"electronics": 5}},
    "tnt_factory": {"name": "🧨 خط تولید TNT", "type": "industrial", "cost": 50000, "workers": 300, "input": {"explosives_base": 5, "chemicals": 5, "electronics": 2}, "output": {"tnt": 2}},
    "house": {"name": "🏠 خانه", "type": "residential", "cost": 500, "workers": 10, "pop": 100000, "happiness": 1},
    "park": {"name": "🌳 پارک", "type": "residential", "cost": 1000, "workers": 50, "happiness": 2},
    "bazaar": {"name": "🏪 بازار", "type": "commercial", "cost": 2000, "workers": 100, "income": 3000},
    "bank": {"name": "🏦 بانک", "type": "commercial", "cost": 15000, "workers": 200, "income": 10000},
    "wheat_farm": {"name": "🌾 مزرعه گندم", "type": "agricultural", "cost": 1000, "workers": 100, "input": {"water": 10}, "output": {"wheat": 50}},
}

ZONE_TYPES = {
    "residential": "🏘️ مسکونی", "industrial": "🏭 صنعتی",
    "agricultural": "🌾 کشاورزی", "extractive": "⛽ استخراجی",
    "mining": "⛏️ معدنی", "commercial": "🏪 تجاری",
}

ZONE_SIZES = {
    "small": {"name": "کوچک", "capacity": 3, "cost": 5000},
    "medium": {"name": "متوسط", "capacity": 6, "cost": 10000},
    "large": {"name": "بزرگ", "capacity": 10, "cost": 20000},
}

GOVS = {"dictator": "✊ دیکتاتوری", "democracy": "🗳️ دموکراسی", "religious": "🕌 دینی", "monarch": "👑 سلطنتی", "communist": "☭ کمونیستی", "republic": "🏛️ جمهوری"}
GOV_SUBS = {
    "dictator": {"mil": ["🔒 دیکتاتوری نظامی", 35], "personal": ["👑 دیکتاتوری فردی", 25]},
    "democracy": {"parl": ["📜 پارلمانی", 85], "pres": ["🗳️ ریاستی", 80]},
    "religious": {"trad": ["🕌 سنتی", 70], "mod": ["⚖️ میانه‌رو", 80], "mil": ["🛡️ نظامی-دینی", 55], "legal": ["📜 قانون‌گرا", 75], "radical": ["💀 افراطی", 25]},
    "monarch": {"abs": ["👑 مطلقه", 45], "const": ["🏛️ مشروطه", 75]},
    "communist": {"one": ["☭ تک‌حزبی", 60]},
    "republic": {"sec": ["🏛️ سکولار", 80], "theo": ["⚖️ تئوکراتیک", 55]},
}
RELIGIONS = {"islam": "☪️ اسلام", "christ": "✝️ مسیحیت", "jew": "✡️ یهودیت", "hindu": "🕉️ هندوئیسم", "budd": "☸️ بودیسم", "secular": "🕊️ سکولار"}
REL_SUBS = {
    "islam": {"shia12": "🔵 شیعه ۱۲امامی", "shia_ism": "🟢 اسماعیلی", "shia_zayd": "🟡 زیدی", "suni_hanafi": "🟠 حنفی", "suni_shafei": "🔴 شافعی", "suni_maleki": "🟣 مالکی", "suni_hanbali": "⚫ حنبلی"},
    "christ": {"cath": "⛪ کاتولیک", "orth": "🏛️ ارتدوکس", "prot": "📖 پروتستان"},
    "jew": {"orth": "✡️ ارتدوکس", "cons": "🕎 محافظه‌کار", "ref": "📜 اصلاح‌طلب"},
    "budd": {"thera": "🟡 تراوادا", "maha": "🔴 ماهایانا", "vajra": "⚫ وجریانا"},
}
EXPERTS = {"heavy": "🏭 صنایع سنگین", "energy": "⛽ سوخت و انرژی", "grain": "🌾 کشاورزی", "military": "🔫 صنایع نظامی"}

GOV_GDP_COEF = {"دموکراسی پارلمانی": 1.3, "دموکراسی ریاستی": 1.2, "جمهوری سکولار": 1.2, "سلطنت مشروطه": 1.1, "جمهوری تئوکراتیک": 1.0, "سلطنت مطلقه": 0.9, "تئوکراسی میانه‌رو": 0.8, "تئوکراسی قانون‌گرا": 0.8, "کمونیسم تک‌حزبی": 0.8, "تئوکراسی نظامی-دینی": 0.8, "دیکتاتوری نظامی": 0.8, "دیکتاتوری فردی": 0.7, "تئوکراسی افراطی": 0.5}
RELIGION_COEF = {"سکولار": 1.1, "اسلام": 1.0, "مسیحیت": 0.95, "یهودیت": 1.0, "بودیسم": 0.9, "هندوئیسم": 0.8}
EXPERT_GDP_COEF = {"صنایع سنگین": 1.3, "سوخت و انرژی": 1.5, "غلات و کشاورزی": 1.0, "صنایع نظامی": 1.1}

temp = {}
spam_tracker = {}
banned_users = set()
pool = None

def kb(rows):
    return InlineKeyboardMarkup(rows)

def check_spam(uid):
    now = time.time()
    spam_tracker.setdefault(uid, [])
    spam_tracker[uid] = [t for t in spam_tracker[uid] if now - t < 10]
    spam_tracker[uid].append(now)
    if len(spam_tracker[uid]) > 5:
        banned_users.add(uid)
        return True
    return False

def fmt_money(amount):
    d = amount * 1000
    if d >= 1_000_000_000: return f"{d/1_000_000_000:.2f} میلیارد دلار"
    if d >= 1_000_000: return f"{d/1_000_000:.1f} میلیون دلار"
    if d >= 1_000: return f"{d/1_000:.0f} هزار دلار"
    return f"{d:.0f} دلار"

def fmt_date(year, month):
    mn = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور", "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]
    return f"{mn[month-1]} {year}"

async def init_db():
    global pool
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=3, command_timeout=60)
    async with pool.acquire() as conn:
        await conn.execute("CREATE TABLE IF NOT EXISTS countries (user_id BIGINT PRIMARY KEY, username TEXT, name TEXT, leader TEXT, age INT, reign TEXT, gov TEXT, gov_sub TEXT, religion TEXT, rel_sub TEXT, expert TEXT, flag_id TEXT, status TEXT, happiness INT, science TEXT, ban_reason TEXT)")
        await conn.execute("CREATE TABLE IF NOT EXISTS pending (user_id BIGINT PRIMARY KEY, username TEXT, name TEXT, leader TEXT, age INT, reign TEXT, gov TEXT, gov_sub TEXT, religion TEXT, rel_sub TEXT, expert TEXT, flag_id TEXT)")
        await conn.execute("CREATE TABLE IF NOT EXISTS spam_banned (user_id BIGINT PRIMARY KEY)")
        await conn.execute("CREATE TABLE IF NOT EXISTS game_state (id INT PRIMARY KEY DEFAULT 1, current_year INT DEFAULT 2075, current_month INT DEFAULT 1, total_turns INT DEFAULT 0, last_update TIMESTAMP DEFAULT NOW())")
        await conn.execute("CREATE TABLE IF NOT EXISTS country_stats (user_id BIGINT PRIMARY KEY, gdp BIGINT DEFAULT 500000, treasury BIGINT DEFAULT 150000, population BIGINT DEFAULT 15000000, tax_rate INT DEFAULT 0, infrastructure INT DEFAULT 25, happiness INT DEFAULT 60, science_base INT DEFAULT 10, science_applied INT DEFAULT 10, science_military INT DEFAULT 10, science_space INT DEFAULT 5, research_budget INT DEFAULT 0, military_budget INT DEFAULT 0, education_budget INT DEFAULT 0, infrastructure_budget INT DEFAULT 0, welfare_budget INT DEFAULT 0, army INT DEFAULT 0, unemployment INT DEFAULT 0)")
        await conn.execute("CREATE TABLE IF NOT EXISTS cities (id SERIAL PRIMARY KEY, user_id BIGINT, name TEXT)")
        await conn.execute("CREATE TABLE IF NOT EXISTS city_zones (id SERIAL PRIMARY KEY, user_id BIGINT, city_id INT, zone_type TEXT, name TEXT, size TEXT, capacity INT, used INT DEFAULT 0)")
        await conn.execute("CREATE TABLE IF NOT EXISTS zone_buildings (id SERIAL PRIMARY KEY, zone_id INT, building_key TEXT)")
        await conn.execute("CREATE TABLE IF NOT EXISTS country_resources (user_id BIGINT PRIMARY KEY, water BIGINT DEFAULT 0, wheat BIGINT DEFAULT 0, iron_ore BIGINT DEFAULT 0, bauxite BIGINT DEFAULT 0, copper_ore BIGINT DEFAULT 0, titanium_ore BIGINT DEFAULT 0, gold BIGINT DEFAULT 0, uranium BIGINT DEFAULT 0, rare_earth BIGINT DEFAULT 0, crude_oil BIGINT DEFAULT 0, steel BIGINT DEFAULT 0, aluminum BIGINT DEFAULT 0, copper BIGINT DEFAULT 0, titanium BIGINT DEFAULT 0, power BIGINT DEFAULT 0, chemicals BIGINT DEFAULT 0, explosives_base BIGINT DEFAULT 0, car_parts BIGINT DEFAULT 0, aero_parts BIGINT DEFAULT 0, electronics BIGINT DEFAULT 0, tnt BIGINT DEFAULT 0)")
        await conn.execute("CREATE TABLE IF NOT EXISTS resource_capacities (user_id BIGINT PRIMARY KEY, water BIGINT DEFAULT 1000000, wheat BIGINT DEFAULT 1000000, iron_ore BIGINT DEFAULT 500000, bauxite BIGINT DEFAULT 500000, copper_ore BIGINT DEFAULT 500000, titanium_ore BIGINT DEFAULT 500000, gold BIGINT DEFAULT 100000, uranium BIGINT DEFAULT 100000, rare_earth BIGINT DEFAULT 100000, crude_oil BIGINT DEFAULT 1000000, steel BIGINT DEFAULT 500000, aluminum BIGINT DEFAULT 500000, copper BIGINT DEFAULT 500000, titanium BIGINT DEFAULT 500000, power BIGINT DEFAULT 1000000, chemicals BIGINT DEFAULT 500000, explosives_base BIGINT DEFAULT 500000, car_parts BIGINT DEFAULT 100000, aero_parts BIGINT DEFAULT 100000, electronics BIGINT DEFAULT 100000, tnt BIGINT DEFAULT 50000)")
        
        await conn.execute("ALTER TABLE countries ADD COLUMN IF NOT EXISTS map_region TEXT")
        await conn.execute("ALTER TABLE pending ADD COLUMN IF NOT EXISTS map_region TEXT")
        
        r = await conn.fetchrow("SELECT * FROM game_state WHERE id = 1")
        if not r:
            await conn.execute("INSERT INTO game_state (id) VALUES (1)")
    async with pool.acquire() as conn:
        for r in await conn.fetch("SELECT user_id FROM spam_banned"):
            banned_users.add(r["user_id"])

async def get_country(uid):
    async with pool.acquire() as conn:
        r = await conn.fetchrow("SELECT * FROM countries WHERE user_id = $1", uid)
        return dict(r) if r else None

async def get_pending(uid):
    async with pool.acquire() as conn:
        r = await conn.fetchrow("SELECT * FROM pending WHERE user_id = $1", uid)
        return dict(r) if r else None

async def save_pending(uid, d):
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO pending (user_id, username, name, leader, age, reign, gov, gov_sub, religion, rel_sub, expert, map_region, flag_id)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)
               ON CONFLICT (user_id) DO UPDATE SET username=$2, name=$3, leader=$4, age=$5, reign=$6,
               gov=$7, gov_sub=$8, religion=$9, rel_sub=$10, expert=$11, map_region=$12, flag_id=$13""",
            uid, d.get("username"), d.get("name"), d.get("leader"), d.get("age"), d.get("reign"),
            d.get("gov"), d.get("gov_sub"), d.get("religion"), d.get("rel_sub"),
            d.get("expert"), d.get("map_region"), d.get("flag_id"),
        )

async def delete_pending(uid):
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM pending WHERE user_id = $1", uid)

async def save_country(uid, d):
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO countries (user_id, username, name, leader, age, reign, gov, gov_sub, religion, rel_sub, expert, map_region, flag_id, status, happiness, science, ban_reason)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,'approved',60,'10',NULL)
               ON CONFLICT (user_id) DO UPDATE SET username=$2, name=$3, leader=$4, age=$5, reign=$6,
               gov=$7, gov_sub=$8, religion=$9, rel_sub=$10, expert=$11, map_region=$12, flag_id=$13, status='approved'""",
            uid, d.get("username"), d.get("name"), d.get("leader"), d.get("age"), d.get("reign"),
            d.get("gov"), d.get("gov_sub"), d.get("religion"), d.get("rel_sub"),
            d.get("expert"), d.get("map_region"), d.get("flag_id"),
        )
    await init_stats(uid, d)

async def init_stats(uid, d):
    g = GOV_GDP_COEF.get(d.get("gov_sub", ""), 1.0)
    r = RELIGION_COEF.get(d.get("religion", ""), 1.0)
    e = EXPERT_GDP_COEF.get(d.get("expert", ""), 1.0)
    gdp = int(500000 * g * r * e)
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO country_stats (user_id, gdp, treasury, population, tax_rate, military_budget, research_budget, education_budget, infrastructure_budget, welfare_budget)
               VALUES ($1, $2, 150000, 15000000, 0, 0, 0, 0, 0, 0)
               ON CONFLICT (user_id) DO UPDATE SET gdp=$2, treasury=150000, population=15000000""",
            uid, gdp,
        )
        cols = ", ".join(START_RES.keys())
        vals = ", ".join(f"${i+2}" for i in range(len(START_RES)))
        await conn.execute(f"INSERT INTO country_resources (user_id, {cols}) VALUES ($1, {vals}) ON CONFLICT DO NOTHING", uid, *START_RES.values())
        await conn.execute("INSERT INTO resource_capacities (user_id) VALUES ($1) ON CONFLICT DO NOTHING", uid)

async def get_stats(uid):
    async with pool.acquire() as conn:
        s = await conn.fetchrow("SELECT * FROM country_stats WHERE user_id = $1", uid)
        return dict(s) if s else None

async def get_resources(uid):
    async with pool.acquire() as conn:
        r = await conn.fetchrow("SELECT * FROM country_resources WHERE user_id = $1", uid)
        return dict(r) if r else None

async def get_cities(uid):
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM cities WHERE user_id = $1 ORDER BY id", uid)
        return [dict(r) for r in rows]

async def get_city_zones(city_id):
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM city_zones WHERE city_id = $1 ORDER BY id", city_id)
        return [dict(r) for r in rows]

async def get_one_zone(rid, uid):
    async with pool.acquire() as conn:
        r = await conn.fetchrow("SELECT * FROM city_zones WHERE id = $1 AND user_id = $2", rid, uid)
        return dict(r) if r else None

async def set_status(uid, status, reason=None):
    async with pool.acquire() as conn:
        await conn.execute("UPDATE countries SET status=$1, ban_reason=$2 WHERE user_id=$3", status, reason, uid)

async def delete_country(uid):
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM zone_buildings WHERE zone_id IN (SELECT id FROM city_zones WHERE user_id=$1)", uid)
        await conn.execute("DELETE FROM city_zones WHERE user_id=$1", uid)
        await conn.execute("DELETE FROM cities WHERE user_id=$1", uid)
        await conn.execute("DELETE FROM country_resources WHERE user_id=$1", uid)
        await conn.execute("DELETE FROM resource_capacities WHERE user_id=$1", uid)
        await conn.execute("DELETE FROM country_stats WHERE user_id=$1", uid)
        await conn.execute("DELETE FROM pending WHERE user_id=$1", uid)
        await conn.execute("DELETE FROM countries WHERE user_id=$1", uid)

async def get_all_countries():
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM countries ORDER BY user_id DESC")
        return [dict(r) for r in rows]

async def get_banned():
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM countries WHERE status='banned' ORDER BY user_id DESC")
        return [dict(r) for r in rows]

async def get_pending_all():
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM pending")
        return [dict(r) for r in rows]

async def get_taken_map_regions():
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT map_region, user_id FROM countries WHERE map_region IS NOT NULL")
        return {r["map_region"]: r["user_id"] for r in rows}

async def add_spam_ban(uid):
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO spam_banned (user_id) VALUES ($1) ON CONFLICT DO NOTHING", uid)

async def remove_spam_ban(uid):
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM spam_banned WHERE user_id=$1", uid)

async def get_game_date():
    async with pool.acquire() as conn:
        r = await conn.fetchrow("SELECT current_year, current_month, total_turns FROM game_state WHERE id=1")
        return {"year": r["current_year"], "month": r["current_month"], "turns": r["total_turns"]}

async def set_commands(application):
    cmds = [
        BotCommand("start", "شروع / ثبت کشور"),
        BotCommand("country", "پروفایل کشور"),
        BotCommand("economy", "مدیریت بودجه و اقتصاد"),
        BotCommand("date", "تاریخ بازی"),
        BotCommand("cities", "مدیریت شهرها"),
        BotCommand("zones", "مدیریت نواحی شهری"),
        BotCommand("resources", "منابع و انبار"),
        BotCommand("admin", "پنل ادمین"),
        BotCommand("cancel", "لغو"),
    ]
    await application.bot.set_my_commands(cmds)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    chat_id = update.effective_chat.id
    if uid in banned_users and uid != ADMIN_ID:
        await context.bot.send_message(chat_id, "🚫 مسدود هستید.")
        return
    if check_spam(uid) and uid != ADMIN_ID:
        await context.bot.send_message(chat_id, "🚫 اسپم!")
        await add_spam_ban(uid)
        return
    c = await get_country(uid)
    if c:
        if c["status"] == "approved":
            cities = await get_cities(uid)
            if len(cities) < 10:
                await context.bot.send_message(chat_id, f"⚠️ باید ابتدا ۱۰ شهر خود را نام‌گذاری کنید. ({len(cities)}/۱۰)\nدستور: /cities")
            else:
                await context.bot.send_message(chat_id, "✅ کشور شما فعال است. از /economy برای تنظیم بودجه و /zones برای ساخت نواحی شهری استفاده کنید.")
        elif c["status"] == "banned":
            await context.bot.send_message(chat_id, "🚫 کشور شما مسدود شده است.")
        else:
            await context.bot.send_message(chat_id, "⏳ در انتظار تایید ادمین.")
        return
    temp[uid] = {"username": update.effective_user.username or update.effective_user.first_name, "step": "NAME"}
    await context.bot.send_message(chat_id, "🏛️ نام کشور خود را وارد کنید:")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    temp.pop(update.effective_user.id, None)
    await update.message.reply_text("❌ لغو شد.")

async def date_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    gd = await get_game_date()
    await context.bot.send_message(update.effective_chat.id, f"📅 تاریخ بازی: {fmt_date(gd['year'], gd['month'])}\n🔄 تعداد نوبت‌ها: {gd['turns']}")

async def country_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    c = await get_country(uid)
    if not c:
        return
    await context.bot.send_message(
        update.effective_chat.id,
        f"🏛️ کشور: {c['name']}\n"
        f"📍 منطقه جهانی: {c.get('map_region', '—')}\n"
        f"👤 رهبر: {c['leader']}\n"
        f"⚙️ حکومت: {c['gov_sub']}\n"
        f"☪️ دین: {c['religion']}\n"
        f"🏭 تخصص: {c['expert']}",
        parse_mode="Markdown",
    )

async def cities_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    c = await get_country(uid)
    if not c or c["status"] != "approved":
        return
    cities = await get_cities(uid)
    if len(cities) >= 10:
        txt = "🏙️ شهرهای شما:\n\n" + "\n".join(f"🔹 {city['name']}" for city in cities)
        await context.bot.send_message(update.effective_chat.id, txt)
        return
    temp[uid] = {"step": "CITY_NAME"}
    await context.bot.send_message(update.effective_chat.id, f"🏙️ نام شهر شماره {len(cities)+1} را وارد کنید:")

async def economy_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    c = await get_country(uid)
    if not c or c["status"] != "approved":
        return
    s = await get_stats(uid)
    if s["treasury"] == 150000 and s["military_budget"] == 0 and s["research_budget"] == 0:
        temp[uid] = {"step": "BUDGET_SET", "mil": 0, "sci": 0, "wel": 0, "inf": 0}
        await show_budget_panel(update.effective_chat.id, context, temp[uid])
        return
    capital = 100 - s["military_budget"] - s["research_budget"] - s["welfare_budget"] - s["infrastructure_budget"]
    text = (
        f"💰 *اقتصاد {c['name']}*\n\n"
        f"📈 GDP: {fmt_money(s['gdp'])}\n"
        f"🏦 خزانه: {fmt_money(s['treasury'])}\n\n"
        f"📊 تخصیص بودجه:\n"
        f"🪖 نظامی: {s['military_budget']}٪\n"
        f"🔬 علم: {s['research_budget']}٪\n"
        f"🏥 رفاه: {s['welfare_budget']}٪\n"
        f"🏗️ زیرساخت: {s['infrastructure_budget']}٪\n"
        f"🏦 سرمایه: {capital}٪"
    )
    await context.bot.send_message(update.effective_chat.id, text, parse_mode="Markdown")

async def show_budget_panel(chat_id, context, t):
    total = t["mil"] + t["sci"] + t["wel"] + t["inf"]
    cap = 100 - total
    text = (
        f"💰 *تنظیم بودجه اولیه (۱۵۰ میلیون دلار)*\n\n"
        f"مجموع تخصیص: {total}٪\n"
        f"💰 سرمایه باقیمانده: {cap}٪\n\n"
        f"🪖 نظامی: {t['mil']}٪\n"
        f"🔬 علم: {t['sci']}٪\n"
        f"🏥 رفاه: {t['wel']}٪\n"
        f"🏗️ زیرساخت: {t['inf']}٪"
    )
        rows = [
        [InlineKeyboardButton("🪖 +۵٪", callback_data="bud_mil_5"), InlineKeyboardButton("🪖 -۵٪", callback_data="bud_mil_-5")],
        [InlineKeyboardButton("🔬 +۵٪", callback_data="bud_sci_5"), InlineKeyboardButton("🔬 -۵٪", callback_data="bud_sci_-5")],
        [InlineKeyboardButton("🏥 +۵٪", callback_data="bud_wel_5"), InlineKeyboardButton("🏥 -۵٪", callback_data="bud_wel_-5")],
        [InlineKeyboardButton("🏗️ +۵٪", callback_data="bud_inf_5"), InlineKeyboardButton("🏗️ -۵٪", callback_data="bud_inf_-5")],
        [InlineKeyboardButton("✅ تایید نهایی", callback_data="bud_confirm")],
    ]
    await context.bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=kb(rows))

async def zones_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    cities = await get_cities(uid)
    if len(cities) < 10:
        await context.bot.send_message(update.effective_chat.id, "❌ ابتدا باید ۱۰ شهر بسازید. /cities")
        return
    rows = [[InlineKeyboardButton(f"🏙️ {city['name']}", callback_data=f"city_view_{city['id']}")] for city in cities]
    await context.bot.send_message(update.effective_chat.id, "🏙️ یک شهر برای مدیریت نواحی انتخاب کنید:", reply_markup=kb(rows))

async def resources_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    res = await get_resources(uid)
    if not res:
        return
    text = "📦 *منابع کشور:*\n\n"
    for k, v in res.items():
        if k != "user_id" and v and v > 0:
            text += f"{RESOURCES.get(k, k)}: {v:,}\n"
    await context.bot.send_message(update.effective_chat.id, text, parse_mode="Markdown")

def _admin_panel_payload(all_count, pending_count):
    text = f"👑 *پنل مدیریت*\n\n👥 بازیکنان: {all_count}\n⏳ در انتظار: {pending_count}"
    rows = [
        [InlineKeyboardButton("📋 لیست کشورها", callback_data="adm_list_0")],
        [InlineKeyboardButton("🚫 لیست مسدودها", callback_data="adm_banned_0")],
        [InlineKeyboardButton("⏳ در انتظار تایید", callback_data="adm_pending")],
        [InlineKeyboardButton("🛡️ لیست اسپم‌ها", callback_data="adm_spamlist")],
    ]
    return text, kb(rows)

async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    all_c = await get_all_countries()
    pl = await get_pending_all()
    text, keyboard = _admin_panel_payload(len(all_c), len(pl))
    await context.bot.send_message(update.effective_chat.id, text, parse_mode="Markdown", reply_markup=keyboard)

async def force_turn_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    ran = await process_turn(force=True)
    await update.message.reply_text("✅ نوبت اجرا شد." if ran else "⏭️ رد شد (اخیراً اجرا شده).")

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cb = update.callback_query
    data = cb.data or ""
    uid = cb.from_user.id
    chat_id = cb.message.chat.id
    msg_id = cb.message.message_id
    t = temp.get(uid, {})
    await cb.answer()

    async def edit(text, keyboard=None):
        try:
            await context.bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=text, parse_mode="Markdown", reply_markup=keyboard)
            return
        except Exception:
            pass
        try:
            await context.bot.edit_message_caption(chat_id=chat_id, message_id=msg_id, caption=text, parse_mode="Markdown", reply_markup=keyboard)
        except Exception:
            pass

    if data.startswith("bud_") and t.get("step") == "BUDGET_SET":
        if data == "bud_confirm":
            total = t["mil"] + t["sci"] + t["wel"] + t["inf"]
            if total > 100:
                await cb.answer("مجموع نمی‌تواند بیشتر از ۱۰۰ باشد!", show_alert=True)
                return
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE country_stats SET military_budget=$1, research_budget=$2, welfare_budget=$3, infrastructure_budget=$4 WHERE user_id=$5",
                    t["mil"], t["sci"], t["wel"], t["inf"], uid,
                )
            temp.pop(uid, None)
            await edit("✅ بودجه ثبت شد! حالا /cities برای نام‌گذاری شهرها.")
            return
        try:
            act = data.split("_")[1]
            val = int(data.split("_")[2])
        except Exception:
            return
        t[act] += val
        if t[act] < 0:
            t[act] = 0
        if t["mil"] + t["sci"] + t["wel"] + t["inf"] > 100:
            t[act] -= val
            await cb.answer("بیشتر از ۱۰۰ نمی‌شود!", show_alert=True)
        temp[uid] = t
        await show_budget_panel(chat_id, context, t)
        return

    if data.startswith("reign_"):
        mp = {"reign_5": "۵ سال", "reign_10": "۱۰ سال", "reign_20": "۲۰ سال", "reign_30": "۳۰ سال", "reign_life": "مادام‌العمر"}
        t["reign"] = mp.get(data, "۱۰ سال")
        t["step"] = "GOV"
        temp[uid] = t
        rows = [[InlineKeyboardButton(v, callback_data=f"gov_{k}")] for k, v in GOVS.items()]
        await edit("⚙️ *حکومت*:", kb(rows))
        return

    if data.startswith("gov_") and not data.startswith("govsub_"):
        gk = data.replace("gov_", "")
        if gk not in GOVS:
            return
        t["gov"] = GOVS[gk]
        t["step"] = "GOV_SUB"
        temp[uid] = t
        rows = [[InlineKeyboardButton(v[0], callback_data=f"govsub_{gk}_{k}")] for k, v in GOV_SUBS[gk].items()]
        await edit("🏛️ *نظام حکومتی*:", kb(rows))
        return

    if data.startswith("govsub_"):
        parts = data.replace("govsub_", "").split("_")
        gk = parts[0]
        sk = "_".join(parts[1:])
        if gk not in GOV_SUBS or sk not in GOV_SUBS[gk]:
            return
        sub, hap = GOV_SUBS[gk][sk]
        t["gov_sub"] = sub
        t["happiness"] = hap
        t["step"] = "RELIGION"
        temp[uid] = t
        rows = [[InlineKeyboardButton(v, callback_data=f"rel_{k}")] for k, v in RELIGIONS.items()]
        await edit("☪️ *دین*:", kb(rows))
        return

    if data.startswith("rel_") and not data.startswith("relsub_"):
        rk = data.replace("rel_", "")
        if rk not in RELIGIONS:
            return
        t["religion"] = RELIGIONS[rk]
        if rk == "secular" or rk not in REL_SUBS:
            t["rel_sub"] = "—"
            t["step"] = "EXPERT"
            temp[uid] = t
            rows = [[InlineKeyboardButton(v, callback_data=f"exp_{k}")] for k, v in EXPERTS.items()]
            await edit("🏭 *تخصص*:", kb(rows))
            return
        t["step"] = "REL_SUB"
        temp[uid] = t
        rows = [[InlineKeyboardButton(v, callback_data=f"relsub_{rk}_{k}")] for k, v in REL_SUBS[rk].items()]
        await edit("📖 *مذهب*:", kb(rows))
        return

    if data.startswith("relsub_"):
        parts = data.replace("relsub_", "").split("_")
        rk = parts[0]
        sk = "_".join(parts[1:])
        if rk not in REL_SUBS or sk not in REL_SUBS[rk]:
            return
        t["rel_sub"] = REL_SUBS[rk][sk]
        t["step"] = "EXPERT"
        temp[uid] = t
        rows = [[InlineKeyboardButton(v, callback_data=f"exp_{k}")] for k, v in EXPERTS.items()]
        await edit("🏭 *تخصص*:", kb(rows))
        return

    if data.startswith("exp_"):
        ek = data.replace("exp_", "")
        if ek not in EXPERTS:
            return
        t["expert"] = EXPERTS[ek]
        t["step"] = "MAP_REGION"
        temp[uid] = t
        taken = await get_taken_map_regions()
        rows, row, cnt = [], [], 0
        for code in REGIONS_19:
            if code in taken:
                row.append(InlineKeyboardButton(f"🔒 {code}", callback_data="region_locked"))
            else:
                row.append(InlineKeyboardButton(f"🟢 {code}", callback_data=f"mapregion_{code}"))
            cnt += 1
            if cnt % 3 == 0:
                rows.append(row)
                row = []
        if row:
            rows.append(row)
        await edit("📍 *منطقه جهانی* را انتخاب کن:", kb(rows))
        return

    if data == "region_locked":
        await cb.answer("🔒 این منطقه گرفته شده!", show_alert=True)
        return

    if data.startswith("mapregion_"):
        code = data.replace("mapregion_", "")
        taken = await get_taken_map_regions()
        if code in taken:
            await cb.answer("🔒 همین الان گرفته شد!", show_alert=True)
            return
        t["map_region"] = code
        t["step"] = "FLAG"
        temp[uid] = t
        await edit(f"✅ منطقه جهانی: *{code}*\n\n🖼️ حالا عکس پرچم کشورت رو بفرست:")
        return

    if data.startswith("city_view_"):
        cid = int(data.split("_")[2])
        regs = await get_city_zones(cid)
        text = "🏙️ نواحی شهر:\n\n" + ("\n".join(f"📍 {r['name']} ({r['used']}/{r['capacity']})" for r in regs) if regs else "خالی")
        rows = []
        if len(regs) < 3:
            rows.append([InlineKeyboardButton("➕ تاسیس ناحیه جدید", callback_data=f"newreg_{cid}")])
        if regs:
            rows.append([InlineKeyboardButton("🏗️ ساخت در نواحی", callback_data=f"build_in_{cid}")])
        rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="back_cities")])
        await edit(text, kb(rows))
        return

    if data.startswith("newreg_") and not data.startswith("newreg_type_") and not data.startswith("newreg_size_"):
        cid = int(data.split("_")[1])
        t["newreg_city"] = cid
        temp[uid] = t
        rows = [[InlineKeyboardButton(v, callback_data=f"newreg_type_{k}")] for k, v in ZONE_TYPES.items()]
        rows.append([InlineKeyboardButton("🔙 انصراف", callback_data="back_cities")])
        await edit("🏗️ نوع ناحیه جدید:", kb(rows))
        return

    if data.startswith("newreg_type_"):
        rt = data[len("newreg_type_"):]
        if rt not in ZONE_TYPES:
            return
        t["newreg_type"] = rt
        temp[uid] = t
        rows = [[InlineKeyboardButton(f"{v['name']} ({fmt_money(v['cost'])})", callback_data=f"newreg_size_{k}")] for k, v in ZONE_SIZES.items()]
        await edit("📐 اندازه ناحیه:", kb(rows))
        return

    if data.startswith("newreg_size_"):
        sz = data[len("newreg_size_"):]
        if sz not in ZONE_SIZES:
            return
        info = ZONE_SIZES[sz]
        s = await get_stats(uid)
        if not s or s["treasury"] < info["cost"]:
            await cb.answer("❌ خزانه کافی نیست!", show_alert=True)
            return
        async with pool.acquire() as conn:
            await conn.execute("UPDATE country_stats SET treasury = treasury - $1 WHERE user_id = $2", info["cost"], uid)
            await conn.execute(
                "INSERT INTO city_zones (user_id, city_id, zone_type, name, size, capacity, used) VALUES ($1, $2, $3, $4, $5, $6, 0)",
                uid, t["newreg_city"], t["newreg_type"], f"ناحیه {ZONE_TYPES.get(t['newreg_type'], t['newreg_type'])}", sz, info["capacity"],
            )
        temp.pop(uid, None)
        await edit("✅ ناحیه ساخته شد! از /zones برای مدیریت استفاده کنید.")
        return

    if data.startswith("build_in_"):
        cid = int(data.split("_")[2])
        regs = await get_city_zones(cid)
        rows = [[InlineKeyboardButton(f"📍 {r['name']}", callback_data=f"bld_reg_{r['id']}")] for r in regs]
        await edit("انتخاب ناحیه برای ساخت:", kb(rows))
        return

    if data.startswith("bld_reg_"):
        rid = int(data.split("_")[2])
        reg = await get_one_zone(rid, uid)
        if not reg:
            await cb.answer("پیدا نشد!", show_alert=True)
            return
        if reg["used"] >= reg["capacity"]:
            await cb.answer("پر است!", show_alert=True)
            return
        avail = [(k, v) for k, v in BUILDINGS.items() if v["type"] == reg["zone_type"]]
        if not avail:
            await cb.answer("ساختمونی برای این نوع نیست!", show_alert=True)
            return
        t["bld_reg"] = rid
        temp[uid] = t
        rows = [[InlineKeyboardButton(f"{v['name']} ({fmt_money(v['cost'])})", callback_data=f"bld_make_{k}")] for k, v in avail]
        await edit("🏗️ انتخاب ساختمون:", kb(rows))
        return

    if data.startswith("bld_make_"):
        bk = data[len("bld_make_"):]
        if bk not in BUILDINGS:
            await cb.answer("ساختمون نامعتبر!", show_alert=True)
            return
        b = BUILDINGS[bk]
        s = await get_stats(uid)
        if not s or s["treasury"] < b["cost"]:
            await cb.answer("❌ خزانه کم است!", show_alert=True)
            return
        rid = t.get("bld_reg")
        if not rid:
            await cb.answer("جلسه منقضی شده، دوباره تلاش کن.", show_alert=True)
            return
        async with pool.acquire() as conn:
            await conn.execute("UPDATE country_stats SET treasury = treasury - $1 WHERE user_id = $2", b["cost"], uid)
            await conn.execute("INSERT INTO zone_buildings (zone_id, building_key) VALUES ($1, $2)", rid, bk)
            await conn.execute("UPDATE city_zones SET used = used + 1 WHERE id = $1", rid)
        await cb.answer("✅ ساخته شد!", show_alert=True)
        temp.pop(uid, None)
        await edit("✅ ساختمون ساخته شد!")
        return

    if data == "back_cities":
        cities = await get_cities(uid)
        if len(cities) < 10:
            await edit("❌ ابتدا باید ۱۰ شهر بسازید. /cities")
            return
        rows = [[InlineKeyboardButton(f"🏙️ {city['name']}", callback_data=f"city_view_{city['id']}")] for city in cities]
        await edit("🏙️ یک شهر برای مدیریت نواحی انتخاب کنید:", kb(rows))
        return

    if data == "adm_panel" and uid == ADMIN_ID:
        all_c = await get_all_countries()
        pl = await get_pending_all()
        text, keyboard = _admin_panel_payload(len(all_c), len(pl))
        await edit(text, keyboard)
        return

    if data == "adm_pending" and uid == ADMIN_ID:
        pl = await get_pending_all()
        if not pl:
            await cb.answer("لیست خالی است.", show_alert=True)
            return
        for p in pl:
            txt = f"🏛️ {p['name']}\n📍 {p.get('map_region', '—')}\n👤 {p['leader']}\n⚙️ {p['gov_sub']}"
            btn = [[
                InlineKeyboardButton("✅ تایید", callback_data=f"adm_ok_{p['user_id']}"),
                InlineKeyboardButton("❌ رد", callback_data=f"adm_no_{p['user_id']}"),
            ]]
            try:
                await context.bot.send_photo(chat_id, p["flag_id"], caption=txt, reply_markup=kb(btn))
            except Exception:
                await context.bot.send_message(chat_id, txt, reply_markup=kb(btn))
        return

    if data.startswith("adm_ok_") or data.startswith("adm_no_"):
        action = "ok" if data.startswith("adm_ok_") else "no"
        try:
            tu = int(data.split("_")[2])
        except Exception:
            return
        p = await get_pending(tu)
        if not p:
            try:
                await cb.message.delete()
            except Exception:
                pass
            await context.bot.send_message(chat_id, "⚠️ این درخواست قبلاً پردازش شده.")
            return
        if action == "ok":
            await save_country(tu, p)
            await delete_pending(tu)
            try:
                await context.bot.send_message(tu, "🎉 کشور شما تایید شد! حالا از /cities استفاده کنید.")
                await context.bot.send_message(tu, "از /economy برای تنظیم بودجه استفاده کنید.")
            except Exception:
                pass
            try:
                await cb.message.delete()
            except Exception:
                pass
            await context.bot.send_message(chat_id, f"✅ کشور «{p['name']}» در منطقه {p.get('map_region', '—')} تایید شد.")
        else:
            await delete_pending(tu)
            try:
                await context.bot.send_message(tu, "❌ درخواست شما رد شد.")
            except Exception:
                pass
            try:
                await cb.message.delete()
            except Exception:
                pass
            await context.bot.send_message(chat_id, f"❌ درخواست «{p['name']}» رد شد.")
        return

    if data == "adm_spamlist" and uid == ADMIN_ID:
        if not banned_users:
            await edit("خالی.")
            return
        text = "🛡️ *کاربران اسپم:*\n\n"
        btns = []
        for b in banned_users:
            text += f"🆔 `{b}`\n"
            btns.append([InlineKeyboardButton(f"✅ رفع {b}", callback_data=f"adm_unspam_{b}")])
        btns.append([InlineKeyboardButton("🔙 پنل", callback_data="adm_panel")])
        await edit(text, kb(btns))
        return

    if data.startswith("adm_unspam_") and uid == ADMIN_ID:
        try:
            tu = int(data.split("_")[2])
        except Exception:
            return
        banned_users.discard(tu)
        await remove_spam_ban(tu)
        await edit("✅ رفع شد.", kb([[InlineKeyboardButton("🔙 لیست", callback_data="adm_spamlist")]]))
        return

    if data.startswith("adm_list_") and uid == ADMIN_ID:
        try:
            page = int(data.split("_")[2])
        except Exception:
            page = 0
        await show_country_list(chat_id, msg_id, context, page, "all")
        return

    if data.startswith("adm_banned_") and uid == ADMIN_ID:
        try:
            page = int(data.split("_")[2])
        except Exception:
            page = 0
        await show_country_list(chat_id, msg_id, context, page, "banned")
        return

    if data.startswith("adm_view_") and uid == ADMIN_ID:
        try:
            tu = int(data.split("_")[2])
        except Exception:
            return
        c = await get_country(tu)
        if not c:
            await cb.answer("پیدا نشد!", show_alert=True)
            return
        st = "✅ فعال" if c["status"] == "approved" else "🚫 مسدود" if c["status"] == "banned" else "⏳ در انتظار"
        text = (
            f"🏛️ *{c['name']}*\n\n"
            f"📍 منطقه جهانی: {c.get('map_region', '—')}\n"
            f"👤 رهبر: {c['leader']}\n🎂 سن: {c['age']}\n"
            f"⚙️ حکومت: {c['gov_sub']}\n"
            f"☪️ دین: {c['religion']}\n"
            f"🏭 تخصص: {c['expert']}\n"
            f"📌 وضعیت: {st}\n\n"
            f"👤 کاربر: @{c.get('username', '')}\n🆔 `{c['user_id']}`"
        )
        btns = []
        if c["status"] == "banned":
            btns.append([InlineKeyboardButton("✅ رفع مسدودی", callback_data=f"adm_unban_{tu}")])
        else:
            btns.append([InlineKeyboardButton("🚫 مسدود کردن", callback_data=f"adm_ban_{tu}")])
        btns.append([InlineKeyboardButton("🗑️ حذف کامل کشور", callback_data=f"adm_del_{tu}")])
        btns.append([InlineKeyboardButton("🔙 بازگشت", callback_data="adm_list_0")])
        await edit(text, kb(btns))
        return

    if data.startswith("adm_ban_") and uid == ADMIN_ID:
        try:
            tu = int(data.split("_")[2])
        except Exception:
            return
        temp[uid] = {"step": "BAN_REASON", "targetUid": tu}
        await edit(f"📝 دلیل مسدودیت را بنویس:\n\n🆔 هدف: `{tu}`", kb([[InlineKeyboardButton("❌ لغو", callback_data=f"adm_view_{tu}")]]))
        return

    if data.startswith("adm_unban_") and uid == ADMIN_ID:
        try:
            tu = int(data.split("_")[2])
        except Exception:
            return
        await set_status(tu, "approved", None)
        try:
            await context.bot.send_message(tu, "✅ کشور شما از مسدودی خارج شد!")
        except Exception:
            pass
        await cb.answer("رفع مسدودی شد.", show_alert=True)
        await edit("✅ انجام شد.", kb([[InlineKeyboardButton("🔙 لیست", callback_data="adm_list_0")]]))
        return

    if data.startswith("adm_del_") and uid == ADMIN_ID:
        try:
            tu = int(data.split("_")[2])
        except Exception:
            return
        await delete_country(tu)
        try:
            await context.bot.send_message(tu, "🗑️ کشور شما توسط ادمین حذف شد.")
        except Exception:
            pass
        await edit("🗑️ حذف شد.", kb([[InlineKeyboardButton("🔙 لیست", callback_data="adm_list_0")]]))
        return

async def show_country_list(chat_id, msg_id, context, page, status):
    per_page = 5
    offset = page * per_page
    all_list = await get_banned() if status == "banned" else await get_all_countries()
    page_list = all_list[offset:offset + per_page]
    if not page_list:
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id, message_id=msg_id,
                text=("🚫 خالی." if status == "banned" else "📋 خالی."),
            )
        except Exception:
            pass
        return
    text = "🚫 *کشورهای مسدود:*\n\n" if status == "banned" else "📋 *لیست کشورها:*\n\n"
    buttons = []
    for c in page_list:
        icon = "✅" if c["status"] == "approved" else "🚫" if c["status"] == "banned" else "⏳"
        text += f"{icon} *{c['name']}* — {c.get('map_region', '—')}\n\n"
        buttons.append([InlineKeyboardButton(f"🔍 {c['name']}", callback_data=f"adm_view_{c['user_id']}")])
    prefix = "banned" if status == "banned" else "list"
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ قبلی", callback_data=f"adm_{prefix}_{page-1}"))
    nav.append(InlineKeyboardButton("🔙 پنل", callback_data="adm_panel"))
    if offset + per_page < len(all_list):
        nav.append(InlineKeyboardButton("➡️ بعدی", callback_data=f"adm_{prefix}_{page+1}"))
    buttons.append(nav)
    try:
        await context.bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=text, parse_mode="Markdown", reply_markup=kb(buttons))
    except Exception:
        pass

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = (update.message.text or "").strip()
    t = temp.get(uid)
    if not t:
        return

    if t.get("step") == "NAME":
        if len(text) < 3 or len(text) > 25:
            await update.message.reply_text("❌ ۳ تا ۲۵ حرف:")
            return
        t["name"] = text
        t["step"] = "LEADER"
        temp[uid] = t
        await update.message.reply_text("👤 نام رهبر:")
    elif t.get("step") == "LEADER":
        t["leader"] = text
        t["step"] = "AGE"
        temp[uid] = t
        await update.message.reply_text("🎂 سن رهبر (۳۵-۴۵):")
    elif t.get("step") == "AGE":
        if not text.isdigit() or not (35 <= int(text) <= 45):
            await update.message.reply_text("عدد بین ۳۵ تا ۴۵:")
            return
        t["age"] = int(text)
        t["step"] = "REIGN"
        temp[uid] = t
        rows = [[
            InlineKeyboardButton("۱۰ سال", callback_data="reign_10"),
            InlineKeyboardButton("۲۰ سال", callback_data="reign_20"),
            InlineKeyboardButton("مادام‌العمر", callback_data="reign_life"),
        ]]
        await update.message.reply_text("⏳ مدت حکومت:", reply_markup=kb(rows))
    elif t.get("step") == "CITY_NAME":
        async with pool.acquire() as conn:
            await conn.execute("INSERT INTO cities (user_id, name) VALUES ($1, $2)", uid, text)
            cnt = await conn.fetchval("SELECT COUNT(*) FROM cities WHERE user_id = $1", uid)
        if cnt >= 10:
            temp.pop(uid, None)
            await update.message.reply_text("✅ ۱۰ شهر ثبت شد! حالا از /economy برای تنظیم بودجه استفاده کنید.")
        else:
            await update.message.reply_text(f"✅ شهر ثبت شد. نام شهر شماره {cnt+1}:")
    elif t.get("step") == "BAN_REASON" and uid == ADMIN_ID:
        tu = t.get("targetUid")
        await set_status(tu, "banned", text)
        temp.pop(uid, None)
        await update.message.reply_text(f"🚫 مسدود شد.\n📝 دلیل: {text}")
        try:
            await context.bot.send_message(tu, f"🚫 کشور شما مسدود شد.\n📝 دلیل: {text}")
        except Exception:
            pass

async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    t = temp.get(uid)
    if not t or t.get("step") != "FLAG":
        return
    taken = await get_taken_map_regions()
    if t.get("map_region") in taken:
        temp.pop(uid, None)
        await update.message.reply_text(f"❌ منطقه {t.get('map_region')} همین الان گرفته شد. /start")
        return
    t["flag_id"] = update.message.photo[-1].file_id
    await save_pending(uid, t)
    temp.pop(uid, None)
    await context.bot.send_message(
        ADMIN_ID, "📥 درخواست جدید ثبت شد!",
        reply_markup=kb([[InlineKeyboardButton("مشاهده", callback_data="adm_pending")]]),
    )
    await update.message.reply_text("⏳ ارسال شد. منتظر تایید.")

async def process_turn(force: bool = False) -> bool:
    async with pool.acquire() as conn:
        async with conn.transaction():
            state = await conn.fetchrow(
                "SELECT current_year, current_month, total_turns, last_update FROM game_state WHERE id=1 FOR UPDATE"
            )
            if not state:
                return False
            if not force:
                recent = await conn.fetchval(
                    "SELECT last_update IS NOT NULL AND NOW() - last_update < INTERVAL '23 hours' FROM game_state WHERE id=1"
                )
                if recent:
                    return False

            rows = await conn.fetch(
                """SELECT zb.building_key, cz.user_id
                   FROM zone_buildings zb
                   JOIN city_zones cz ON cz.id = zb.zone_id"""
            )
            by_user = defaultdict(list)
            for r in rows:
                by_user[r["user_id"]].append(r["building_key"])

            for user_id, bkeys in by_user.items():
                res_row = await conn.fetchrow("SELECT * FROM country_resources WHERE user_id=$1 FOR UPDATE", user_id)
                stats_row = await conn.fetchrow("SELECT * FROM country_stats WHERE user_id=$1 FOR UPDATE", user_id)
                if not res_row or not stats_row:
                    continue
                res = dict(res_row)
                stats = dict(stats_row)
                total_workers = 0
                total_income = 0
                pop_gain = 0

                for bkey in bkeys:
                    bdef = BUILDINGS.get(bkey)
                    if not bdef:
                        continue
                    inputs = bdef.get("input", {})
                    if not all(res.get(k, 0) >= v for k, v in inputs.items()):
                        continue
                    for k, v in inputs.items():
                        res[k] = res.get(k, 0) - v
                    for k, v in bdef.get("output", {}).items():
                        res[k] = res.get(k, 0) + v
                    total_workers += bdef.get("workers", 0)
                    total_income += bdef.get("income", 0)
                    pop_gain += bdef.get("pop", 0)

                cols = [k for k in res.keys() if k != "user_id"]
                set_clause = ", ".join(f"{k}=${i+2}" for i, k in enumerate(cols))
                await conn.execute(
                    f"UPDATE country_resources SET {set_clause} WHERE user_id=$1",
                    user_id, *[res[k] for k in cols],
                )

                army = stats.get("army", 0) or 0
                treasury_delta = (total_income * 1000) - (army * 200) - (total_workers * 5)

                mil_b = (stats.get("military_budget") or 0) / 100.0
                sci_b = (stats.get("research_budget") or 0) / 100.0
                wel_b = (stats.get("welfare_budget") or 0) / 100.0
                inf_b = (stats.get("infrastructure_budget") or 0) / 100.0
                edu_b = (stats.get("education_budget") or 0) / 100.0

                pop_growth = 0.005 + wel_b * 0.02 + inf_b * 0.01
                new_pop = int((stats["population"] + pop_gain) * (1 + pop_growth))
                sci_growth = 0.003 + sci_b * 0.05 + edu_b * 0.02
                new_sci_base = int(stats.get("science_base", 10) * (1 + sci_growth))
                new_sci_appl = int(stats.get("science_applied", 10) * (1 + sci_growth * 0.8))
                gdp_growth = 0.01 + sci_b * 0.02 + inf_b * 0.03 + mil_b * 0.005 + wel_b * 0.01
                new_gdp = int(stats["gdp"] * (1 + gdp_growth))

                await conn.execute(
                    """UPDATE country_stats SET
                       treasury = GREATEST(0, treasury + $1),
                       population = $2,
                       gdp = $3,
                       science_base = $4,
                       science_applied = $5
                       WHERE user_id = $6""",
                    treasury_delta, new_pop, new_gdp, new_sci_base, new_sci_appl, user_id,
                )

            new_month = state["current_month"] + 1
            new_year = state["current_year"]
            if new_month > 12:
                new_month = 1
                new_year += 1
            await conn.execute(
                """UPDATE game_state
                   SET current_year=$1, current_month=$2,
                       total_turns=total_turns+1, last_update=NOW()
                   WHERE id=1""",
                new_year, new_month,
            )
            logger.info("Turn advanced to %s/%s", new_year, new_month)
            return True

async def _daily_turn_job(context):
    try:
        ran = await process_turn()
        if ran:
            logger.info("Daily turn processed.")
    except Exception:
        logger.exception("Daily turn failed.")

async def post_init(app):
    await init_db()
    await set_commands(app)
    await app.bot.delete_webhook(drop_pending_updates=True)

    try:
        ran = await process_turn()
        if ran:
            logger.info("Catch-up turn executed on startup.")
    except Exception:
        logger.exception("Catch-up turn failed.")

    if app.job_queue:
        app.job_queue.run_daily(
            _daily_turn_job,
            time=dt_time(hour=0, minute=5, tzinfo=dt_timezone.utc),
            name="daily_turn",
        )
        logger.info("Daily turn scheduled at 00:05 UTC.")
    else:
        logger.warning("JobQueue not available — install python-telegram-bot[job-queue]")

def main():
    app = Application.builder().token(TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CommandHandler("date", date_cmd))
    app.add_handler(CommandHandler("country", country_cmd))
    app.add_handler(CommandHandler("cities", cities_cmd))
    app.add_handler(CommandHandler("economy", economy_cmd))
    app.add_handler(CommandHandler("zones", zones_cmd))
    app.add_handler(CommandHandler("build", zones_cmd))
    app.add_handler(CommandHandler("resources", resources_cmd))
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(CommandHandler("force_turn", force_turn_cmd))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    app.add_handler(MessageHandler(filters.PHOTO, photo_handler))

    rh = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
    if rh:
        port = int(os.environ.get("PORT", 10000))
        app.run_webhook(listen="0.0.0.0", port=port, url_path=TOKEN, webhook_url=f"https://{rh}/{TOKEN}", drop_pending_updates=True)
    else:
        app.run_polling()

if __name__ == "__main__":
    main()
