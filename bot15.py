import os
import time
import random
import asyncpg
import asyncio
from aiohttp import web
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

START_YEAR = 2075
BASE_POPULATION = 15_000_000
BASE_GDP = 500_000
BASE_TREASURY = 50_000
SOLDIER_COST = 1500
POPULATION_MILITARY_CAP = 0.02

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
        "mil": ["🔒 دیکتاتوری نظامی", 35, "🪖 زیر نظر حکومت و ارتش"],
        "personal": ["👑 دیکتاتوری فردی", 25, "👤 زیر نظر شخص رهبر"],
    },
    "democracy": {
        "parl": ["📜 دموکراسی پارلمانی", 85, "👥 زیر نظر کل مردم"],
        "pres": ["🗳️ دموکراسی ریاستی", 80, "👥 زیر نظر کل مردم"],
    },
    "religious": {
        "trad": ["🕌 تئوکراسی سنتی", 70, "🕌 زیر نظر روحانیت"],
        "mod": ["⚖️ تئوکراسی میانه‌رو", 80, "🤝 زیر نظر مردم و دین"],
        "mil": ["🛡️ تئوکراسی نظامی-دینی", 55, "🪖 ارتش و روحانیت"],
        "legal": ["📜 تئوکراسی قانون‌گرا", 75, "📜 قانون و مردم"],
        "radical": ["💀 تئوکراسی افراطی", 25, "💀 گروه کوچک قدرت"],
    },
    "monarch": {
        "abs": ["👑 سلطنت مطلقه", 45, "👑 خانواده سلطنتی"],
        "const": ["🏛️ سلطنت مشروطه", 75, "👥 مردم و پادشاه"],
    },
    "communist": {
        "one": ["☭ کمونیسم تک‌حزبی", 60, "☭ حزب واحد"],
    },
    "republic": {
        "sec": ["🏛️ جمهوری سکولار", 80, "👥 کل مردم"],
        "theo": ["⚖️ جمهوری تئوکراتیک", 55, "📖 مردم و روحانیت"],
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
    "christ": {
        "cath": "⛪ کاتولیک",
        "orth": "🏛️ ارتدوکس",
        "prot": "📖 پروتستان",
    },
    "jew": {
        "orth": "✡️ ارتدوکس",
        "cons": "🕎 محافظه‌کار",
        "ref": "📜 اصلاح‌طلب",
    },
    "budd": {
        "thera": "🟡 تراوادا",
        "maha": "🔴 ماهایانا",
        "vajra": "⚫ وجریانا",
    },
}

EXPERTS = {
    "heavy": "🏭 صنایع سنگین",
    "energy": "⛽ سوخت و انرژی",
    "grain": "🌾 غلات و کشاورزی",
    "military": "🔫 صنایع نظامی",
}

GOV_GDP_COEF = {
    "دموکراسی پارلمانی": 1.3,
    "دموکراسی ریاستی": 1.2,
    "جمهوری سکولار": 1.2,
    "سلطنت مشروطه": 1.1,
    "جمهوری تئوکراتیک": 1.0,
    "سلطنت مطلقه": 0.9,
    "تئوکراسی میانه‌رو": 0.8,
    "تئوکراسی قانون‌گرا": 0.8,
    "کمونیسم تک‌حزبی": 0.8,
    "تئوکراسی نظامی-دینی": 0.8,
    "دیکتاتوری نظامی": 0.8,
    "دیکتاتوری فردی": 0.7,
    "تئوکراسی افراطی": 0.5,
}

GOV_MIL_COEF = {
    "دیکتاتوری نظامی": 2.0,
    "تئوکراسی نظامی-دینی": 1.8,
    "تئوکراسی افراطی": 1.7,
    "دیکتاتوری فردی": 1.5,
    "کمونیسم تک‌حزبی": 1.4,
    "سلطنت مطلقه": 1.3,
    "سلطنت مشروطه": 1.0,
    "جمهوری تئوکراتیک": 1.0,
    "تئوکراسی میانه‌رو": 0.9,
    "تئوکراسی قانون‌گرا": 0.9,
    "جمهوری سکولار": 0.8,
    "دموکراسی ریاستی": 0.8,
    "دموکراسی پارلمانی": 0.7,
}

RELIGION_COEF = {
    "سکولار": 1.1,
    "اسلام": 1.0,
    "مسیحیت": 0.95,
    "یهودیت": 1.0,
    "بودیسم": 0.9,
    "هندوئیسم": 0.8,
}

EXPERT_GDP_COEF = {
    "صنایع سنگین": 1.3,
    "سوخت و انرژی": 1.5,
    "غلات و کشاورزی": 1.0,
    "صنایع نظامی": 1.1,
}

REGION_COEF = {
    "III": 1.2, "GGG": 1.1, "YYY": 1.1,
    "OOO": 1.0, "TTT": 1.0, "FFF": 1.0, "SSS": 1.0, "AAA": 1.0,
    "HHH": 1.0, "KKK": 1.0, "LLL": 0.9, "RRR": 0.9,
    "DDD": 0.9, "WWW": 0.9, "QQQ": 0.9,
    "UUU": 1.0, "PPP": 1.0, "EEE": 1.0, "MMM": 1.0,
}

RESOURCE_NAMES = {
    "water": "💧 آب",
    "wheat": "🌾 گندم",
    "iron": "⛏ آهن",
    "titanium": "⚙️ تیتانیوم",
    "gold": "🏵 طلا",
    "oil": "🛢 نفت",
    "power": "⚡️ برق",
    "steel": "🏗 فولاد",
    "yellowcake": "🟡 کیک زرد",
    "uranium": "☢ اورانیوم",
}

RESOURCE_UNITS = {
    "water": "متر مکعب",
    "wheat": "تن",
    "iron": "تن",
    "titanium": "تن",
    "gold": "شمش",
    "oil": "بشکه",
    "power": "واحد",
    "steel": "تن",
    "yellowcake": "واحد",
    "uranium": "گرم",
}

REGION_SIZES = {
    "small": {"name": "کوچک", "capacity": 3, "clear_cost": 500, "foundation_cost": 1000},
    "medium": {"name": "متوسط", "capacity": 6, "clear_cost": 1000, "foundation_cost": 2000},
    "large": {"name": "بزرگ", "capacity": 10, "clear_cost": 2000, "foundation_cost": 4000},
    "huge": {"name": "عظیم", "capacity": 20, "clear_cost": 5000, "foundation_cost": 10000},
}

REGION_TYPES = {
    "residential": {"name": "🏘️ مسکونی"},
    "industrial": {"name": "🏭 صنعتی"},
    "agricultural": {"name": "🌾 کشاورزی"},
    "extractive": {"name": "⛽ استخراجی"},
    "mining": {"name": "⛏️ معدنی"},
    "commercial": {"name": "🏪 تجاری"},
}

BUILDINGS = {
    "park": {"name": "🌳 پارک", "type": "residential", "cost": 500, "workers": 50, "happiness": 0.5},
    "school": {"name": "🏫 مدرسه", "type": "residential", "cost": 1000, "workers": 200, "education": 100},
    "house": {"name": "🏠 خانه", "type": "residential", "cost": 200, "workers": 10, "pop": 100_000},
    "apartment": {"name": "🏢 آپارتمان", "type": "residential", "cost": 1500, "workers": 50, "pop": 500_000, "happiness": 0.3},
    "hospital": {"name": "🏥 بیمارستان", "type": "residential", "cost": 5000, "workers": 500, "happiness": 2.0},
    "tower": {"name": "🏙️ برج", "type": "residential", "cost": 5000, "workers": 200, "pop": 1_500_000, "happiness": 0.5},
    "skyscraper": {"name": "🌆 آسمان‌خراش", "type": "residential", "cost": 15000, "workers": 800, "pop": 5_000_000, "happiness": 1.0},

    "vocational": {"name": "🔧 هنرستان", "type": "educational", "cost": 4000, "workers": 300},
    "university": {"name": "🎓 دانشگاه", "type": "educational", "cost": 12000, "workers": 1000},
    "research": {"name": "👨‍🔬 پژوهشگاه", "type": "educational", "cost": 25000, "workers": 2500},
    "lab": {"name": "🧪 آزمایشگاه", "type": "educational", "cost": 8000, "workers": 800},

    "small_workshop": {
        "name": "🏭 کارگاه کوچک", "type": "industrial", "cost": 7000, "workers": 100,
        "input": {"oil": 15, "power": 5, "steel": 2}, "income": 1500,
    },
    "medium_factory": {
        "name": "🏭 کارخانه متوسط", "type": "industrial", "cost": 10000, "workers": 200,
        "input": {"oil": 20, "power": 7, "steel": 3}, "income": 2000,
    },
    "big_factory": {
        "name": "🏭 کارخانه بزرگ", "type": "industrial", "cost": 15000, "workers": 350,
        "input": {"oil": 25, "power": 10, "steel": 5}, "income": 6000,
    },
    "huge_factory": {
        "name": "🏭 کارخانه عظیم", "type": "industrial", "cost": 25000, "workers": 600,
        "input": {"oil": 40, "power": 15, "steel": 8}, "income": 23000,
    },
    "oil_refinery": {
        "name": "🛢 پالایشگاه نفت", "type": "industrial", "cost": 5000, "workers": 50,
        "input": {"power": 25, "steel": 1}, "output": {"oil": 250}, "income": 250,
    },
    "power_plant": {
        "name": "⚡️ پالایشگاه برق", "type": "industrial", "cost": 5000, "workers": 80,
        "input": {"oil": 5, "steel": 2}, "output": {"power": 100}, "income": 400,
    },
    "yellowcake_plant": {
        "name": "☢ کارخانه فرآوری اورانیوم", "type": "industrial", "cost": 65000, "workers": 120,
        "input": {"uranium": 400, "oil": 200, "power": 50, "steel": 5},
        "output": {"yellowcake": 1},
    },
    "reactor": {
        "name": "🏭 راکتور اتمی", "type": "industrial", "cost": 35000, "workers": 500,
        "input": {"yellowcake": 1, "steel": 10}, "income": 50000,
    },

    "iron_mine": {
        "name": "⛏ معدن آهن و فولاد", "type": "mining", "cost": 1000, "workers": 45,
        "input": {"power": 500, "oil": 500}, "output": {"iron": 1, "steel": 1},
    },
    "gold_mine": {
        "name": "🏵 معدن طلا", "type": "mining", "cost": 8000, "workers": 50,
        "input": {"oil": 5, "power": 4}, "output": {"gold": 5}, "limit": 10,
    },
    "uranium_mine": {
        "name": "☢ معدن اورانیوم", "type": "mining", "cost": 15000, "workers": 60,
        "input": {"oil": 15, "power": 12}, "output": {"uranium": 200}, "limit": 5,
    },
    "titanium_mine": {
        "name": "⚙️ معدن تیتانیوم", "type": "mining", "cost": 12000, "workers": 55,
        "input": {"oil": 10, "power": 10}, "output": {"titanium": 5}, "limit": 8,
    },

    "wheat_farm": {"name": "🌾 مزرعه گندم", "type": "agricultural", "cost": 1000, "workers": 100, "output": {"wheat": 100}},
    "livestock": {"name": "🐄 دامداری", "type": "agricultural", "cost": 1500, "workers": 150, "output": {"wheat": 150}},
    "fish_farm": {"name": "🐟 مزرعه ماهی", "type": "agricultural", "cost": 2000, "workers": 200, "output": {"wheat": 200}},
    "orchard": {"name": "🌴 باغ میوه", "type": "agricultural", "cost": 1200, "workers": 120, "output": {"wheat": 120}},

    "bazaar": {"name": "🏪 بازار", "type": "commercial", "cost": 2000, "workers": 100, "income": 300},
    "mall": {"name": "🏬 مرکز خرید", "type": "commercial", "cost": 8000, "workers": 300, "income": 1200},
    "bank": {"name": "🏦 بانک", "type": "commercial", "cost": 15000, "workers": 200, "income": 2500},
    "port": {"name": "🚢 بندر", "type": "commercial", "cost": 30000, "workers": 500, "income": 5000, "unlocks_trade": True},
    "railway": {"name": "🛤️ راه‌آهن", "type": "commercial", "cost": 20000, "workers": 400, "income": 3500},
    "airport": {"name": "✈️ فرودگاه", "type": "commercial", "cost": 40000, "workers": 600, "income": 6000},

    "dam": {"name": "🌊 سد", "type": "infrastructure", "cost": 1500, "workers": 20, "input": {"power": 600}, "output": {"water": 120}, "limit": 20},
    "oil_storage": {"name": "🛢 انبار نفت", "type": "infrastructure", "cost": 1000, "workers": 15, "input": {"power": 500}, "capacity": {"oil": 1_000_000}, "limit": 30},
    "warehouse": {"name": "📦 انبار", "type": "infrastructure", "cost": 800, "workers": 10, "capacity": {"steel": 50_000, "iron": 50_000, "wheat": 100_000, "titanium": 20_000}},
}

EXPLORATION_COST = {
    "oil": 5000,
    "gas": 5000,
    "iron": 3000,
    "steel": 3000,
    "titanium": 4000,
    "gold": 5000,
    "uranium": 7000,
}

EXPLORATION_CHANCES = {
    "oil": 0.30,
    "gas": 0.20,
    "iron": 0.40,
    "steel": 0.30,
    "titanium": 0.20,
    "gold": 0.15,
    "uranium": 0.10,
}

temp = {}
spam_tracker = {}
banned_users = set()
spam_limit = 5
spam_window = 10
pool = None


def kb(rows):
    return InlineKeyboardMarkup(rows)


def check_spam(uid: int) -> bool:
    now = time.time()
    if uid not in spam_tracker:
        spam_tracker[uid] = []
    spam_tracker[uid] = [t for t in spam_tracker[uid] if now - t < spam_window]
    spam_tracker[uid].append(now)
    if len(spam_tracker[uid]) > spam_limit:
        banned_users.add(uid)
        return True
    return False


def format_money(amount: int) -> str:
    dollars = amount * 1000
    if dollars >= 1_000_000_000:
        return f"{dollars/1_000_000_000:.2f} میلیارد دلار"
    elif dollars >= 1_000_000:
        return f"{dollars/1_000_000:.1f} میلیون دلار"
    elif dollars >= 1_000:
        return f"{dollars/1_000:.0f} هزار دلار"
    else:
        return f"{dollars:.0f} دلار"


def format_game_date(year: int, month: int) -> str:
    month_names = [
        "فروردین", "اردیبهشت", "خرداد", "تیر",
        "مرداد", "شهریور", "مهر", "آبان",
        "آذر", "دی", "بهمن", "اسفند",
    ]
    return f"{month_names[month-1]} {year}"


async def init_db():
    global pool
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS countries (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                name TEXT,
                leader TEXT,
                age INT,
                reign TEXT,
                gov TEXT,
                gov_sub TEXT,
                religion TEXT,
                rel_sub TEXT,
                expert TEXT,
                region TEXT,
                happiness INT,
                science TEXT,
                flag_id TEXT,
                status TEXT,
                economy INT DEFAULT 500,
                army INT DEFAULT 100,
                revolt INT DEFAULT 5,
                ban_reason TEXT
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS pending (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                name TEXT,
                leader TEXT,
                age INT,
                reign TEXT,
                gov TEXT,
                gov_sub TEXT,
                religion TEXT,
                rel_sub TEXT,
                expert TEXT,
                region TEXT,
                happiness INT,
                science TEXT,
                flag_id TEXT
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS regions (
                code TEXT PRIMARY KEY,
                user_id BIGINT
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS spam_banned (
                user_id BIGINT PRIMARY KEY
            )
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
                unemployment INT DEFAULT 0,
                labor_used INT DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES countries(user_id)
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS country_regions (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                region_code TEXT,
                region_type TEXT,
                name TEXT,
                size TEXT,
                capacity INT,
                used INT DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES countries(user_id)
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS region_buildings (
                id SERIAL PRIMARY KEY,
                region_id INT,
                building_key TEXT,
                active BOOLEAN DEFAULT TRUE,
                lifespan INT DEFAULT NULL,
                FOREIGN KEY (region_id) REFERENCES country_regions(id)
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS country_resources (
                user_id BIGINT PRIMARY KEY,
                water BIGINT DEFAULT 0,
                wheat BIGINT DEFAULT 0,
                iron BIGINT DEFAULT 0,
                titanium BIGINT DEFAULT 0,
                gold BIGINT DEFAULT 0,
                oil BIGINT DEFAULT 0,
                power BIGINT DEFAULT 0,
                steel BIGINT DEFAULT 0,
                yellowcake BIGINT DEFAULT 0,
                uranium BIGINT DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES countries(user_id)
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS resource_capacities (
                user_id BIGINT PRIMARY KEY,
                water BIGINT DEFAULT 1000000,
                wheat BIGINT DEFAULT 100000,
                iron BIGINT DEFAULT 50000,
                titanium BIGINT DEFAULT 20000,
                gold BIGINT DEFAULT 10000,
                oil BIGINT DEFAULT 1000000,
                power BIGINT DEFAULT 500000,
                steel BIGINT DEFAULT 50000,
                yellowcake BIGINT DEFAULT 5000,
                uranium BIGINT DEFAULT 10000,
                FOREIGN KEY (user_id) REFERENCES countries(user_id)
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS exploration (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                resource_type TEXT,
                status TEXT DEFAULT 'searching',
                started_at TIMESTAMP DEFAULT NOW(),
                FOREIGN KEY (user_id) REFERENCES countries(user_id)
            )
        """)

        row = await conn.fetchrow("SELECT * FROM game_state WHERE id = 1")
        if not row:
            await conn.execute("INSERT INTO game_state (id, current_year, current_month) VALUES (1, 2075, 1)")

    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT user_id FROM spam_banned")
        for r in rows:
            banned_users.add(r["user_id"])


async def get_country(uid):
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM countries WHERE user_id = $1", uid)
        return dict(row) if row else None


async def get_pending(uid):
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM pending WHERE user_id = $1", uid)
        return dict(row) if row else None


async def save_pending(uid, data):
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO pending (user_id, username, name, leader, age, reign, gov, gov_sub,
                religion, rel_sub, expert, region, happiness, science, flag_id)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15)
            ON CONFLICT (user_id) DO UPDATE SET
                username=$2, name=$3, leader=$4, age=$5, reign=$6, gov=$7, gov_sub=$8,
                religion=$9, rel_sub=$10, expert=$11, region=$12, happiness=$13,
                science=$14, flag_id=$15
        """, uid, data.get("username"), data.get("name"), data.get("leader"),
            data.get("age"), data.get("reign"), data.get("gov"), data.get("gov_sub"),
            data.get("religion"), data.get("rel_sub"), data.get("expert"),
            data.get("region"), data.get("happiness"), data.get("science"),
            data.get("flag_id"))


async def delete_pending(uid):
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM pending WHERE user_id = $1", uid)


async def save_country(uid, data):
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO countries (user_id, username, name, leader, age, reign, gov, gov_sub,
                religion, rel_sub, expert, region, happiness, science, flag_id, status,
                economy, army, revolt)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,'approved',500,100,5)
            ON CONFLICT (user_id) DO UPDATE SET
                username=$2, name=$3, leader=$4, age=$5, reign=$6, gov=$7, gov_sub=$8,
                religion=$9, rel_sub=$10, expert=$11, region=$12, happiness=$13,
                science=$14, flag_id=$15, status='approved'
        """, uid, data.get("username"), data.get("name"), data.get("leader"),
            data.get("age"), data.get("reign"), data.get("gov"), data.get("gov_sub"),
            data.get("religion"), data.get("rel_sub"), data.get("expert"),
            data.get("region"), data.get("happiness"), data.get("science"),
            data.get("flag_id"))

    await init_country_stats_for(uid, data)


async def init_country_stats_for(uid, data):
    gov_sub_name = data.get("gov_sub", "")
    religion_name = data.get("religion", "")
    expert_name = data.get("expert", "")
    region = data.get("region", "")

    gdp_coef = GOV_GDP_COEF.get(gov_sub_name, 1.0)
    rel_coef = RELIGION_COEF.get(religion_name, 1.0)
    exp_coef = EXPERT_GDP_COEF.get(expert_name, 1.0)
    reg_coef = REGION_COEF.get(region, 1.0)

    gdp = int(BASE_GDP * gdp_coef * rel_coef * exp_coef * reg_coef)
    mil_coef = GOV_MIL_COEF.get(gov_sub_name, 1.0)
    military_budget_pct = int(5 * mil_coef)
    if military_budget_pct > 20:
        military_budget_pct = 20

    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO country_stats (
                user_id, gdp, treasury, population, tax_rate,
                military_budget, research_budget, education_budget,
                infrastructure_budget, welfare_budget
            )
            VALUES ($1, $2, $3, $4, 25, $5, 3, 3, 5, 10)
            ON CONFLICT (user_id) DO UPDATE SET
                gdp = $2, treasury = $3, population = $4, tax_rate = 25,
                military_budget = $5, research_budget = 3,
                education_budget = 3, infrastructure_budget = 5, welfare_budget = 10
        """, uid, gdp, BASE_TREASURY, BASE_POPULATION, military_budget_pct)

        await conn.execute("""
            INSERT INTO country_resources (user_id) VALUES ($1)
            ON CONFLICT (user_id) DO NOTHING
        """, uid)

        await conn.execute("""
            INSERT INTO resource_capacities (user_id) VALUES ($1)
            ON CONFLICT (user_id) DO NOTHING
        """, uid)

    await calculate_army_for(uid)

async def set_country_status(uid, status, ban_reason=None):
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE countries SET status=$1, ban_reason=$2 WHERE user_id=$3",
            status, ban_reason, uid
        )


async def delete_country(uid):
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM region_buildings WHERE region_id IN (SELECT id FROM country_regions WHERE user_id = $1)", uid)
        await conn.execute("DELETE FROM country_regions WHERE user_id = $1", uid)
        await conn.execute("DELETE FROM country_resources WHERE user_id = $1", uid)
        await conn.execute("DELETE FROM resource_capacities WHERE user_id = $1", uid)
        await conn.execute("DELETE FROM exploration WHERE user_id = $1", uid)
        await conn.execute("DELETE FROM country_stats WHERE user_id = $1", uid)
        await conn.execute("DELETE FROM pending WHERE user_id = $1", uid)
        await conn.execute("DELETE FROM countries WHERE user_id = $1", uid)


async def get_all_countries():
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM countries ORDER BY user_id DESC")
        return [dict(r) for r in rows]


async def get_banned_countries():
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM countries WHERE status='banned' ORDER BY user_id DESC")
        return [dict(r) for r in rows]


async def get_pending_all():
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM pending")
        return [dict(r) for r in rows]


async def get_regions():
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
        await conn.execute("DELETE FROM regions WHERE code = $1", code)


async def add_spam_ban(uid):
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO spam_banned (user_id) VALUES ($1) ON CONFLICT DO NOTHING", uid
        )


async def remove_spam_ban(uid):
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM spam_banned WHERE user_id = $1", uid)


async def get_game_date():
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT current_year, current_month, total_turns FROM game_state WHERE id = 1"
        )
        if not row:
            return {"year": 2075, "month": 1, "turns": 0}
        return {
            "year": row["current_year"],
            "month": row["current_month"],
            "turns": row["total_turns"],
        }


async def advance_game_time():
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT current_year, current_month, total_turns FROM game_state WHERE id = 1"
        )
        year = row["current_year"]
        month = row["current_month"]
        turns = row["total_turns"] + 1

        month += 1
        if month > 12:
            month = 1
            year += 1

        await conn.execute(
            """UPDATE game_state 
               SET current_year = $1, current_month = $2, 
                   total_turns = $3, last_update = NOW()
               WHERE id = 1""",
            year, month, turns,
        )


async def get_stats(uid):
    async with pool.acquire() as conn:
        stats = await conn.fetchrow(
            "SELECT * FROM country_stats WHERE user_id = $1", uid
        )
        if not stats:
            await conn.execute(
                "INSERT INTO country_stats (user_id) VALUES ($1)", uid
            )
            stats = await conn.fetchrow(
                "SELECT * FROM country_stats WHERE user_id = $1", uid
            )
        return dict(stats)


async def get_resources(uid):
    async with pool.acquire() as conn:
        res = await conn.fetchrow(
            "SELECT * FROM country_resources WHERE user_id = $1", uid
        )
        if not res:
            await conn.execute(
                "INSERT INTO country_resources (user_id) VALUES ($1)", uid
            )
            res = await conn.fetchrow(
                "SELECT * FROM country_resources WHERE user_id = $1", uid
            )
        return dict(res)


async def get_capacities(uid):
    async with pool.acquire() as conn:
        cap = await conn.fetchrow(
            "SELECT * FROM resource_capacities WHERE user_id = $1", uid
        )
        if not cap:
            await conn.execute(
                "INSERT INTO resource_capacities (user_id) VALUES ($1)", uid
            )
            cap = await conn.fetchrow(
                "SELECT * FROM resource_capacities WHERE user_id = $1", uid
            )
        return dict(cap)


async def calculate_army_for(uid):
    async with pool.acquire() as conn:
        stats = await conn.fetchrow(
            "SELECT gdp, population, military_budget FROM country_stats WHERE user_id = $1",
            uid
        )
        if not stats:
            return 0

        gdp = stats["gdp"]
        population = stats["population"]
        mil_pct = stats["military_budget"]

        pop_cap = int(population * POPULATION_MILITARY_CAP / 1000)
        mil_budget = gdp * mil_pct // 100
        budget_cap = mil_budget // SOLDIER_COST
        army = min(pop_cap, budget_cap)

        await conn.execute(
            "UPDATE country_stats SET army = $1 WHERE user_id = $2",
            army, uid
        )
        return army


async def get_user_regions(uid):
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM country_regions WHERE user_id = $1 ORDER BY id", uid
        )
        return [dict(r) for r in rows]


async def get_region(region_id, uid):
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM country_regions WHERE id = $1 AND user_id = $2",
            region_id, uid
        )
        return dict(row) if row else None


async def get_region_buildings(region_id):
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM region_buildings WHERE region_id = $1", region_id
        )
        return [dict(r) for r in rows]


async def set_bot_commands(application):
    commands = [
        BotCommand("start", "شروع بازی و ثبت کشور"),
        BotCommand("country", "نمایش وضعیت کامل کشور"),
        BotCommand("economy", "وضعیت اقتصادی و مالی"),
        BotCommand("science", "وضعیت علمی و فناوری"),
        BotCommand("date", "تاریخ جاری بازی"),
        BotCommand("regions", "لیست مناطق کشور"),
        BotCommand("newregion", "ساخت منطقه جدید"),
        BotCommand("build", "ساخت ساختمون در منطقه"),
        BotCommand("resources", "وضعیت منابع و انبارها"),
        BotCommand("admin", "پنل مدیریت (فقط ادمین)"),
        BotCommand("cancel", "لغو عملیات جاری"),
    ]
    await application.bot.set_my_commands(commands)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    chat_id = update.effective_chat.id

    if uid in banned_users and uid != ADMIN_ID:
        await context.bot.send_message(chat_id, "🚫 شما به دلیل اسپم مسدود شده‌اید.")
        return

    if check_spam(uid) and uid != ADMIN_ID:
        await context.bot.send_message(chat_id, "🚫 اسپم! شما مسدود شدید.")
        await add_spam_ban(uid)
        return

    c = await get_country(uid)
    if c:
        if c["status"] == "approved":
            await context.bot.send_message(chat_id, "✅ کشور شما قبلاً تأیید شده است.")
        elif c["status"] == "banned":
            await context.bot.send_message(chat_id, "🚫 کشور شما توسط ادمین مسدود شده است.")
        else:
            await context.bot.send_message(chat_id, "⏳ درخواست شما در حال بررسی ادمین است.")
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
    pending_list = await get_pending_all()
    pending = len(pending_list)

    text = (
        f"👑 *پنل مدیریت ناوال لیگ*\n\n"
        f"📊 آمار کلی:\n"
        f"• کل کشورها: {total}\n"
        f"• فعال: {approved}\n"
        f"• مسدود: {banned}\n"
        f"• در انتظار تأیید: {pending}\n\n"
        f"یکی از گزینه‌ها را انتخاب کن:"
    )

    keyboard = kb([
        [InlineKeyboardButton("📋 لیست کشورها", callback_data="adm_list_0")],
        [InlineKeyboardButton("🚫 لیست مسدودها", callback_data="adm_banned_0")],
        [InlineKeyboardButton("⏳ درخواست‌های در انتظار", callback_data="adm_pending_0")],
        [InlineKeyboardButton("🗺️ وضعیت مناطق", callback_data="adm_regions")],
        [InlineKeyboardButton("🛡️ لیست مسدودهای اسپم", callback_data="adm_spamlist")],
    ])

    await context.bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=keyboard)


async def date_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    gd = await get_game_date()
    text = (
        f"📅 *تاریخ بازی*\n\n"
        f"🗓️ {format_game_date(gd['year'], gd['month'])}\n"
        f"🔄 تعداد نوبت‌ها: {gd['turns']}\n\n"
        f"⏱️ هر روز واقعی = ۱ ماه بازی\n"
        f"🌍 سال شروع: ۲۰۷۵"
    )
    await context.bot.send_message(chat_id, text, parse_mode="Markdown")


async def country_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    chat_id = update.effective_chat.id

    c = await get_country(uid)
    if not c:
        await context.bot.send_message(chat_id, "❌ هنوز کشوری ثبت نکردی. /start رو بزن.")
        return

    status_emoji = "✅" if c["status"] == "approved" else "🚫" if c["status"] == "banned" else "⏳"
    status_text = "فعال" if c["status"] == "approved" else "مسدود" if c["status"] == "banned" else "در انتظار تأیید"

    text = (
        f"🏛️ *کشور {c['name']}*\n"
        f"📌 وضعیت: {status_emoji} {status_text}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 *رهبر*\n"
        f"   نام: {c['leader']}\n"
        f"   سن: {c['age']} سال\n"
        f"   مدت حکومت: {c['reign']}\n\n"
        f"⚙️ *حکومت*\n"
        f"   نوع: {c['gov']}\n"
        f"   نظام: {c['gov_sub']}\n"
        f"   دین: {c['religion']}\n"
        f"   مذهب: {c['rel_sub']}\n"
        f"   تخصص: {c['expert']}\n\n"
        f"📍 *موقعیت*\n"
        f"   منطقه: {c['region']}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"😊 رضایت مردمی: {c['happiness']}٪\n"
        f"🔬 علم: {c['science']}\n"
        f"💰 اقتصاد: {c.get('economy', 0)} میلیون دلار\n"
        f"⚠️ شورش: {c.get('revolt', 0)}٪"
    )

    await context.bot.send_message(chat_id, text, parse_mode="Markdown")


async def economy_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    chat_id = update.effective_chat.id

    c = await get_country(uid)
    if not c or c["status"] != "approved":
        await context.bot.send_message(chat_id, "❌ اول باید کشورت تأیید بشه.")
        return

    await calculate_army_for(uid)
    stats = await get_stats(uid)

    gdp = stats["gdp"]
    treasury = stats["treasury"]
    tax = stats["tax_rate"]

    tax_income = gdp * tax // 100
    resource_income = gdp * 5 // 100
    total_income = tax_income + resource_income

    military_cost = gdp * stats["military_budget"] // 100
    research_cost = gdp * stats["research_budget"] // 100
    edu_cost = gdp * stats["education_budget"] // 100
    infra_cost = gdp * stats["infrastructure_budget"] // 100
    welfare_cost = gdp * stats["welfare_budget"] // 100
    total_cost = military_cost + research_cost + edu_cost + infra_cost + welfare_cost

    net = total_income - total_cost

    pop_cap = int(stats["population"] * POPULATION_MILITARY_CAP / 1000)
    budget_cap = (gdp * stats["military_budget"] // 100) // SOLDIER_COST

    text = (
        f"💰 *اقتصاد کشور {c['name']}*\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📈 GDP: {format_money(gdp)}\n"
        f"💵 درآمد مالیات ({tax}٪): {format_money(tax_income)}\n"
        f"⛏️ درآمد منابع (۵٪): {format_money(resource_income)}\n"
        f"💵 *جمع درآمد: {format_money(total_income)}*\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"💸 هزینه نظامی ({stats['military_budget']}٪): {format_money(military_cost)}\n"
        f"🔬 هزینه تحقیق ({stats['research_budget']}٪): {format_money(research_cost)}\n"
        f"🎓 هزینه آموزش ({stats['education_budget']}٪): {format_money(edu_cost)}\n"
        f"🏗️ هزینه زیرساخت ({stats['infrastructure_budget']}٪): {format_money(infra_cost)}\n"
        f"🏥 هزینه رفاه ({stats['welfare_budget']}٪): {format_money(welfare_cost)}\n"
        f"💸 *جمع هزینه: {format_money(total_cost)}*\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 خزانه: {format_money(treasury)}\n"
        f"{'✅' if net >= 0 else '❌'} *تراز نوبت: {format_money(abs(net))} {'سود' if net >= 0 else 'ضرر'}*\n\n"
        f"📊 *وضعیت*\n"
        f"😊 رضایت: {stats['happiness']}٪\n"
        f"🏗️ زیرساخت: {stats['infrastructure']}/۱۰۰\n"
        f"⚠️ بیکاری: {stats['unemployment']}٪\n\n"
        f"🪖 *نیروی زمینی*\n"
        f"   تعداد: {stats['army']:,} هزار سرباز\n"
        f"   💸 هزینه: {format_money(stats['army'] * SOLDIER_COST)}\n"
        f"   🧑 سقف جمعیتی: {pop_cap:,} هزار (۲٪)\n"
        f"   💰 سقف بودجه‌ای: {budget_cap:,} هزار"
    )
    await context.bot.send_message(chat_id, text, parse_mode="Markdown")


async def science_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    chat_id = update.effective_chat.id

    c = await get_country(uid)
    if not c or c["status"] != "approved":
        await context.bot.send_message(chat_id, "❌ اول باید کشورت تأیید بشه.")
        return

    stats = await get_stats(uid)

    sb = stats["science_base"]
    sa = stats["science_applied"]
    sm = stats["science_military"]
    ss = stats["science_space"]

    def bar(val):
        filled = val // 10
        return "█" * filled + "░" * (10 - filled)

    text = (
        f"🔬 *علم کشور {c['name']}*\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔬 علم پایه: {sb}/۱۰۰\n"
        f"   {bar(sb)}\n\n"
        f"⚙️ علم کاربردی: {sa}/۱۰۰\n"
        f"   {bar(sa)}\n\n"
        f"🪖 علم نظامی: {sm}/۱۰۰\n"
        f"   {bar(sm)}\n\n"
        f"🚀 علم فضایی: {ss}/۱۰۰\n"
        f"   {bar(ss)}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 بودجه تحقیق: {stats['research_budget']}٪ GDP\n"
        f"💵 هزینه تحقیق: {format_money(stats['gdp'] * stats['research_budget'] // 100)}"
    )
    await context.bot.send_message(chat_id, text, parse_mode="Markdown")

async def regions_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    chat_id = update.effective_chat.id

    c = await get_country(uid)
    if not c or c["status"] != "approved":
        await context.bot.send_message(chat_id, "❌ اول باید کشورت تأیید بشه.")
        return

    regions = await get_user_regions(uid)

    if not regions:
        await context.bot.send_message(
            chat_id,
            "🗺️ هنوز هیچ منطقه‌ای نساختی.\n\n"
            "برای ساخت منطقه از /newregion استفاده کن.",
            parse_mode="Markdown",
        )
        return

    text = f"🗺️ *مناطق کشور {c['name']}*\n\n📊 تعداد: {len(regions)}\n━━━━━━━━━━━━━━━━━━━━━\n\n"

    for r in regions:
        emoji = {
            "residential": "🏘️", "industrial": "🏭",
            "agricultural": "🌾", "extractive": "⛽",
            "mining": "⛏️", "commercial": "🏪",
        }.get(r["region_type"], "❓")
        size_name = REGION_SIZES.get(r["size"], {}).get("name", "?")
        text += (
            f"{emoji} *{r['name']}*\n"
            f"   نوع: {REGION_TYPES.get(r['region_type'], {}).get('name', '?')}\n"
            f"   اندازه: {size_name}\n"
            f"   ظرفیت: {r['used']}/{r['capacity']}\n"
            f"   📍 موقعیت: {r['region_code']}\n\n"
        )

    text += "━━━━━━━━━━━━━━━━━━━━━\n"
    text += "🔨 ساخت ساختمون: /build"
    await context.bot.send_message(chat_id, text, parse_mode="Markdown")


async def newregion_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    chat_id = update.effective_chat.id

    c = await get_country(uid)
    if not c or c["status"] != "approved":
        await context.bot.send_message(chat_id, "❌ اول باید کشورت تأیید بشه.")
        return

    temp[uid] = {"step": "NEWREGION_TYPE"}
    rows = [
        [InlineKeyboardButton("🏘️ مسکونی", callback_data="newreg_type_residential")],
        [InlineKeyboardButton("🏭 صنعتی", callback_data="newreg_type_industrial")],
        [InlineKeyboardButton("🌾 کشاورزی", callback_data="newreg_type_agricultural")],
        [InlineKeyboardButton("⛽ استخراجی", callback_data="newreg_type_extractive")],
        [InlineKeyboardButton("⛏️ معدنی", callback_data="newreg_type_mining")],
        [InlineKeyboardButton("🏪 تجاری", callback_data="newreg_type_commercial")],
        [InlineKeyboardButton("🔙 انصراف", callback_data="newreg_cancel")],
    ]
    await context.bot.send_message(
        chat_id,
        "🏗️ *ساخت منطقه جدید*\n\n"
        "نوع منطقه رو انتخاب کن:",
        parse_mode="Markdown",
        reply_markup=kb(rows),
    )


async def build_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    chat_id = update.effective_chat.id

    c = await get_country(uid)
    if not c or c["status"] != "approved":
        await context.bot.send_message(chat_id, "❌ اول باید کشورت تأیید بشه.")
        return

    regions = await get_user_regions(uid)

    if not regions:
        await context.bot.send_message(chat_id, "❌ هنوز هیچ منطقه‌ای نساختی. /newregion")
        return

    rows = []
    for r in regions:
        emoji = {
            "residential": "🏘️", "industrial": "🏭",
            "agricultural": "🌾", "extractive": "⛽",
            "mining": "⛏️", "commercial": "🏪",
        }.get(r["region_type"], "❓")
        rows.append([InlineKeyboardButton(
            f"{emoji} {r['name']} ({r['used']}/{r['capacity']})",
            callback_data=f"bld_region_{r['id']}"
        )])

    rows.append([InlineKeyboardButton("🔙 انصراف", callback_data="bld_cancel")])

    await context.bot.send_message(
        chat_id,
        "🔨 *ساخت ساختمون*\n\n🗺️ کدوم منطقه رو انتخاب می‌کنی؟",
        parse_mode="Markdown",
        reply_markup=kb(rows),
    )


async def resources_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    chat_id = update.effective_chat.id

    c = await get_country(uid)
    if not c or c["status"] != "approved":
        await context.bot.send_message(chat_id, "❌ اول باید کشورت تأیید بشه.")
        return

    res = await get_resources(uid)
    cap = await get_capacities(uid)

    def line(key):
        name = RESOURCE_NAMES.get(key, key)
        unit = RESOURCE_UNITS.get(key, "")
        amount = res.get(key, 0)
        capacity = cap.get(key, 0)
        pct = int(amount / capacity * 100) if capacity else 0
        return f"{name}: {amount:,} / {capacity:,} {unit} ({pct}٪)"

    text = (
        f"📦 *منابع کشور {c['name']}*\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"{line('water')}\n"
        f"{line('wheat')}\n"
        f"{line('iron')}\n"
        f"{line('titanium')}\n"
        f"{line('gold')}\n"
        f"{line('oil')}\n"
        f"{line('power')}\n"
        f"{line('steel')}\n"
        f"{line('uranium')}\n"
        f"{line('yellowcake')}\n"
        f"━━━━━━━━━━━━━━━━━━━━━"
    )
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

    # ========== ادمین ==========
    if data == "adm_panel" and uid == ADMIN_ID:
        all_c = await get_all_countries()
        total = len(all_c)
        approved = len([c for c in all_c if c["status"] == "approved"])
        banned = len([c for c in all_c if c["status"] == "banned"])
        pending = len(await get_pending_all())
        text = (
            f"👑 *پنل مدیریت ناوال لیگ*\n\n"
            f"📊 آمار:\n"
            f"• کل: {total}\n"
            f"• فعال: {approved}\n"
            f"• مسدود: {banned}\n"
            f"• در انتظار: {pending}"
        )
        keyboard = kb([
            [InlineKeyboardButton("📋 لیست کشورها", callback_data="adm_list_0")],
            [InlineKeyboardButton("🚫 لیست مسدودها", callback_data="adm_banned_0")],
            [InlineKeyboardButton("⏳ در انتظار", callback_data="adm_pending_0")],
            [InlineKeyboardButton("🗺️ مناطق", callback_data="adm_regions")],
            [InlineKeyboardButton("🛡️ اسپم‌ها", callback_data="adm_spamlist")],
        ])
        await edit(text, keyboard)
        return

    if data == "adm_spamlist" and uid == ADMIN_ID:
        if not banned_users:
            await edit("🛡️ خالی.", kb([[InlineKeyboardButton("🔙 پنل", callback_data="adm_panel")]]))
            return
        text = "🛡️ *مسدودها:*\n\n"
        btns = []
        for b in banned_users:
            text += f"🆔 `{b}`\n"
            btns.append([InlineKeyboardButton(f"✅ رفع {b}", callback_data=f"adm_unspam_{b}")])
        btns.append([InlineKeyboardButton("🔙 پنل", callback_data="adm_panel")])
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
        await edit("✅ رفع شد.", kb([[InlineKeyboardButton("🔙 لیست", callback_data="adm_spamlist")]]))
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
            await edit("⏳ خالیه.", kb([[InlineKeyboardButton("🔙 پنل", callback_data="adm_panel")]]))
            return
        text = "⏳ *در انتظار:*\n\n"
        for d in pl:
            text += f"🏛️ {d['name']} — @{d.get('username', '')}\n"
        await edit(text, kb([[InlineKeyboardButton("🔙 پنل", callback_data="adm_panel")]]))
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
        await edit(f"📝 دلیل:\n\n🆔 `{tt}`", kb([[InlineKeyboardButton("❌ لغو", callback_data=f"adm_view_{tt}")]]))
        return

    if data.startswith("adm_unban_") and uid == ADMIN_ID:
        try:
            tt = int(data.replace("adm_unban_", ""))
        except ValueError:
            return
        await set_country_status(tt, "approved", None)
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
                await context.bot.send_message(tt, f"🗑️ *{c['name']}* حذف شد.", parse_mode="Markdown")
            except Exception:
                pass
        await edit("🗑️ حذف شد.", kb([[InlineKeyboardButton("🔙 لیست", callback_data="adm_list_0")]]))
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
                await cb.answer("⚠️ منطقه گرفته شد!", show_alert=True)
                return
            await save_country(tu, d)
            await delete_pending(tu)
            temp.pop(tu, None)
            try:
                await context.bot.edit_message_caption(chat_id=chat_id, message_id=msg_id, caption=oc + "\n\n✅ *تأیید شد*", parse_mode="Markdown")
            except Exception:
                pass
            try:
                await context.bot.send_message(tu, f"🎉 *{d['name']}* تأیید شد!\n📍 {d['region']}", parse_mode="Markdown")
            except Exception:
                pass
        else:
            await delete_pending(tu)
            temp.pop(tu, None)
            try:
                await context.bot.edit_message_caption(chat_id=chat_id, message_id=msg_id, caption=oc + "\n\n❌ *رد شد*", parse_mode="Markdown")
            except Exception:
                pass
            try:
                await context.bot.send_message(tu, "❌ رد شد.")
            except Exception:
                pass
        return

    # ========== ثبت کشور ==========
    if data == "register_country":
        c = await get_country(uid)
        if c:
            m = ("✅ قبلاً ثبت شدی." if c["status"] == "approved"
                 else "🚫 مسدود." if c["status"] == "banned"
                 else "⏳ در انتظار.")
            await cb.answer(m, show_alert=True)
            return
        temp[uid] = {"username": cb.from_user.username or cb.from_user.first_name, "step": "NAME"}
        await edit("🏛️ *نام کشور* را بنویس:")
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
        t["step"] = "REGION"
        temp[uid] = t
        taken = await get_regions()
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
        taken = await get_regions()
        if code in taken:
            await cb.answer("🔒 گرفته شد!", show_alert=True)
            return
        t["region"] = code
        t["step"] = "FLAG"
        temp[uid] = t
        await edit(f"✅ منطقه *{code}*.\n\n🖼️ عکس پرچم رو بفرست:")
        return

    if data == "confirm_restart":
        temp.pop(uid, None)
        try:
            await context.bot.edit_message_caption(chat_id=chat_id, message_id=msg_id, caption="🔄 پاک شد. /start")
        except Exception:
            pass
        return

    if data == "confirm_yes":
        d = temp.get(uid)
        if not d:
            return
        taken = await get_regions()
        if d.get("region") in taken:
            try:
                await context.bot.edit_message_caption(chat_id=chat_id, message_id=msg_id, caption=f"❌ منطقه *{d['region']}* گرفته شد.", parse_mode="Markdown")
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
        await context.bot.send_photo(chat_id=ADMIN_ID, photo=d["flag_id"], caption=at, parse_mode="Markdown", reply_markup=keyboard)
        try:
            await context.bot.edit_message_caption(chat_id=chat_id, message_id=msg_id, caption="⏳ ارسال شد.")
        except Exception:
            pass
        return

    # ========== مناطق ==========
    if data == "newreg_cancel":
        temp.pop(uid, None)
        await edit("❌ لغو شد.")
        return

    if data.startswith("newreg_type_"):
        rt = data.replace("newreg_type_", "")
        if rt not in REGION_TYPES:
            return
        t["newreg_type"] = rt
        t["step"] = "NEWREGION_CODE"
        temp[uid] = t
        taken = await get_regions()
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
        await edit(f"📍 *موقعیت منطقه* ({REGION_TYPES[rt]['name']}):", kb(rows))
        return

    if data.startswith("newreg_code_"):
        code = data.replace("newreg_code_", "")
        taken = await get_regions()
        if code in taken:
            await cb.answer("🔒 گرفته شده!", show_alert=True)
            return
        t["newreg_code"] = code
        t["step"] = "NEWREGION_NAME"
        temp[uid] = t
        await edit(f"✅ موقعیت: *{code}*\n\n📝 حالا اسم منطقه رو بنویس:")
        return

    if data.startswith("newreg_size_"):
        sz = data.replace("newreg_size_", "")
        if sz not in REGION_SIZES:
            return
        info = REGION_SIZES[sz]
        total_cost = info["clear_cost"] + info["foundation_cost"]
        stats = await get_stats(uid)
        if stats["treasury"] < total_cost:
            await cb.answer(f"❌ خزانه کافی نیست! نیاز: {format_money(total_cost)}", show_alert=True)
            return
        rt = t.get("newreg_type")
        code = t.get("newreg_code")
        name = t.get("newreg_name")
        if not rt or not code or not name:
            await cb.answer("❌ اطلاعات ناقص!", show_alert=True)
            return
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE country_stats SET treasury = treasury - $1 WHERE user_id = $2",
                total_cost, uid
            )
            await conn.execute("""
                INSERT INTO country_regions (user_id, region_code, region_type, name, size, capacity, used)
                VALUES ($1, $2, $3, $4, $5, $6, 0)
            """, uid, code, rt, name, sz, info["capacity"])
        temp.pop(uid, None)
        await cb.answer("✅ منطقه ساخته شد!", show_alert=True)
        await edit(
            f"🎉 *منطقه ساخته شد!*\n\n"
            f"📛 نام: {name}\n"
            f"🏷️ نوع: {REGION_TYPES[rt]['name']}\n"
            f"📐 اندازه: {info['name']}\n"
            f"📍 موقعیت: {code}\n"
            f"💰 هزینه: {format_money(total_cost)}\n"
            f"📦 ظرفیت: {info['capacity']}\n\n"
            f"🔨 برای ساخت ساختمون /build"
        )
        return

    if data == "bld_cancel":
        temp.pop(uid, None)
        await edit("❌ لغو شد.")
        return

    if data.startswith("bld_region_"):
        try:
            rid = int(data.replace("bld_region_", ""))
        except ValueError:
            return
        region = await get_region(rid, uid)
        if not region:
            await cb.answer("❌ پیدا نشد!", show_alert=True)
            return
        if region["used"] >= region["capacity"]:
            await cb.answer("⚠️ پر شده!", show_alert=True)
            return
        rt = region["region_type"]
        available = [(k, v) for k, v in BUILDINGS.items() if v["type"] == rt]
        if not available:
            await cb.answer("⚠️ ساختمونی نیست!", show_alert=True)
            return
        t["selected_region"] = rid
        temp[uid] = t
        rows = []
        for k, v in available:
            rows.append([InlineKeyboardButton(
                f"{v['name']} — {format_money(v['cost'])}",
                callback_data=f"bld_make_{k}"
            )])
        rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="bld_back")])
        await edit(
            f"🏗️ *ساخت ساختمون*\n\n"
            f"📍 {region['name']}\n"
            f"📐 ظرفیت: {region['used']}/{region['capacity']}\n\n"
            f"کدوم ساختمون؟",
            kb(rows)
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
            await cb.answer("❌ اول منطقه انتخاب کن!", show_alert=True)
            return
        b = BUILDINGS[bk]
        region = await get_region(rid, uid)
        if not region:
            await cb.answer("❌ پیدا نشد!", show_alert=True)
            return
        if region["used"] >= region["capacity"]:
            await cb.answer("⚠️ پر شده!", show_alert=True)
            return
        if b["type"] != region["region_type"]:
            await cb.answer("⚠️ نوع ساختمون سازگار نیست!", show_alert=True)
            return
        stats = await get_stats(uid)
        if stats["treasury"] < b["cost"]:
            await cb.answer(f"❌ خزانه کم! نیاز: {format_money(b['cost'])}", show_alert=True)
            return
        async with pool.acquire() as conn:
            await conn.execute("UPDATE country_stats SET treasury = treasury - $1 WHERE user_id = $2", b["cost"], uid)
            await conn.execute("INSERT INTO region_buildings (region_id, building_key) VALUES ($1, $2)", rid, bk)
            await conn.execute("UPDATE country_regions SET used = used + 1 WHERE id = $1", rid)
        await cb.answer(f"✅ {b['name']} ساخته شد!", show_alert=True)
        region = await get_region(rid, uid)
        rt = region["region_type"]
        available = [(k, v) for k, v in BUILDINGS.items() if v["type"] == rt]
        rows = []
        for k, v in available:
            rows.append([InlineKeyboardButton(
                f"{v['name']} — {format_money(v['cost'])}",
                callback_data=f"bld_make_{k}"
            )])
        rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="bld_back")])
        await edit(
            f"🏗️ *ساخت ساختمون*\n\n"
            f"📍 {region['name']}\n"
            f"📐 ظرفیت: {region['used']}/{region['capacity']}\n"
            f"✅ ساخته شد!\n\n"
            f"یکی دیگه؟",
            kb(rows)
        )
        return


async def show_country_list(chat_id, msg_id, context, page, status):
    per_page = 5
    offset = page * per_page
    if status == "banned":
        all_list = await get_banned_countries()
    else:
        all_list = await get_all_countries()
    page_list = all_list[offset:offset + per_page]
    if not page_list:
        text = "🚫 خالی." if status == "banned" else "📋 خالی."
        await context.bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=text)
        return
    text = "🚫 *مسدودها:*\n\n" if status == "banned" else "📋 *کشورها:*\n\n"
    buttons = []
    for c in page_list:
        icon = "✅" if c["status"] == "approved" else "🚫" if c["status"] == "banned" else "⏳"
        text += f"{icon} *{c['name']}* — {c['gov']}\n📍 {c['region']}\n\n"
        buttons.append([InlineKeyboardButton(f"🔍 {c['name']}", callback_data=f"adm_view_{c['user_id']}")])
    prefix = "banned" if status == "banned" else "list"
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"adm_{prefix}_{page - 1}"))
    nav.append(InlineKeyboardButton("🔙 پنل", callback_data="adm_panel"))
    if offset + per_page < len(all_list):
        nav.append(InlineKeyboardButton("➡️", callback_data=f"adm_{prefix}_{page + 1}"))
    buttons.append(nav)
    try:
        await context.bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=text, parse_mode="Markdown", reply_markup=kb(buttons))
    except Exception:
        pass


async def show_country_detail(chat_id, msg_id, context, tu):
    c = await get_country(tu)
    if not c:
        await context.bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text="❌ پیدا نشد.")
        return
    st = "✅ فعال" if c["status"] == "approved" else "🚫 مسدود" if c["status"] == "banned" else "⏳ در انتظار"
    text = (
        f"🏛️ *{c['name']}*\n\n"
        f"👤 {c['leader']}\n🎂 {c['age']}\n⏳ {c['reign']}\n"
        f"⚙️ {c['gov']}\n🏛️ {c['gov_sub']}\n"
        f"☪️ {c['religion']} — {c['rel_sub']}\n🏭 {c['expert']}\n"
        f"📍 {c['region']}\n😊 {c['happiness']}٪\n🔬 {c['science']}\n"
        f"💰 {c.get('economy', 0)}\n🪖 {c.get('army', 0)}\n⚠️ {c.get('revolt', 0)}٪\n"
        f"📌 {st}\n\n👤 @{c.get('username', '')}\n🆔 `{c['user_id']}`"
    )
    buttons = []
    if c["status"] == "banned":
        buttons.append([InlineKeyboardButton("✅ رفع", callback_data=f"adm_unban_{tu}")])
    else:
        buttons.append([InlineKeyboardButton("🚫 مسدود", callback_data=f"adm_ban_{tu}")])
    buttons.append([InlineKeyboardButton("🗑️ حذف", callback_data=f"adm_del_{tu}")])
    buttons.append([InlineKeyboardButton("🔙 لیست", callback_data="adm_list_0")])
    try:
        await context.bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=text, parse_mode="Markdown", reply_markup=kb(buttons))
    except Exception:
        pass


async def show_regions_status(chat_id, msg_id, context):
    taken = await get_regions()
    text = "🗺️ *مناطق:*\n\n"
    buttons, row = [], []
    for code in REGIONS_19:
        if code in taken:
            text += f"🔒 {code}\n"
            row.append(InlineKeyboardButton(f"🔓 {code}", callback_data=f"adm_free_{code}"))
        else:
            text += f"🟢 {code}\n"
            row.append(InlineKeyboardButton(f"🟢 {code}", callback_data="adm_noop"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("🔙 پنل", callback_data="adm_panel")])
    try:
        await context.bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=text, parse_mode="Markdown", reply_markup=kb(buttons))
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
        await context.bot.send_message(chat_id, "⏳ *مدت حکومت*:", parse_mode="Markdown", reply_markup=kb(rows))
        return

    if t.get("step") == "NEWREGION_NAME":
        if len(text) < 2 or len(text) > 30:
            await context.bot.send_message(chat_id, "❌ ۲ تا ۳۰ حرف:")
            return
        t["newreg_name"] = text
        t["step"] = "NEWREGION_SIZE"
        temp[uid] = t
        rows = []
        for k, v in REGION_SIZES.items():
            total = v["clear_cost"] + v["foundation_cost"]
            rows.append([InlineKeyboardButton(
                f"{v['name']} — ظرفیت {v['capacity']} — {format_money(total)}",
                callback_data=f"newreg_size_{k}"
            )])
        rows.append([InlineKeyboardButton("🔙 انصراف", callback_data="newreg_cancel")])
        await context.bot.send_message(chat_id, "📐 *اندازه منطقه*:", parse_mode="Markdown", reply_markup=kb(rows))
        return

    if t.get("step") == "BAN_REASON" and uid == ADMIN_ID:
        tu = t.get("targetUid")
        await set_country_status(tu, "banned", text)
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
        f"🏛️ {t['name']}\n👤 {t['leader']}\n🎂 {t['age']}\n⏳ {t['reign']}\n"
        f"⚙️ {t['gov']}\n🏛️ {t['gov_sub']}\n"
        f"☪️ {t['religion']} — {t['rel_sub']}\n🏭 {t['expert']}\n"
        f"📍 {t['region']}\n😊 {t['happiness']}٪\n🔬 {t['science']}\n\nآیا درسته؟"
    )
    rows = [
        [InlineKeyboardButton("✅ ثبت", callback_data="confirm_yes")],
        [InlineKeyboardButton("🔄 مجدد", callback_data="confirm_restart")],
    ]
    await context.bot.send_photo(chat_id=msg.chat.id, photo=fid, caption=text, parse_mode="Markdown", reply_markup=kb(rows))


async def post_init(application):
    try:
        await init_db()
        print("DB connected")
    except Exception as e:
        print(f"DB ERROR: {e}")
        raise
    try:
        await set_bot_commands(application)
    except Exception as e:
        print(f"Commands error: {e}")


async def health(request):
    return web.Response(text="OK")


async def start_web_server():
    port = int(os.environ.get("PORT", 8443))
    web_app = web.Application()
    web_app.router.add_get("/", health)
    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"✅ Web server started on port {port}")
    return runner

async def health(request):
    return web.Response(text="OK")


async def start_web_server():
    port = int(os.environ.get("PORT", 10000))
    web_app = web.Application()
    web_app.router.add_get("/", health)
    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"✅ Web server started on port {port}")
    return runner


async def run_bot():
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

    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)
    print("✅ Bot polling started")

    await start_web_server()
    await asyncio.Event().wait()


def main():
    asyncio.run(run_bot())


if __name__ == "__main__":
    main()
