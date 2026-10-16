import os
import time
import random
import asyncpg
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes,
)

TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_ID = 8849773822
DATABASE_URL = os.environ.get("DATABASE_URL", "")

if not TOKEN:
    raise SystemExit("BOT_TOKEN not set!")
if not DATABASE_URL:
    raise SystemExit("DATABASE_URL not set!")

BASE_POPULATION = 15_000_000
BASE_GDP = 500_000
BASE_TREASURY = 50_000
SOLDIER_COST = 1500
POP_CAP_RATIO = 0.02

REGIONS_19 = [
    "III", "GGG", "YYY", "OOO", "TTT", "FFF", "SSS", "AAA", "HHH", "KKK",
    "LLL", "RRR", "DDD", "WWW", "QQQ", "UUU", "PPP", "EEE", "MMM",
]

GOVS = {
    "dictator": "✊ دیکتاتوری",
    "democracy": "🗳️ دموکراسی",
    "religious": "🕌 دینی (تئوکراسی)",
    "monarch": "👑 سلطنتی",
    "communist": "☭ کمونیستی",
    "republic": "🏛️ جمهوری",
}

GOV_SUBS = {
    "dictator": {
        "mil": ["🔒 دیکتاتوری نظامی", 35, "🪖"],
        "personal": ["👑 دیکتاتوری فردی", 25, "👤"],
    },
    "democracy": {
        "parl": ["📜 دموکراسی پارلمانی", 85, "👥"],
        "pres": ["🗳️ دموکراسی ریاستی", 80, "👥"],
    },
    "religious": {
        "trad": ["🕌 تئوکراسی سنتی", 70, "🕌"],
        "mod": ["⚖️ تئوکراسی میانه‌رو", 80, "🤝"],
        "mil": ["🛡️ تئوکراسی نظامی-دینی", 55, "🪖"],
        "legal": ["📜 تئوکراسی قانون‌گرا", 75, "📜"],
        "radical": ["💀 تئوکراسی افراطی", 25, "💀"],
    },
    "monarch": {
        "abs": ["👑 سلطنت مطلقه", 45, "👑"],
        "const": ["🏛️ سلطنت مشروطه", 75, "👥"],
    },
    "communist": {
        "one": ["☭ کمونیسم تک‌حزبی", 60, "☭"],
    },
    "republic": {
        "sec": ["🏛️ جمهوری سکولار", 80, "👥"],
        "theo": ["⚖️ جمهوری تئوکراتیک", 55, "📖"],
    },
}

RELIGIONS = {
    "islam": "☪️ اسلام",
    "christ": "✝️ مسیحیت",
    "jew": "✡️ یهودیت",
    "hindu": "🕉️ هندوئیسم",
    "budd": "☸️ بودیسم",
    "secular": "🕊️ سکولار",
}

REL_SUBS = {
    "islam": {
        "shia12": "🔵 شیعه دوازده‌امامی",
        "shia_ism": "🟢 شیعه اسماعیلی",
        "shia_zayd": "🟡 شیعه زیدی",
        "suni_hanafi": "🟠 سنی حنفی",
        "suni_shafei": "🔴 سنی شافعی",
        "suni_maleki": "🟣 سنی مالکی",
        "suni_hanbali": "⚫ سنی حنبلی",
    },
    "christ": {"cath": "⛪ کاتولیک", "orth": "🏛️ ارتدوکس", "prot": "📖 پروتستان"},
    "jew": {"orth": "✡️ ارتدوکس", "cons": "🕎 محافظه‌کار", "ref": "📜 اصلاح‌طلب"},
    "budd": {"thera": "🟡 تراوادا", "maha": "🔴 ماهایانا", "vajra": "⚫ وجریانا"},
}

EXPERTS = {
    "heavy": "🏭 صنایع سنگین",
    "energy": "⛽ سوخت و انرژی",
    "grain": "🌾 غلات و کشاورزی",
    "military": "🔫 صنایع نظامی",
}

GOV_GDP_COEF = {
    "دموکراسی پارلمانی": 1.3, "دموکراسی ریاستی": 1.2,
    "جمهوری سکولار": 1.2, "سلطنت مشروطه": 1.1,
    "جمهوری تئوکراتیک": 1.0, "سلطنت مطلقه": 0.9,
    "تئوکراسی میانه‌رو": 0.8, "تئوکراسی قانون‌گرا": 0.8,
    "کمونیسم تک‌حزبی": 0.8, "تئوکراسی نظامی-دینی": 0.8,
    "دیکتاتوری نظامی": 0.8, "دیکتاتوری فردی": 0.7,
    "تئوکراسی افراطی": 0.5,
}

GOV_MIL_COEF = {
    "دیکتاتوری نظامی": 2.0, "تئوکراسی نظامی-دینی": 1.8,
    "تئوکراسی افراطی": 1.7, "دیکتاتوری فردی": 1.5,
    "کمونیسم تک‌حزبی": 1.4, "سلطنت مطلقه": 1.3,
    "سلطنت مشروطه": 1.0, "جمهوری تئوکراتیک": 1.0,
    "تئوکراسی میانه‌رو": 0.9, "تئوکراسی قانون‌گرا": 0.9,
    "جمهوری سکولار": 0.8, "دموکراسی ریاستی": 0.8,
    "دموکراسی پارلمانی": 0.7,
}

RELIGION_COEF = {
    "سکولار": 1.1, "اسلام": 1.0, "مسیحیت": 0.95,
    "یهودیت": 1.0, "بودیسم": 0.9, "هندوئیسم": 0.8,
}

EXPERT_GDP_COEF = {
    "صنایع سنگین": 1.3, "سوخت و انرژی": 1.5,
    "غلات و کشاورزی": 1.0, "صنایع نظامی": 1.1,
}

REGION_COEF = {
    "III": 1.2, "GGG": 1.1, "YYY": 1.1, "OOO": 1.0, "TTT": 1.0,
    "FFF": 1.0, "SSS": 1.0, "AAA": 1.0, "HHH": 1.0, "KKK": 1.0,
    "LLL": 0.9, "RRR": 0.9, "DDD": 0.9, "WWW": 0.9, "QQQ": 0.9,
    "UUU": 1.0, "PPP": 1.0, "EEE": 1.0, "MMM": 1.0,
}

RES_NAMES = {
    "water": "💧 آب", "wheat": "🌾 گندم", "iron": "⛏ آهن",
    "titanium": "⚙️ تیتانیوم", "gold": "🏵 طلا", "oil": "🛢 نفت",
    "power": "⚡️ برق", "steel": "🏗 فولاد",
    "yellowcake": "🟡 کیک زرد", "uranium": "☢ اورانیوم",
}

REGION_SIZES = {
    "small": {"name": "کوچک", "capacity": 3, "cost": 1500},
    "medium": {"name": "متوسط", "capacity": 6, "cost": 3000},
    "large": {"name": "بزرگ", "capacity": 10, "cost": 6000},
    "huge": {"name": "عظیم", "capacity": 20, "cost": 15000},
}

REGION_TYPES = {
    "residential": "🏘️ مسکونی",
    "industrial": "🏭 صنعتی",
    "agricultural": "🌾 کشاورزی",
    "extractive": "⛽ استخراجی",
    "mining": "⛏️ معدنی",
    "commercial": "🏪 تجاری",
}

BUILDINGS = {
    "park": {"name": "🌳 پارک", "type": "residential", "cost": 500, "workers": 50, "happiness": 0.5},
    "school": {"name": "🏫 مدرسه", "type": "residential", "cost": 1000, "workers": 200, "edu": 100},
    "house": {"name": "🏠 خانه", "type": "residential", "cost": 200, "workers": 10, "pop": 100_000},
    "apartment": {"name": "🏢 آپارتمان", "type": "residential", "cost": 1500, "workers": 50, "pop": 500_000, "happiness": 0.3},
    "hospital": {"name": "🏥 بیمارستان", "type": "residential", "cost": 5000, "workers": 500, "happiness": 2.0},
    "tower": {"name": "🏙️ برج", "type": "residential", "cost": 5000, "workers": 200, "pop": 1_500_000, "happiness": 0.5},
    "skyscraper": {"name": "🌆 آسمان‌خراش", "type": "residential", "cost": 15000, "workers": 800, "pop": 5_000_000, "happiness": 1.0},
    "vocational": {"name": "🔧 هنرستان", "type": "educational", "cost": 4000, "workers": 300},
    "university": {"name": "🎓 دانشگاه", "type": "educational", "cost": 12000, "workers": 1000},
    "research": {"name": "👨‍🔬 پژوهشگاه", "type": "educational", "cost": 25000, "workers": 2500},
    "small_workshop": {"name": "🏭 کارگاه کوچک", "type": "industrial", "cost": 7000, "workers": 100, "input": {"oil": 15, "power": 5, "steel": 2}, "income": 1500},
    "medium_factory": {"name": "🏭 کارخانه متوسط", "type": "industrial", "cost": 10000, "workers": 200, "input": {"oil": 20, "power": 7, "steel": 3}, "income": 2000},
    "big_factory": {"name": "🏭 کارخانه بزرگ", "type": "industrial", "cost": 15000, "workers": 350, "input": {"oil": 25, "power": 10, "steel": 5}, "income": 6000},
    "huge_factory": {"name": "🏭 کارخانه عظیم", "type": "industrial", "cost": 25000, "workers": 600, "input": {"oil": 40, "power": 15, "steel": 8}, "income": 23000},
    "oil_refinery": {"name": "🛢 پالایشگاه نفت", "type": "industrial", "cost": 5000, "workers": 50, "input": {"power": 25, "steel": 1}, "output": {"oil": 250}, "income": 250},
    "power_plant": {"name": "⚡️ پالایشگاه برق", "type": "industrial", "cost": 5000, "workers": 80, "input": {"oil": 5, "steel": 2}, "output": {"power": 100}, "income": 400},
    "iron_mine": {"name": "⛏ معدن آهن", "type": "mining", "cost": 1000, "workers": 45, "input": {"power": 50, "oil": 5}, "output": {"iron": 1, "steel": 1}},
    "gold_mine": {"name": "🏵 معدن طلا", "type": "mining", "cost": 8000, "workers": 50, "input": {"oil": 5, "power": 4}, "output": {"gold": 5}},
    "titanium_mine": {"name": "⚙️ معدن تیتانیوم", "type": "mining", "cost": 12000, "workers": 55, "input": {"oil": 10, "power": 10}, "output": {"titanium": 5}},
    "wheat_farm": {"name": "🌾 مزرعه گندم", "type": "agricultural", "cost": 1000, "workers": 100, "output": {"wheat": 100}},
    "livestock": {"name": "🐄 دامداری", "type": "agricultural", "cost": 1500, "workers": 150, "output": {"wheat": 150}},
    "bazaar": {"name": "🏪 بازار", "type": "commercial", "cost": 2000, "workers": 100, "income": 300},
    "mall": {"name": "🏬 مرکز خرید", "type": "commercial", "cost": 8000, "workers": 300, "income": 1200},
    "bank": {"name": "🏦 بانک", "type": "commercial", "cost": 15000, "workers": 200, "income": 2500},
    "port": {"name": "🚢 بندر", "type": "commercial", "cost": 30000, "workers": 500, "income": 5000, "unlocks_trade": True},
    "dam": {"name": "🌊 سد", "type": "infrastructure", "cost": 1500, "workers": 20, "input": {"power": 60}, "output": {"water": 120}},
}

temp = {}
spam_tracker = {}
banned_users = set()
SPAM_LIMIT = 5
SPAM_WINDOW = 10
pool = None


def kb(rows):
    return InlineKeyboardMarkup(rows)


def check_spam(uid):
    now = time.time()
    if uid not in spam_tracker:
        spam_tracker[uid] = []
    spam_tracker[uid] = [t for t in spam_tracker[uid] if now - t < SPAM_WINDOW]
    spam_tracker[uid].append(now)
    if len(spam_tracker[uid]) > SPAM_LIMIT:
        banned_users.add(uid)
        return True
    return False


def fmt_money(amount):
    d = amount * 1000
    if d >= 1_000_000_000:
        return f"{d/1_000_000_000:.2f} میلیارد دلار"
    if d >= 1_000_000:
        return f"{d/1_000_000:.1f} میلیون دلار"
    if d >= 1_000:
        return f"{d/1_000:.0f} هزار دلار"
    return f"{d:.0f} دلار"


def fmt_date(year, month):
    mn = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
          "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]
    return f"{mn[month-1]} {year}"


async def init_db():
    global pool
    pool = await asyncpg.create_pool(
        DATABASE_URL, min_size=1, max_size=1, command_timeout=60
    )
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS countries (
                user_id BIGINT PRIMARY KEY,
                username TEXT, name TEXT, leader TEXT, age INT,
                reign TEXT, gov TEXT, gov_sub TEXT,
                religion TEXT, rel_sub TEXT, expert TEXT, region TEXT,
                happiness INT, science TEXT, flag_id TEXT, status TEXT,
                economy INT DEFAULT 500, army INT DEFAULT 100,
                revolt INT DEFAULT 5, ban_reason TEXT
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS pending (
                user_id BIGINT PRIMARY KEY,
                username TEXT, name TEXT, leader TEXT, age INT,
                reign TEXT, gov TEXT, gov_sub TEXT,
                religion TEXT, rel_sub TEXT, expert TEXT, region TEXT,
                happiness INT, science TEXT, flag_id TEXT
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS regions (
                code TEXT PRIMARY KEY, user_id BIGINT
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS spam_banned (user_id BIGINT PRIMARY KEY)
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS game_state (
                id INT PRIMARY KEY DEFAULT 1,
                current_year INT DEFAULT 2075,
                current_month INT DEFAULT 1,
                total_turns INT DEFAULT 0,
                last_update TIMESTAMP DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS country_stats (
                user_id BIGINT PRIMARY KEY,
                gdp BIGINT DEFAULT 500000,
                treasury BIGINT DEFAULT 50000,
                population BIGINT DEFAULT 15000000,
                tax_rate INT DEFAULT 25,
                infrastructure INT DEFAULT 25,
                happiness INT DEFAULT 60,
                science_base INT DEFAULT 10,
                science_applied INT DEFAULT 10,
                science_military INT DEFAULT 10,
                science_space INT DEFAULT 5,
                research_budget INT DEFAULT 3,
                military_budget INT DEFAULT 5,
                education_budget INT DEFAULT 3,
                infrastructure_budget INT DEFAULT 5,
                welfare_budget INT DEFAULT 10,
                army INT DEFAULT 0,
                unemployment INT DEFAULT 0
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS country_regions (
                id SERIAL PRIMARY KEY,
                user_id BIGINT, region_code TEXT, region_type TEXT,
                name TEXT, size TEXT, capacity INT, used INT DEFAULT 0
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS region_buildings (
                id SERIAL PRIMARY KEY,
                region_id INT, building_key TEXT
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS country_resources (
                user_id BIGINT PRIMARY KEY,
                water BIGINT DEFAULT 0, wheat BIGINT DEFAULT 0,
                iron BIGINT DEFAULT 0, titanium BIGINT DEFAULT 0,
                gold BIGINT DEFAULT 0, oil BIGINT DEFAULT 0,
                power BIGINT DEFAULT 0, steel BIGINT DEFAULT 0,
                yellowcake BIGINT DEFAULT 0, uranium BIGINT DEFAULT 0
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS resource_capacities (
                user_id BIGINT PRIMARY KEY,
                water BIGINT DEFAULT 1000000, wheat BIGINT DEFAULT 100000,
                iron BIGINT DEFAULT 50000, titanium BIGINT DEFAULT 20000,
                gold BIGINT DEFAULT 10000, oil BIGINT DEFAULT 1000000,
                power BIGINT DEFAULT 500000, steel BIGINT DEFAULT 50000,
                yellowcake BIGINT DEFAULT 5000, uranium BIGINT DEFAULT 10000
            )
        """)
        r = await conn.fetchrow("SELECT * FROM game_state WHERE id = 1")
        if not r:
            await conn.execute("INSERT INTO game_state (id) VALUES (1)")
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT user_id FROM spam_banned")
        for r in rows:
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
        await conn.execute("""
            INSERT INTO pending (user_id, username, name, leader, age, reign,
                gov, gov_sub, religion, rel_sub, expert, region,
                happiness, science, flag_id)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15)
            ON CONFLICT (user_id) DO UPDATE SET
                username=$2, name=$3, leader=$4, age=$5, reign=$6,
                gov=$7, gov_sub=$8, religion=$9, rel_sub=$10,
                expert=$11, region=$12, happiness=$13, science=$14, flag_id=$15
        """, uid, d.get("username"), d.get("name"), d.get("leader"),
            d.get("age"), d.get("reign"), d.get("gov"), d.get("gov_sub"),
            d.get("religion"), d.get("rel_sub"), d.get("expert"),
            d.get("region"), d.get("happiness"), d.get("science"),
            d.get("flag_id"))


async def delete_pending(uid):
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM pending WHERE user_id = $1", uid)


async def save_country(uid, d):
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO countries (user_id, username, name, leader, age, reign,
                gov, gov_sub, religion, rel_sub, expert, region,
                happiness, science, flag_id, status, economy, army, revolt)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,
                    'approved', 500, 100, 5)
            ON CONFLICT (user_id) DO UPDATE SET
                username=$2, name=$3, leader=$4, age=$5, reign=$6,
                gov=$7, gov_sub=$8, religion=$9, rel_sub=$10,
                expert=$11, region=$12, happiness=$13, science=$14,
                flag_id=$15, status='approved'
        """, uid, d.get("username"), d.get("name"), d.get("leader"),
            d.get("age"), d.get("reign"), d.get("gov"), d.get("gov_sub"),
            d.get("religion"), d.get("rel_sub"), d.get("expert"),
            d.get("region"), d.get("happiness"), d.get("science"),
            d.get("flag_id"))
    await init_stats(uid, d)


async def init_stats(uid, d):
    g = GOV_GDP_COEF.get(d.get("gov_sub", ""), 1.0)
    r = RELIGION_COEF.get(d.get("religion", ""), 1.0)
    e = EXPERT_GDP_COEF.get(d.get("expert", ""), 1.0)
    rg = REGION_COEF.get(d.get("region", ""), 1.0)
    gdp = int(BASE_GDP * g * r * e * rg)
    mil = int(5 * GOV_MIL_COEF.get(d.get("gov_sub", ""), 1.0))
    if mil > 20:
        mil = 20
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO country_stats (user_id, gdp, treasury, population,
                tax_rate, military_budget, research_budget, education_budget,
                infrastructure_budget, welfare_budget)
            VALUES ($1, $2, $3, $4, 25, $5, 3, 3, 5, 10)
            ON CONFLICT (user_id) DO UPDATE SET
                gdp=$2, treasury=$3, population=$4, tax_rate=25,
                military_budget=$5, research_budget=3,
                education_budget=3, infrastructure_budget=5, welfare_budget=10
        """, uid, gdp, BASE_TREASURY, BASE_POPULATION, mil)
        await conn.execute(
            "INSERT INTO country_resources (user_id) VALUES ($1) ON CONFLICT DO NOTHING", uid
        )
        await conn.execute(
            "INSERT INTO resource_capacities (user_id) VALUES ($1) ON CONFLICT DO NOTHING", uid
        )
    await calc_army(uid)


async def set_status(uid, status, reason=None):
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE countries SET status=$1, ban_reason=$2 WHERE user_id=$3",
            status, reason, uid
        )


async def delete_country(uid):
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM region_buildings WHERE region_id IN (SELECT id FROM country_regions WHERE user_id=$1)", uid)
        await conn.execute("DELETE FROM country_regions WHERE user_id=$1", uid)
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


async def get_taken_regions():
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT code, user_id FROM regions")
        return {r["code"]: r["user_id"] for r in rows}


async def take_region(code, uid):
    async with pool.acquire() as conn:
        try:
            await conn.execute(
                "INSERT INTO regions (code, user_id) VALUES ($1, $2)", code, uid
            )
            return True
        except asyncpg.UniqueViolationError:
            return False


async def free_region(code):
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM regions WHERE code=$1", code)


async def add_spam_ban(uid):
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO spam_banned (user_id) VALUES ($1) ON CONFLICT DO NOTHING", uid
        )


async def remove_spam_ban(uid):
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM spam_banned WHERE user_id=$1", uid)


async def get_game_date():
    async with pool.acquire() as conn:
        r = await conn.fetchrow(
            "SELECT current_year, current_month, total_turns FROM game_state WHERE id=1"
        )
        if not r:
            return {"year": 2075, "month": 1, "turns": 0}
        return {"year": r["current_year"], "month": r["current_month"], "turns": r["total_turns"]}


async def get_stats(uid):
    async with pool.acquire() as conn:
        s = await conn.fetchrow("SELECT * FROM country_stats WHERE user_id=$1", uid)
        if not s:
            await conn.execute("INSERT INTO country_stats (user_id) VALUES ($1)", uid)
            s = await conn.fetchrow("SELECT * FROM country_stats WHERE user_id=$1", uid)
        return dict(s)


async def get_resources(uid):
    async with pool.acquire() as conn:
        r = await conn.fetchrow("SELECT * FROM country_resources WHERE user_id=$1", uid)
        if not r:
            await conn.execute("INSERT INTO country_resources (user_id) VALUES ($1)", uid)
            r = await conn.fetchrow("SELECT * FROM country_resources WHERE user_id=$1", uid)
        return dict(r)


async def calc_army(uid):
    async with pool.acquire() as conn:
        s = await conn.fetchrow(
            "SELECT gdp, population, military_budget FROM country_stats WHERE user_id=$1", uid
        )
        if not s:
            return 0
        pop_cap = int(s["population"] * POP_CAP_RATIO / 1000)
        bud_cap = (s["gdp"] * s["military_budget"] // 100) // SOLDIER_COST
        army = min(pop_cap, bud_cap)
        await conn.execute("UPDATE country_stats SET army=$1 WHERE user_id=$2", army, uid)
        return army


async def get_user_regions(uid):
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM country_regions WHERE user_id=$1 ORDER BY id", uid
        )
        return [dict(r) for r in rows]


async def get_one_region(rid, uid):
    async with pool.acquire() as conn:
        r = await conn.fetchrow(
            "SELECT * FROM country_regions WHERE id=$1 AND user_id=$2", rid, uid
        )
        return dict(r) if r else None


async def set_commands(application):
    cmds = [
        BotCommand("start", "شروع / ثبت کشور"),
        BotCommand("country", "پروفایل کشور"),
        BotCommand("economy", "اقتصاد و مالی"),
        BotCommand("science", "علم و فناوری"),
        BotCommand("date", "تاریخ بازی"),
        BotCommand("regions", "لیست مناطق"),
        BotCommand("newregion", "ساخت منطقه جدید"),
        BotCommand("build", "ساخت ساختمون"),
        BotCommand("resources", "منابع و انبار"),
        BotCommand("admin", "پنل ادمین"),
        BotCommand("cancel", "لغو"),
    ]
    await application.bot.set_my_commands(cmds)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    chat_id = update.effective_chat.id
    if uid in banned_users and uid != ADMIN_ID:
        await context.bot.send_message(chat_id, "🚫 مسدود شده‌اید.")
        return
    if check_spam(uid) and uid != ADMIN_ID:
        await context.bot.send_message(chat_id, "🚫 اسپم! مسدود شدید.")
        await add_spam_ban(uid)
        return
    c = await get_country(uid)
    if c:
        if c["status"] == "approved":
            await context.bot.send_message(chat_id, "✅ کشور شما قبلاً تأیید شده است.")
        elif c["status"] == "banned":
            await context.bot.send_message(chat_id, "🚫 کشور شما مسدود شده است.")
        else:
            await context.bot.send_message(chat_id, "⏳ در حال بررسی ادمین.")
        return
    temp[uid] = {
        "username": update.effective_user.username or update.effective_user.first_name,
        "step": "MENU",
    }
    keyboard = kb([[InlineKeyboardButton("🏛️ ثبت کشور", callback_data="register_country")]])
    await context.bot.send_message(
        chat_id,
        "🌊 *به ناوال لیگ خوش آمدی!*\n\nWelcome to Naval League",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    temp.pop(uid, None)
    await update.message.reply_text("❌ لغو شد.")


async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid != ADMIN_ID:
        return
    temp.pop(uid, None)
    chat_id = update.effective_chat.id
    all_c = await get_all_countries()
    total = len(all_c)
    approved = len([c for c in all_c if c["status"] == "approved"])
    banned = len([c for c in all_c if c["status"] == "banned"])
    pending = len(await get_pending_all())
    text = (
        f"👑 *پنل مدیریت*\n\n"
        f"📊 آمار:\n"
        f"• کل: {total}\n• فعال: {approved}\n"
        f"• مسدود: {banned}\n• در انتظار: {pending}"
    )
    keyboard = kb([
        [InlineKeyboardButton("📋 لیست کشورها", callback_data="adm_list_0")],
        [InlineKeyboardButton("🚫 مسدودها", callback_data="adm_banned_0")],
        [InlineKeyboardButton("⏳ در انتظار", callback_data="adm_pending_0")],
        [InlineKeyboardButton("🗺️ مناطق", callback_data="adm_regions")],
        [InlineKeyboardButton("🛡️ اسپم‌ها", callback_data="adm_spamlist")],
    ])
    await context.bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=keyboard)


async def date_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    gd = await get_game_date()
    text = (
        f"📅 *تاریخ بازی*\n\n"
        f"🗓️ {fmt_date(gd['year'], gd['month'])}\n"
        f"🔄 نوبت: {gd['turns']}\n\n"
        f"⏱️ هر روز واقعی = ۱ ماه بازی\n"
        f"🌍 سال شروع: ۲۰۷۵"
    )
    await context.bot.send_message(chat_id, text, parse_mode="Markdown")


async def country_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    chat_id = update.effective_chat.id
    c = await get_country(uid)
    if not c:
        await context.bot.send_message(chat_id, "❌ هنوز کشوری ثبت نکردی. /start")
        return
    se = "✅" if c["status"] == "approved" else "🚫" if c["status"] == "banned" else "⏳"
    st = "فعال" if c["status"] == "approved" else "مسدود" if c["status"] == "banned" else "در انتظار"
    text = (
        f"🏛️ *کشور {c['name']}*\n"
        f"📌 وضعیت: {se} {st}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 *رهبر*\n   نام: {c['leader']}\n   سن: {c['age']}\n   حکومت: {c['reign']}\n\n"
        f"⚙️ *حکومت*\n   نوع: {c['gov']}\n   نظام: {c['gov_sub']}\n"
        f"   دین: {c['religion']}\n   مذهب: {c['rel_sub']}\n   تخصص: {c['expert']}\n\n"
        f"📍 *موقعیت*\n   منطقه: {c['region']}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"😊 رضایت: {c['happiness']}٪\n"
        f"🔬 علم: {c['science']}\n"
        f"💰 اقتصاد: {c.get('economy', 0)} میلیون\n"
        f"⚠️ شورش: {c.get('revolt', 0)}٪"
    )
    await context.bot.send_message(chat_id, text, parse_mode="Markdown")


async def economy_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    chat_id = update.effective_chat.id
    c = await get_country(uid)
    if not c or c["status"] != "approved":
        await context.bot.send_message(chat_id, "❌ اول تأیید بشو.")
        return
    await calc_army(uid)
    s = await get_stats(uid)
    gdp = s["gdp"]
    tr = s["treasury"]
    tax = s["tax_rate"]
    tax_inc = gdp * tax // 100
    res_inc = gdp * 5 // 100
    total_inc = tax_inc + res_inc
    mil = gdp * s["military_budget"] // 100
    rsc = gdp * s["research_budget"] // 100
    edu = gdp * s["education_budget"] // 100
    inf = gdp * s["infrastructure_budget"] // 100
    wel = gdp * s["welfare_budget"] // 100
    total_cost = mil + rsc + edu + inf + wel
    net = total_inc - total_cost
    pop_cap = int(s["population"] * POP_CAP_RATIO / 1000)
    bud_cap = (gdp * s["military_budget"] // 100) // SOLDIER_COST
    text = (
        f"💰 *اقتصاد {c['name']}*\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📈 GDP: {fmt_money(gdp)}\n"
        f"💵 مالیات ({tax}٪): {fmt_money(tax_inc)}\n"
        f"⛏️ منابع (۵٪): {fmt_money(res_inc)}\n"
        f"💵 *جمع درآمد: {fmt_money(total_inc)}*\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"💸 نظامی: {fmt_money(mil)}\n"
        f"🔬 تحقیق: {fmt_money(rsc)}\n"
        f"🎓 آموزش: {fmt_money(edu)}\n"
        f"🏗️ زیرساخت: {fmt_money(inf)}\n"
        f"🏥 رفاه: {fmt_money(wel)}\n"
        f"💸 *جمع هزینه: {fmt_money(total_cost)}*\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 خزانه: {fmt_money(tr)}\n"
        f"{'✅' if net >= 0 else '❌'} تراز: {fmt_money(abs(net))} {'سود' if net >= 0 else 'ضرر'}\n\n"
        f"📊 *وضعیت*\n"
        f"😊 رضایت: {s['happiness']}٪\n"
        f"🏗️ زیرساخت: {s['infrastructure']}/۱۰۰\n"
        f"⚠️ بیکاری: {s['unemployment']}٪\n\n"
        f"🪖 *نیروی زمینی*\n"
        f"   تعداد: {s['army']:,} هزار\n"
        f"   💸 هزینه: {fmt_money(s['army'] * SOLDIER_COST)}\n"
        f"   🧑 سقف جمعیتی: {pop_cap:,}\n"
        f"   💰 سقف بودجه: {bud_cap:,}"
    )
    await context.bot.send_message(chat_id, text, parse_mode="Markdown")


async def science_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    chat_id = update.effective_chat.id
    c = await get_country(uid)
    if not c or c["status"] != "approved":
        await context.bot.send_message(chat_id, "❌ اول تأیید بشو.")
        return
    s = await get_stats(uid)

    def bar(v):
        f = v // 10
        return "█" * f + "░" * (10 - f)

    text = (
        f"🔬 *علم {c['name']}*\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔬 پایه: {s['science_base']}/۱۰۰\n   {bar(s['science_base'])}\n\n"
        f"⚙️ کاربردی: {s['science_applied']}/۱۰۰\n   {bar(s['science_applied'])}\n\n"
        f"🪖 نظامی: {s['science_military']}/۱۰۰\n   {bar(s['science_military'])}\n\n"
        f"🚀 فضایی: {s['science_space']}/۱۰۰\n   {bar(s['science_space'])}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 بودجه تحقیق: {s['research_budget']}٪\n"
        f"💵 هزینه: {fmt_money(s['gdp'] * s['research_budget'] // 100)}"
    )
    await context.bot.send_message(chat_id, text, parse_mode="Markdown")


async def regions_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    chat_id = update.effective_chat.id
    c = await get_country(uid)
    if not c or c["status"] != "approved":
        await context.bot.send_message(chat_id, "❌ اول تأیید بشو.")
        return
    regions = await get_user_regions(uid)
    if not regions:
        await context.bot.send_message(chat_id, "🗺️ هنوز منطقه‌ای نساختی. /newregion")
        return
    text = f"🗺️ *مناطق {c['name']}*\n\n📊 تعداد: {len(regions)}\n━━━━━━━━━━━━━━━━━━━━━\n\n"
    for r in regions:
        emoji = {"residential": "🏘️", "industrial": "🏭", "agricultural": "🌾",
                 "extractive": "⛽", "mining": "⛏️", "commercial": "🏪"}.get(r["region_type"], "❓")
        sz = REGION_SIZES.get(r["size"], {}).get("name", "?")
        text += (
            f"{emoji} *{r['name']}*\n"
            f"   نوع: {REGION_TYPES.get(r['region_type'], '?')}\n"
            f"   اندازه: {sz}\n"
            f"   ظرفیت: {r['used']}/{r['capacity']}\n"
            f"   📍 {r['region_code']}\n\n"
        )
    text += "🔨 /build برای ساخت"
    await context.bot.send_message(chat_id, text, parse_mode="Markdown")


async def newregion_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    chat_id = update.effective_chat.id
    c = await get_country(uid)
    if not c or c["status"] != "approved":
        await context.bot.send_message(chat_id, "❌ اول تأیید بشو.")
        return
    temp[uid] = {"step": "NEWREG_TYPE"}
    rows = []
    for k, v in REGION_TYPES.items():
        rows.append([InlineKeyboardButton(v, callback_data=f"newreg_type_{k}")])
    rows.append([InlineKeyboardButton("🔙 انصراف", callback_data="newreg_cancel")])
    await context.bot.send_message(
        chat_id, "🏗️ *ساخت منطقه جدید*\n\nنوع منطقه:",
        parse_mode="Markdown", reply_markup=kb(rows),
    )


async def build_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    chat_id = update.effective_chat.id
    c = await get_country(uid)
    if not c or c["status"] != "approved":
        await context.bot.send_message(chat_id, "❌ اول تأیید بشو.")
        return
    regions = await get_user_regions(uid)
    if not regions:
        await context.bot.send_message(chat_id, "❌ هنوز منطقه‌ای نساختی. /newregion")
        return
    rows = []
    for r in regions:
        emoji = {"residential": "🏘️", "industrial": "🏭", "agricultural": "🌾",
                 "extractive": "⛽", "mining": "⛏️", "commercial": "🏪"}.get(r["region_type"], "❓")
        rows.append([InlineKeyboardButton(
            f"{emoji} {r['name']} ({r['used']}/{r['capacity']})",
            callback_data=f"bld_region_{r['id']}"
        )])
    rows.append([InlineKeyboardButton("🔙 انصراف", callback_data="bld_cancel")])
    await context.bot.send_message(
        chat_id, "🔨 *ساخت ساختمون*\n\nکدوم منطقه؟",
        parse_mode="Markdown", reply_markup=kb(rows),
    )


async def resources_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    chat_id = update.effective_chat.id
    c = await get_country(uid)
    if not c or c["status"] != "approved":
        await context.bot.send_message(chat_id, "❌ اول تأیید بشو.")
        return
    res = await get_resources(uid)
    text = f"📦 *منابع {c['name']}*\n\n━━━━━━━━━━━━━━━━━━━━━\n"
    for k, name in RES_NAMES.items():
        text += f"{name}: {res.get(k, 0):,}\n"
    await context.bot.send_message(chat_id, text, parse_mode="Markdown")


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cb = update.callback_query
    data = cb.data
    uid = cb.from_user.id
    chat_id = cb.message.chat.id
    msg_id = cb.message.message_id
    t = temp.get(uid, {})
    await cb.answer()

    async def edit(text, keyboard=None):
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id, message_id=msg_id,
                text=text, parse_mode="Markdown", reply_markup=keyboard,
            )
        except Exception:
            pass

    if data == "adm_panel" and uid == ADMIN_ID:
        all_c = await get_all_countries()
        text = (
            f"👑 *پنل مدیریت*\n\n"
            f"📊 کل: {len(all_c)} | "
            f"فعال: {len([c for c in all_c if c['status']=='approved'])} | "
            f"مسدود: {len([c for c in all_c if c['status']=='banned'])} | "
            f"در انتظار: {len(await get_pending_all())}"
        )
        keyboard = kb([
            [InlineKeyboardButton("📋 لیست", callback_data="adm_list_0")],
            [InlineKeyboardButton("🚫 مسدودها", callback_data="adm_banned_0")],
            [InlineKeyboardButton("⏳ در انتظار", callback_data="adm_pending_0")],
            [InlineKeyboardButton("🗺️ مناطق", callback_data="adm_regions")],
            [InlineKeyboardButton("🛡️ اسپم", callback_data="adm_spamlist")],
        ])
        await edit(text, keyboard)
        return

    if data == "adm_spamlist" and uid == ADMIN_ID:
        if not banned_users:
            await edit("🛡️ خالی.", kb([[InlineKeyboardButton("🔙", callback_data="adm_panel")]]))
            return
        text = "🛡️ *مسدودها:*\n\n"
        btns = []
        for b in banned_users:
            text += f"🆔 `{b}`\n"
            btns.append([InlineKeyboardButton(f"✅ {b}", callback_data=f"adm_unspam_{b}")])
        btns.append([InlineKeyboardButton("🔙", callback_data="adm_panel")])
        await edit(text, kb(btns))
        return

    if data.startswith("adm_unspam_") and uid == ADMIN_ID:
        try:
            tt = int(data.replace("adm_unspam_", ""))
        except ValueError:
            return
        banned_users.discard(tt)
        spam_tracker.pop(tt, None)
        await remove_spam_ban(tt)
        await edit("✅ رفع شد.", kb([[InlineKeyboardButton("🔙", callback_data="adm_spamlist")]]))
        return

    if data.startswith("adm_list_") and uid == ADMIN_ID:
        try:
            p = int(data.replace("adm_list_", ""))
        except ValueError:
            p = 0
        await show_country_list(chat_id, msg_id, context, p, "all")
        return

    if data.startswith("adm_banned_") and uid == ADMIN_ID:
        try:
            p = int(data.replace("adm_banned_", ""))
        except ValueError:
            p = 0
        await show_country_list(chat_id, msg_id, context, p, "banned")
        return

    if data == "adm_pending_0" and uid == ADMIN_ID:
        pl = await get_pending_all()
        if not pl:
            await edit("⏳ خالی.", kb([[InlineKeyboardButton("🔙", callback_data="adm_panel")]]))
            return
        text = "⏳ *در انتظار:*\n\n"
        for d in pl:
            text += f"🏛️ {d['name']} — @{d.get('username', '')}\n"
        await edit(text, kb([[InlineKeyboardButton("🔙", callback_data="adm_panel")]]))
        return

    if data.startswith("adm_view_") and uid == ADMIN_ID:
        try:
            tt = int(data.replace("adm_view_", ""))
        except ValueError:
            return
        await show_country_detail(chat_id, msg_id, context, tt)
        return

    if data.startswith("adm_ban_") and uid == ADMIN_ID:
        try:
            tt = int(data.replace("adm_ban_", ""))
        except ValueError:
            return
        temp[uid] = {"step": "BAN_REASON", "targetUid": tt}
        await edit(f"📝 دلیل:\n\n🆔 `{tt}`",
                   kb([[InlineKeyboardButton("❌ لغو", callback_data=f"adm_view_{tt}")]]))
        return

    if data.startswith("adm_unban_") and uid == ADMIN_ID:
        try:
            tt = int(data.replace("adm_unban_", ""))
        except ValueError:
            return
        await set_status(tt, "approved", None)
        try:
            await context.bot.send_message(tt, "✅ رفع مسدودی!")
        except Exception:
            pass
        await show_country_detail(chat_id, msg_id, context, tt)
        return

    if data.startswith("adm_del_") and uid == ADMIN_ID:
        try:
            tt = int(data.replace("adm_del_", ""))
        except ValueError:
            return
        c = await get_country(tt)
        if c:
            if c.get("region"):
                await free_region(c["region"])
            await delete_country(tt)
            try:
                await context.bot.send_message(tt, f"🗑️ {c['name']} حذف شد.")
            except Exception:
                pass
        await edit("🗑️ حذف شد.", kb([[InlineKeyboardButton("🔙", callback_data="adm_list_0")]]))
        return

    if data.startswith("adm_free_") and uid == ADMIN_ID:
        code = data.replace("adm_free_", "")
        await free_region(code)
        await show_regions_status(chat_id, msg_id, context)
        return

    if data == "adm_regions" and uid == ADMIN_ID:
        await show_regions_status(chat_id, msg_id, context)
        return

    if data == "adm_noop":
        await cb.answer("آزاده ✅")
        return

    if data.startswith("adm_ok_") or data.startswith("adm_no_"):
        if uid != ADMIN_ID:
            return
        action = "ok" if data.startswith("adm_ok_") else "no"
        try:
            tu = int(data.split("_")[2])
        except (IndexError, ValueError):
            return
        d = await get_pending(tu)
        if not d:
            await cb.answer("⚠️ منقضی شده!", show_alert=True)
            return
        oc = cb.message.caption or ""
        if action == "ok":
            ok = await take_region(d["region"], tu)
            if not ok:
                await cb.answer("⚠️ گرفته شد!", show_alert=True)
                return
            await save_country(tu, d)
            await delete_pending(tu)
            temp.pop(tu, None)
            try:
                await context.bot.edit_message_caption(
                    chat_id=chat_id, message_id=msg_id,
                    caption=oc + "\n\n✅ تأیید شد", parse_mode="Markdown",
                )
            except Exception:
                pass
            try:
                await context.bot.send_message(
                    tu, f"🎉 {d['name']} تأیید شد!\n📍 {d['region']}",
                    parse_mode="Markdown",
                )
            except Exception:
                pass
        else:
            await delete_pending(tu)
            temp.pop(tu, None)
            try:
                await context.bot.edit_message_caption(
                    chat_id=chat_id, message_id=msg_id,
                    caption=oc + "\n\n❌ رد شد", parse_mode="Markdown",
                )
            except Exception:
                pass
            try:
                await context.bot.send_message(tu, "❌ رد شد.")
            except Exception:
                pass
        return

    if data == "register_country":
        c = await get_country(uid)
        if c:
            m = "✅ قبلاً ثبت شدی." if c["status"] == "approved" else "🚫 مسدود." if c["status"] == "banned" else "⏳ در انتظار."
            await cb.answer(m, show_alert=True)
            return
        temp[uid] = {"username": cb.from_user.username or cb.from_user.first_name, "step": "NAME"}
        await edit("🏛️ *نام کشور* را بنویس:")
        return

    if data.startswith("reign_"):
        mp = {"reign_5": "۵ سال", "reign_10": "۱۰ سال", "reign_20": "۲۰ سال",
              "reign_30": "۳۰ سال", "reign_life": "مادام‌العمر"}
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
        rows = [[InlineKeyboardButton(v[0], callback_data=f"govsub_{gk}_{k}")]
                for k, v in GOV_SUBS[gk].items()]
        await edit("🏛️ *نظام حکومتی*:", kb(rows))
        return

    if data.startswith("govsub_"):
        parts = data.replace("govsub_", "").split("_")
        gk = parts[0]
        sk = "_".join(parts[1:])
        if gk not in GOV_SUBS or sk not in GOV_SUBS[gk]:
            return
        sub, hap, sci = GOV_SUBS[gk][sk]
        t["gov_sub"] = sub
        t["happiness"] = hap
        t["science"] = sci
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
        rows = [[InlineKeyboardButton(v, callback_data=f"relsub_{rk}_{k}")]
                for k, v in REL_SUBS[rk].items()]
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
        t["step"] = "REGION"
        temp[uid] = t
        taken = await get_taken_regions()
        rows, row, cnt = [], [], 0
        for code in REGIONS_19:
            if code in taken:
                row.append(InlineKeyboardButton(f"🔒 {code}", callback_data="region_locked"))
            else:
                row.append(InlineKeyboardButton(f"🟢 {code}", callback_data=f"region_{code}"))
            cnt += 1
            if cnt % 3 == 0:
                rows.append(row)
                row = []
        if row:
            rows.append(row)
        await edit("📍 *منطقه*:", kb(rows))
        return

    if data == "region_locked":
        await cb.answer("🔒 گرفته شده!", show_alert=True)
        return

    if data.startswith("region_"):
        code = data.replace("region_", "")
        taken = await get_taken_regions()
        if code in taken:
            await cb.answer("🔒 گرفته شد!", show_alert=True)
            return
        t["region"] = code
        t["step"] = "FLAG"
        temp[uid] = t
        await edit(f"✅ *{code}*.\n\n🖼️ عکس پرچم:")
        return

    if data == "confirm_restart":
        temp.pop(uid, None)
        try:
            await context.bot.edit_message_caption(
                chat_id=chat_id, message_id=msg_id, caption="🔄 پاک شد. /start"
            )
        except Exception:
            pass
        return

    if data == "confirm_yes":
        d = temp.get(uid)
        if not d:
            return
        taken = await get_taken_regions()
        if d.get("region") in taken:
            try:
                await context.bot.edit_message_caption(
                    chat_id=chat_id, message_id=msg_id,
                    caption=f"❌ منطقه {d['region']} گرفته شد.",
                    parse_mode="Markdown",
                )
            except Exception:
                pass
            temp.pop(uid, None)
            return
        at = (
            f"📥 *درخواست ثبت*\n\n"
            f"🏛️ {d['name']}\n👤 {d['leader']}\n🎂 {d['age']}\n"
            f"⏳ {d['reign']}\n⚙️ {d['gov']}\n🏛️ {d['gov_sub']}\n"
            f"☪️ {d['religion']} — {d['rel_sub']}\n🏭 {d['expert']}\n"
            f"📍 {d['region']}\n😊 {d['happiness']}٪\n🔬 {d['science']}\n\n"
            f"👤 @{d.get('username', '')}\n🆔 `{uid}`"
        )
        keyboard = kb([
            [InlineKeyboardButton("✅ تأیید", callback_data=f"adm_ok_{uid}")],
            [InlineKeyboardButton("❌ رد", callback_data=f"adm_no_{uid}")],
        ])
        await save_pending(uid, d)
        await context.bot.send_photo(
            chat_id=ADMIN_ID, photo=d["flag_id"], caption=at,
            parse_mode="Markdown", reply_markup=keyboard,
        )
        try:
            await context.bot.edit_message_caption(
                chat_id=chat_id, message_id=msg_id, caption="⏳ ارسال شد."
            )
        except Exception:
            pass
        return

    if data == "newreg_cancel":
        temp.pop(uid, None)
        await edit("❌ لغو.")
        return

    if data.startswith("newreg_type_"):
        rt = data.replace("newreg_type_", "")
        if rt not in REGION_TYPES:
            return
        t["newreg_type"] = rt
        t["step"] = "NEWREG_CODE"
        temp[uid] = t
        taken = await get_taken_regions()
        rows, row, cnt = [], [], 0
        for code in REGIONS_19:
            if code in taken:
                row.append(InlineKeyboardButton(f"🔒 {code}", callback_data="region_locked"))
            else:
                row.append(InlineKeyboardButton(f"🟢 {code}", callback_data=f"newreg_code_{code}"))
            cnt += 1
            if cnt % 3 == 0:
                rows.append(row)
                row = []
        if row:
            rows.append(row)
        rows.append([InlineKeyboardButton("🔙 انصراف", callback_data="newreg_cancel")])
        await edit(f"📍 موقعیت ({REGION_TYPES[rt]}):", kb(rows))
        return

    if data.startswith("newreg_code_"):
        code = data.replace("newreg_code_", "")
        taken = await get_taken_regions()
        if code in taken:
            await cb.answer("🔒 گرفته شده!", show_alert=True)
            return
        t["newreg_code"] = code
        t["step"] = "NEWREG_NAME"
        temp[uid] = t
        await edit(f"✅ موقعیت: *{code}*\n\n📝 اسم منطقه:")
        return

    if data.startswith("newreg_size_"):
        sz = data.replace("newreg_size_", "")
        if sz not in REGION_SIZES:
            return
        info = REGION_SIZES[sz]
        stats = await get_stats(uid)
        if stats["treasury"] < info["cost"]:
            await cb.answer(f"❌ خزانه کم! نیاز: {fmt_money(info['cost'])}", show_alert=True)
            return
        rt = t.get("newreg_type")
        code = t.get("newreg_code")
        name = t.get("newreg_name")
        if not rt or not code or not name:
            await cb.answer("❌ ناقص!", show_alert=True)
            return
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE country_stats SET treasury = treasury - $1 WHERE user_id = $2",
                info["cost"], uid,
            )
            await conn.execute(
                """INSERT INTO country_regions
                   (user_id, region_code, region_type, name, size, capacity, used)
                   VALUES ($1, $2, $3, $4, $5, $6, 0)""",
                uid, code, rt, name, sz, info["capacity"],
            )
        temp.pop(uid, None)
        await cb.answer("✅ ساخته شد!", show_alert=True)
        await edit(
            f"🎉 *منطقه ساخته شد!*\n\n"
            f"📛 {name}\n🏷️ {REGION_TYPES[rt]}\n"
            f"📐 {info['name']}\n📍 {code}\n"
            f"💰 {fmt_money(info['cost'])}\n"
            f"📦 ظرفیت: {info['capacity']}\n\n"
            f"🔨 /build"
        )
        return

    if data == "bld_cancel":
        temp.pop(uid, None)
        await edit("❌ لغو.")
        return

    if data.startswith("bld_region_"):
        try:
            rid = int(data.replace("bld_region_", ""))
        except ValueError:
            return
        region = await get_one_region(rid, uid)
        if not region:
            await cb.answer("❌ پیدا نشد!", show_alert=True)
            return
        if region["used"] >= region["capacity"]:
            await cb.answer("⚠️ پر شده!", show_alert=True)
            return
        rt = region["region_type"]
        avail = [(k, v) for k, v in BUILDINGS.items() if v["type"] == rt]
        if not avail:
            await cb.answer("⚠️ ساختمونی نیست!", show_alert=True)
            return
        t["selected_region"] = rid
        temp[uid] = t
        rows = []
        for k, v in avail:
            rows.append([InlineKeyboardButton(
                f"{v['name']} — {fmt_money(v['cost'])}",
                callback_data=f"bld_make_{k}",
            )])
        rows.append([InlineKeyboardButton("🔙", callback_data="bld_back")])
        await edit(
            f"🏗️ *ساخت*\n\n📍 {region['name']}\n"
            f"📐 {region['used']}/{region['capacity']}\n\nکدوم؟",
            kb(rows),
        )
        return

    if data == "bld_back":
        await build_cmd(update, context)
        return

    if data.startswith("bld_make_"):
        bk = data.replace("bld_make_", "")
        if bk not in BUILDINGS:
            await cb.answer("❌ نامعتبر!", show_alert=True)
            return
        rid = t.get("selected_region")
        if not rid:
            await cb.answer("❌ اول منطقه!", show_alert=True)
            return
        b = BUILDINGS[bk]
        region = await get_one_region(rid, uid)
        if not region:
            await cb.answer("❌ پیدا نشد!", show_alert=True)
            return
        if region["used"] >= region["capacity"]:
            await cb.answer("⚠️ پر شده!", show_alert=True)
            return
        if b["type"] != region["region_type"]:
            await cb.answer("⚠️ نوع سازگار نیست!", show_alert=True)
            return
        stats = await get_stats(uid)
        if stats["treasury"] < b["cost"]:
            await cb.answer(f"❌ نیاز: {fmt_money(b['cost'])}", show_alert=True)
            return
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE country_stats SET treasury = treasury - $1 WHERE user_id = $2",
                b["cost"], uid,
            )
            await conn.execute(
                "INSERT INTO region_buildings (region_id, building_key) VALUES ($1, $2)",
                rid, bk,
            )
            await conn.execute(
                "UPDATE country_regions SET used = used + 1 WHERE id = $1", rid
            )
        await cb.answer(f"✅ {b['name']} ساخته شد!", show_alert=True)
        region = await get_one_region(rid, uid)
        rt = region["region_type"]
        avail = [(k, v) for k, v in BUILDINGS.items() if v["type"] == rt]
        rows = []
        for k, v in avail:
            rows.append([InlineKeyboardButton(
                f"{v['name']} — {fmt_money(v['cost'])}",
                callback_data=f"bld_make_{k}",
            )])
        rows.append([InlineKeyboardButton("🔙", callback_data="bld_back")])
        await edit(
            f"🏗️ *ساخت*\n\n📍 {region['name']}\n"
            f"📐 {region['used']}/{region['capacity']}\n"
            f"✅ ساخته شد!\n\nیکی دیگه؟",
            kb(rows),
        )
        return


async def show_country_list(chat_id, msg_id, context, page, status):
    per = 5
    off = page * per
    if status == "banned":
        al = await get_banned()
    else:
        al = await get_all_countries()
    pl = al[off:off + per]
    if not pl:
        text = "🚫 خالی." if status == "banned" else "📋 خالی."
        await context.bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=text)
        return
    text = "🚫 *مسدودها:*\n\n" if status == "banned" else "📋 *کشورها:*\n\n"
    btns = []
    for c in pl:
        ic = "✅" if c["status"] == "approved" else "🚫" if c["status"] == "banned" else "⏳"
        text += f"{ic} *{c['name']}* — {c['gov']}\n📍 {c['region']}\n\n"
        btns.append([InlineKeyboardButton(f"🔍 {c['name']}", callback_data=f"adm_view_{c['user_id']}")])
    pref = "banned" if status == "banned" else "list"
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"adm_{pref}_{page - 1}"))
    nav.append(InlineKeyboardButton("🔙", callback_data="adm_panel"))
    if off + per < len(al):
        nav.append(InlineKeyboardButton("➡️", callback_data=f"adm_{pref}_{page + 1}"))
    btns.append(nav)
    try:
        await context.bot.edit_message_text(
            chat_id=chat_id, message_id=msg_id, text=text,
            parse_mode="Markdown", reply_markup=kb(btns),
        )
    except Exception:
        pass


async def show_country_detail(chat_id, msg_id, context, tu):
    c = await get_country(tu)
    if not c:
        await context.bot.edit_message_text(
            chat_id=chat_id, message_id=msg_id, text="❌ پیدا نشد."
        )
        return
    st = "✅ فعال" if c["status"] == "approved" else "🚫 مسدود" if c["status"] == "banned" else "⏳ در انتظار"
    text = (
        f"🏛️ *{c['name']}*\n\n"
        f"👤 {c['leader']}\n🎂 {c['age']}\n⏳ {c['reign']}\n"
        f"⚙️ {c['gov']}\n🏛️ {c['gov_sub']}\n"
        f"☪️ {c['religion']} — {c['rel_sub']}\n🏭 {c['expert']}\n"
        f"📍 {c['region']}\n😊 {c['happiness']}٪\n🔬 {c['science']}\n"
        f"📌 {st}\n\n👤 @{c.get('username', '')}\n🆔 `{c['user_id']}`"
    )
    btns = []
    if c["status"] == "banned":
        btns.append([InlineKeyboardButton("✅ رفع", callback_data=f"adm_unban_{tu}")])
    else:
        btns.append([InlineKeyboardButton("🚫 مسدود", callback_data=f"adm_ban_{tu}")])
    btns.append([InlineKeyboardButton("🗑️ حذف", callback_data=f"adm_del_{tu}")])
    btns.append([InlineKeyboardButton("🔙", callback_data="adm_list_0")])
    try:
        await context.bot.edit_message_text(
            chat_id=chat_id, message_id=msg_id, text=text,
            parse_mode="Markdown", reply_markup=kb(btns),
        )
    except Exception:
        pass


async def show_regions_status(chat_id, msg_id, context):
    taken = await get_taken_regions()
    text = "🗺️ *مناطق:*\n\n"
    btns, row = [], []
    for code in REGIONS_19:
        if code in taken:
            text += f"🔒 {code}\n"
            row.append(InlineKeyboardButton(f"🔓 {code}", callback_data=f"adm_free_{code}"))
        else:
            text += f"🟢 {code}\n"
            row.append(InlineKeyboardButton(f"🟢 {code}", callback_data="adm_noop"))
        if len(row) == 3:
            btns.append(row)
            row = []
    if row:
        btns.append(row)
    btns.append([InlineKeyboardButton("🔙", callback_data="adm_panel")])
    try:
        await context.bot.edit_message_text(
            chat_id=chat_id, message_id=msg_id, text=text,
            parse_mode="Markdown", reply_markup=kb(btns),
        )
    except Exception:
        pass


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    uid = msg.from_user.id
    text = (msg.text or "").strip()
    chat_id = msg.chat.id
    if uid in banned_users and uid != ADMIN_ID:
        return
    if check_spam(uid) and uid != ADMIN_ID:
        await context.bot.send_message(chat_id, "🚫 اسپم!")
        await add_spam_ban(uid)
        return
    t = temp.get(uid)
    if not t:
        return

    if t.get("step") == "NAME":
        if len(text) < 3 or len(text) > 25:
            await context.bot.send_message(chat_id, "❌ ۳ تا ۲۵ حرف:")
            return
        all_c = await get_all_countries()
        for c in all_c:
            if c["name"] == text:
                await context.bot.send_message(chat_id, "❌ تکراری:")
                return
        t["name"] = text
        t["step"] = "LEADER"
        await context.bot.send_message(chat_id, "👤 *نام رهبر*:", parse_mode="Markdown")
        return

    if t.get("step") == "LEADER":
        if len(text) < 2:
            await context.bot.send_message(chat_id, "❌ کوتاه:")
            return
        t["leader"] = text
        t["step"] = "AGE"
        await context.bot.send_message(chat_id, "🎂 *سن* (۳۵-۴۵):", parse_mode="Markdown")
        return

    if t.get("step") == "AGE":
        if not text.isdigit():
            await context.bot.send_message(chat_id, "❌ عدد:")
            return
        age = int(text)
        if age < 35 or age > 45:
            await context.bot.send_message(chat_id, "❌ ۳۵-۴۵:")
            return
        t["age"] = age
        t["step"] = "REIGN"
        rows = [
            [InlineKeyboardButton("⏳ ۵ سال", callback_data="reign_5")],
            [InlineKeyboardButton("⏳ ۱۰ سال", callback_data="reign_10")],
            [InlineKeyboardButton("⏳ ۲۰ سال", callback_data="reign_20")],
            [InlineKeyboardButton("⏳ ۳۰ سال", callback_data="reign_30")],
            [InlineKeyboardButton("♾️ مادام", callback_data="reign_life")],
        ]
        await context.bot.send_message(
            chat_id, "⏳ *مدت حکومت*:", parse_mode="Markdown", reply_markup=kb(rows)
        )
        return

    if t.get("step") == "NEWREG_NAME":
        if len(text) < 2 or len(text) > 30:
            await context.bot.send_message(chat_id, "❌ ۲ تا ۳۰ حرف:")
            return
        t["newreg_name"] = text
        t["step"] = "NEWREG_SIZE"
        temp[uid] = t
        rows = []
        for k, v in REGION_SIZES.items():
            rows.append([InlineKeyboardButton(
                f"{v['name']} — ظرفیت {v['capacity']} — {fmt_money(v['cost'])}",
                callback_data=f"newreg_size_{k}",
            )])
        rows.append([InlineKeyboardButton("🔙 انصراف", callback_data="newreg_cancel")])
        await context.bot.send_message(
            chat_id, "📐 *اندازه*:", parse_mode="Markdown", reply_markup=kb(rows)
        )
        return

    if t.get("step") == "BAN_REASON" and uid == ADMIN_ID:
        tu = t.get("targetUid")
        await set_status(tu, "banned", text)
        temp.pop(uid, None)
        await context.bot.send_message(chat_id, f"🚫 مسدود شد.\n📝 {text}")
        try:
            await context.bot.send_message(tu, f"🚫 مسدود شدی.\n📝 {text}")
        except Exception:
            pass
        return


async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    uid = msg.from_user.id
    t = temp.get(uid)
    if not t or t.get("step") != "FLAG":
        return
    fid = msg.photo[-1].file_id
    t["flag_id"] = fid
    t["step"] = "CONFIRM"
    text = (
        f"🏛️ {t['name']}\n👤 {t['leader']}\n🎂 {t['age']}\n"
        f"⏳ {t['reign']}\n⚙️ {t['gov']}\n🏛️ {t['gov_sub']}\n"
        f"☪️ {t['religion']} — {t['rel_sub']}\n🏭 {t['expert']}\n"
        f"📍 {t['region']}\n😊 {t['happiness']}٪\n🔬 {t['science']}\n\nدرسته؟"
    )
    rows = [
        [InlineKeyboardButton("✅ ثبت", callback_data="confirm_yes")],
        [InlineKeyboardButton("🔄 مجدد", callback_data="confirm_restart")],
    ]
    await context.bot.send_photo(
        chat_id=msg.chat.id, photo=fid, caption=text,
        parse_mode="Markdown", reply_markup=kb(rows),
    )


async def post_init(application):
    await init_db()
    await set_commands(application)
    print(f"✅ DB ready, pool = {pool is not None}")


def main():
    app = (
        Application.builder()
        .token(TOKEN)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(CommandHandler("date", date_cmd))
    app.add_handler(CommandHandler("economy", economy_cmd))
    app.add_handler(CommandHandler("science", science_cmd))
    app.add_handler(CommandHandler("country", country_cmd))
    app.add_handler(CommandHandler("regions", regions_cmd))
    app.add_handler(CommandHandler("newregion", newregion_cmd))
    app.add_handler(CommandHandler("build", build_cmd))
    app.add_handler(CommandHandler("resources", resources_cmd))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    render_host = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
    if render_host:
        port = int(os.environ.get("PORT", 10000))
        app.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path=TOKEN,
            webhook_url=f"https://{render_host}/{TOKEN}",
            drop_pending_updates=True,
        )
    else:
        app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
