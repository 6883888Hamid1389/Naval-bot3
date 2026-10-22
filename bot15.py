import os
import logging
import asyncio
import asyncpg
import httpx
import json
import ast
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand, CallbackQuery
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_ID = 8849773822
DATABASE_URL = os.environ.get("DATABASE_URL", "")
CHANNEL_ID = os.environ.get("CHANNEL_ID", "")
CLOUDFLARE_API_TOKEN = os.environ.get("CLOUDFLARE_API_TOKEN", "")
CLOUDFLARE_ACCOUNT_ID = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")

RESOURCES = {
    "oil": "🛢 نفت خام", "coal": "🪨 زغال سنگ", "iron": "⛏ سنگ آهن", 
    "copper": "🟤 سنگ مس", "titanium": "⚙️ سنگ تیتانیوم", "uranium": "☢ سنگ اورانیوم", 
    "tungsten": "🔫 سنگ تنگستن", "cobalt": "🔋 سنگ کوبالت", "chromium": "✨ سنگ کروم", 
    "rare_earth": "💎 فلزات کمیاب", "steel": "🏗 فولاد", "chemicals": "🧪 مواد شیمیایی",
    "tank_armor": "🛡 آلیاژ زره", "jet_engine": "🚀 سوپرآلیاژ جت", "electronics": "📟 الکترونیک", "ammo": "🔫 مهمات"
}

# --- دیتابیس کامل ۲۲ کشور با آمار و شهرهای دقیق سال ۱۹۷۹ ---
COUNTRY_DB = {
    "آمریکا": {
        "gdp_init": 2627333000000, "mil_budget_init": 548272000000, "jets_init": 4000, "refineries_init": 17050000,
        "cities": "نیویورک، کالیفرنیا، تگزاس، فلوریدا، ایلینوی، پنسیلوانیا، اوهایو، میشیگان، جورجیا، کارولینای شمالی، ویرجینیا، واشنگتن، ماساچوست، ایندیانا، میزوری، تنسی",
        "mines": {"iron_mine": {"name": "معدن آهن میشیگان", "output_res": "iron", "amount": 80000}, "tungsten_mine": {"name": "معدن تنگستن کالیفرنیا", "output_res": "tungsten", "amount": 15000}, "oil_well": {"name": "چاه‌های نفت تگزاس", "output_res": "oil", "amount": 1500000}},
        "factories": {"texas_refinery": {"name": "پالایشگاه تگزاس", "income": 400000, "cost": 800000, "consumes": "oil", "produces": "chemicals"}, "us_steel": {"name": "فولاد آمریکا", "income": 200000, "cost": 450000, "consumes": "iron", "produces": "steel"}, "lockheed_jet": {"name": "خط تولید جت لاکهید", "income": 350000, "cost": 900000, "consumes": "titanium", "produces": "jet_engine"}, "colt_ammo": {"name": "خط تولید مهمات کلت", "income": 150000, "cost": 400000, "consumes": "chemicals", "produces": "ammo"}}
    },
    "شوروی": {
        "gdp_init": 901600000000, "mil_budget_init": 105700000000, "jets_init": 5000, "refineries_init": 12000000,
        "cities": "روسیه (مسکو)، اوکراین (کی‌یف)، بلاروس (مینسک)، ازبکستان، قزاقستان، گرجستان (تفلیس)، آذربایجان (باکو)، لیتوانی، مولداوی، لتونی، قرقیزستان، تاجیکستان، ارمنستان، ترکمنستان، استونی",
        "mines": {"iron_mine": {"name": "معدن آهن کورسک", "output_res": "iron", "amount": 100000}, "uranium_mine": {"name": "معدن اورانیوم قزاقستان", "output_res": "uranium", "amount": 50000}, "cobalt_mine": {"name": "معدن کوبالت سیبری", "output_res": "cobalt", "amount": 20000}, "oil_well": {"name": "چاه‌های نفت باکو", "output_res": "oil", "amount": 1800000}},
        "factories": {"baku_refinery": {"name": "پالایشگاه باکو", "income": 350000, "cost": 700000, "consumes": "oil", "produces": "chemicals"}, "magnitogorsk": {"name": "فولاد مگنیتوگورسک", "income": 250000, "cost": 500000, "consumes": "iron", "produces": "steel"}, "ural_tank": {"name": "خط تولید زره اورال", "income": 300000, "cost": 750000, "consumes": "steel", "produces": "tank_armor"}, "sukhoi_engine": {"name": "خط تولید جت سوخو", "income": 400000, "cost": 950000, "consumes": "cobalt", "produces": "jet_engine"}}
    },
    "ایران": {
        "gdp_init": 90365000000, "mil_budget_init": 4688000000, "jets_init": 450, "refineries_init": 1080000,
        "cities": "تهران، اصفهان، خراسان، فارس، آذربایجان شرقی، آذربایجان غربی، خوزستان، کرمانشاه، گیلان، مازندران، کرمان، یزد، مرکزی، همدان، لرستان، سیستان و بلوچستان، هرمزگان، بوشهر، زنجان، قزوین، قم، سمنان، کهگیلویه و بویراحمد، چهارمحال و بختیاری، ایلام، اردبیل، کردستان",
        "mines": {"iron_mine": {"name": "معدن آهن", "output_res": "iron", "amount": 50000}, "copper_mine": {"name": "معدن مس سرچشمه", "output_res": "copper", "amount": 30000}, "oil_well": {"name": "چاه‌های نفت خوزستان", "output_res": "oil", "amount": 2000000}},
        "factories": {"abadan_refinery": {"name": "پالایشگاه آبادان", "income": 250000, "cost": 500000, "consumes": "oil", "produces": "chemicals"}, "isfahan_steel": {"name": "ذوب آهن اصفهان", "income": 150000, "cost": 350000, "consumes": "iron", "produces": "steel"}, "dio_armor": {"name": "خط تولید زره DIO", "income": 200000, "cost": 600000, "consumes": "steel", "produces": "tank_armor"}}
    },
    "عراق": {
        "gdp_init": 16022000000, "mil_budget_init": 3000000000, "jets_init": 300, "refineries_init": 300000,
        "cities": "بغداد، بصره، موصل (نینوا)، کرکوک (تأمیم)، اربیل، نجف، کربلا، سامرا (صلاح‌الدین)، رمادی (انبار)، فلوجه، دیاله، واسط، میسان، ذی‌قار، بابل، قادسیه، مثنی، کربلا",
        "mines": {"iron_mine": {"name": "معدن آهن بصره", "output_res": "iron", "amount": 20000}, "oil_well": {"name": "چاه‌های نفت کرکوک", "output_res": "oil", "amount": 1200000}},
        "factories": {"baiji_refinery": {"name": "پالایشگاه بیجی", "income": 150000, "cost": 300000, "consumes": "oil", "produces": "chemicals"}, "iraq_military": {"name": "صنایع نظامی عراق", "income": 120000, "cost": 350000, "consumes": "steel", "produces": "ammo"}}
    },
    "انگلیس": {
        "gdp_init": 439012000000, "mil_budget_init": 62680000000, "jets_init": 500, "refineries_init": 2000000,
        "cities": "انگلستان (لندن، منچستر، بیرمنگام، لیورپول)، اسکاتلند (ادینبرو، گلاسکو)، ولز (کاردیف)، ایرلند شمالی (بلفاست)",
        "mines": {"coal_mine": {"name": "معدن زغال سنگ", "output_res": "coal", "amount": 80000}, "oil_well": {"name": "نفت دریای شمال", "output_res": "oil", "amount": 800000}},
        "factories": {"uk_refinery": {"name": "پالایشگاه", "income": 200000, "cost": 400000, "consumes": "oil", "produces": "chemicals"}, "uk_steel": {"name": "فولاد", "income": 150000, "cost": 300000, "consumes": "coal", "produces": "steel"}}
    },
    "فرانسه": {
        "gdp_init": 613971000000, "mil_budget_init": 49682000000, "jets_init": 500, "refineries_init": 3500000,
        "cities": "ایل دو فرانس (پاریس)، پروانس-آلپ-کوت دازور (مارسی، نیس)، اوورنی-رون-آلپ (لیون)، اکسیتانی (تولوز)، نر (لیل)، پیی دو لا لوآر (نانت)، گراند است (استراسبورگ)",
        "mines": {"iron_mine": {"name": "معدن آهن", "output_res": "iron", "amount": 40000}, "uranium_mine": {"name": "معدن اورانیوم", "output_res": "uranium", "amount": 10000}},
        "factories": {"fr_refinery": {"name": "پالایشگاه", "income": 180000, "cost": 400000, "consumes": "oil", "produces": "chemicals"}, "fr_jet": {"name": "خط تولید جت", "income": 250000, "cost": 600000, "consumes": "titanium", "produces": "jet_engine"}}
    },
    "آلمان غربی": {
        "gdp_init": 881309000000, "mil_budget_init": 64008000000, "jets_init": 500, "refineries_init": 3000000,
        "cities": "نوردراین-وستفالن (دوسلدورف، کلن)، بایرن (مونیخ)، بادن-وورتمبرگ (اشتوتگارت)، نیدرزاکسن (هانوفر)، هسن (فرانکفورت)، راینلاند-فالتس، شلسویگ-هولشتاین، هامبورگ، برمن، زارلند، برلین غربی",
        "mines": {"coal_mine": {"name": "معدن زغال سنگ", "output_res": "coal", "amount": 100000}, "iron_mine": {"name": "معدن آهن", "output_res": "iron", "amount": 50000}},
        "factories": {"wg_steel": {"name": "فولاد", "income": 200000, "cost": 450000, "consumes": "iron", "produces": "steel"}, "wg_tank": {"name": "خط تولید تانک", "income": 250000, "cost": 600000, "consumes": "steel", "produces": "tank_armor"}}
    },
    "آلمان شرقی": {
        "gdp_init": 150000000000, "mil_budget_init": 8000000000, "jets_init": 300, "refineries_init": 200000,
        "cities": "برلین شرقی، زاکسن (لایپزیگ، درسدن)، براندنبورگ (پوتسدام)، مکلنبورگ-فورپومرن (روستوک)، تورینگن (ارفورت)، زاکسن-آنهالت (هاله)",
        "mines": {"coal_mine": {"name": "معدن زغال سنگ", "output_res": "coal", "amount": 60000}},
        "factories": {"eg_chem": {"name": "کارخانه شیمیایی", "income": 150000, "cost": 300000, "consumes": "coal", "produces": "chemicals"}}
    },
    "چین": {
        "gdp_init": 263698000000, "mil_budget_init": 40000000000, "jets_init": 5800, "refineries_init": 2000000,
        "cities": "پکن، شانگهای، تیانجین، چونگ‌کینگ، گوانگ‌دونگ (گوانگژو)، سیچوان (چنگدو)، هوبی (ووهان)، شاندونگ (جینان)، جیانگسو (نانجینگ)، ژجیانگ (هانگژو)، هنان (ژنگژو)، هبئی (شیجیاژوانگ)",
        "mines": {"iron_mine": {"name": "معدن آهن", "output_res": "iron", "amount": 90000}, "rare_earth_mine": {"name": "معدن کمیاب", "output_res": "rare_earth", "amount": 30000}},
        "factories": {"cn_steel": {"name": "فولاد", "income": 180000, "cost": 400000, "consumes": "iron", "produces": "steel"}, "cn_ammo": {"name": "مهمات", "income": 120000, "cost": 300000, "consumes": "chemicals", "produces": "ammo"}}
    },
    "ژاپن": {
        "gdp_init": 1055012000000, "mil_budget_init": 21225000000, "jets_init": 300, "refineries_init": 5000000,
        "cities": "توکیو، اوساکا، کاناگاوا (یوکوهاما)، آیچی (ناگویا)، هوکایدو (ساپورو)، فوکوئوکا، کیوتو، هیوگو (کوبه)، هیروشیما",
        "mines": {"coal_mine": {"name": "معدن زغال سنگ", "output_res": "coal", "amount": 20000}, "copper_mine": {"name": "معدن مس", "output_res": "copper", "amount": 15000}},
        "factories": {"jp_electronics": {"name": "الکترونیک", "income": 300000, "cost": 600000, "consumes": "copper", "produces": "electronics"}, "jp_steel": {"name": "فولاد", "income": 200000, "cost": 450000, "consumes": "coal", "produces": "steel"}}
    },
    "عربستان": {
        "gdp_init": 111859000000, "mil_budget_init": 31510000000, "jets_init": 100, "refineries_init": 758000,
        "cities": "ریاض، مکه، مدینه، استان شرقی (دمام، ظهران)، عسیر (ابها)، تبوک، حائل، جیزان، نجران، قصیم (بریده)",
        "mines": {"oil_well": {"name": "چاه‌های نفت", "output_res": "oil", "amount": 3000000}},
        "factories": {"sa_refinery": {"name": "پالایشگاه", "income": 250000, "cost": 500000, "consumes": "oil", "produces": "chemicals"}}
    },
    "اسرائیل": {
        "gdp_init": 21094000000, "mil_budget_init": 13269000000, "jets_init": 400, "refineries_init": 150000,
        "cities": "تل‌آویو، اورشلیم، حیفا، بئرشبع، نتانیا، ریشون لتسیون، پتخ تیکوا، اشدود، رعانانا",
        "mines": {"copper_mine": {"name": "معدن مس", "output_res": "copper", "amount": 10000}},
        "factories": {"il_ammo": {"name": "صنایع نظامی", "income": 150000, "cost": 350000, "consumes": "chemicals", "produces": "ammo"}, "il_electronics": {"name": "الکترونیک", "income": 250000, "cost": 500000, "consumes": "copper", "produces": "electronics"}}
    },
    "مصر": {
        "gdp_init": 15616000000, "mil_budget_init": 3341000000, "jets_init": 300, "refineries_init": 300000,
        "cities": "قاهره، اسکندریه، جیزه، سوئز، پورت سعید، لوکسور، اسوان، اسماعیلیه، منصوره، طنطا، اسيوط",
        "mines": {"iron_mine": {"name": "معدن آهن", "output_res": "iron", "amount": 30000}},
        "factories": {"eg_refinery": {"name": "پالایشگاه", "income": 120000, "cost": 250000, "consumes": "oil", "produces": "chemicals"}}
    },
    "هند": {
        "gdp_init": 152062000000, "mil_budget_init": 11190000000, "jets_init": 600, "refineries_init": 500000,
        "cities": "دهلی نو، مهاراشترا (بمبئی)، بنگال غربی (کلکته)، تامیل نادو (چنای)، کارناتاکا (بنگلور)، گجرات (احمدآباد)، راجستان (جایپور)، اوتار پرادش (لاکنو)، پنجاب (امریتسار)",
        "mines": {"iron_mine": {"name": "معدن آهن", "output_res": "iron", "amount": 60000}, "coal_mine": {"name": "معدن زغال سنگ", "output_res": "coal", "amount": 70000}},
        "factories": {"in_steel": {"name": "فولاد", "income": 150000, "cost": 350000, "consumes": "iron", "produces": "steel"}}
    },
    "پاکستان": {
        "gdp_init": 25798000000, "mil_budget_init": 1979000000, "jets_init": 200, "refineries_init": 100000,
        "cities": "اسلام‌آباد، کراچی (سند)، لاهور (پنجاب)، پیشاور (خیبر پختونخوا)، کویته (بلوچستان)، مولتان، فیصل‌آباد، راولپندی",
        "mines": {"iron_mine": {"name": "معدن آهن", "output_res": "iron", "amount": 20000}},
        "factories": {"pk_ammo": {"name": "مهمات", "income": 100000, "cost": 250000, "consumes": "iron", "produces": "ammo"}}
    },
    "ترکیه": {
        "gdp_init": 126394000000, "mil_budget_init": 4733000000, "jets_init": 300, "refineries_init": 400000,
        "cities": "آنکارا، استانبول، ازمیر، بورسا، آدانا، غازیانتپ، قونیه، مرسین، دیاربکر، ارزروم، ترابزون",
        "mines": {"chromium_mine": {"name": "معدن کروم", "output_res": "chromium", "amount": 40000}, "coal_mine": {"name": "معدن زغال سنگ", "output_res": "coal", "amount": 40000}},
        "factories": {"tr_steel": {"name": "فولاد", "income": 120000, "cost": 250000, "consumes": "coal", "produces": "steel"}}
    },
    "برزیل": {
        "gdp_init": 186976000000, "mil_budget_init": 6811000000, "jets_init": 150, "refineries_init": 1000000,
        "cities": "برازیلیا، سائوپائولو، ریودوژانیرو، میناس گرایس (بلو هوریزونته)، باهیا (سالوادور)، پارانا (کوریتیبا)، پرنامبوکو (رسیفه)، سئارا (فورتالزا)، ریوگرانده دو سول (پورتو آلگره)",
        "mines": {"iron_mine": {"name": "معدن آهن", "output_res": "iron", "amount": 80000}},
        "factories": {"br_steel": {"name": "فولاد", "income": 150000, "cost": 300000, "consumes": "iron", "produces": "steel"}}
    },
    "آرژانتین": {
        "gdp_init": 73916000000, "mil_budget_init": 14098000000, "jets_init": 150, "refineries_init": 600000,
        "cities": "بوئنوس آیرس، کوردوبا، سانتافه (روساریو)، مندوزا، لا پلاتا، توکومان، سالتا",
        "mines": {"copper_mine": {"name": "معدن مس", "output_res": "copper", "amount": 20000}},
        "factories": {"ar_steel": {"name": "فولاد", "income": 100000, "cost": 250000, "consumes": "copper", "produces": "steel"}}
    },
    "کره جنوبی": {
        "gdp_init": 66947000000, "mil_budget_init": 8819000000, "jets_init": 200, "refineries_init": 600000,
        "cities": "سئول، بوسان، اینچئون، دئگو، دائجون، گوانگجو، اولسان، سوون",
        "mines": {"tungsten_mine": {"name": "معدن تنگستن", "output_res": "tungsten", "amount": 15000}},
        "factories": {"kr_steel": {"name": "فولاد", "income": 150000, "cost": 300000, "consumes": "tungsten", "produces": "steel"}, "kr_electronics": {"name": "الکترونیک", "income": 200000, "cost": 400000, "consumes": "copper", "produces": "electronics"}}
    },
    "کره شمالی": {
        "gdp_init": 9490000000, "mil_budget_init": 2000000000, "jets_init": 500, "refineries_init": 50000,
        "cities": "پیونگ‌یانگ، هامهونگ، چونگ‌جین، نامپو، وونسان، کائسونگ",
        "mines": {"coal_mine": {"name": "معدن زغال سنگ", "output_res": "coal", "amount": 50000}, "iron_mine": {"name": "معدن آهن", "output_res": "iron", "amount": 40000}},
        "factories": {"nk_ammo": {"name": "مهمات", "income": 100000, "cost": 200000, "consumes": "coal", "produces": "ammo"}}
    },
    "ویتنام": {
        "gdp_init": 7140000000, "mil_budget_init": 1000000000, "jets_init": 100, "refineries_init": 0,
        "cities": "هانوی، هوشی‌مین (سایگون)، هایفونگ، دانانگ، کان‌تو، هیو",
        "mines": {"coal_mine": {"name": "معدن زغال سنگ", "output_res": "coal", "amount": 30000}},
        "factories": {"vn_ammo": {"name": "مهمات", "income": 80000, "cost": 200000, "consumes": "coal", "produces": "ammo"}}
    },
    "کوبا": {
        "gdp_init": 19584000000, "mil_budget_init": 1500000000, "jets_init": 150, "refineries_init": 100000,
        "cities": "هاوانا، سانتیاگو د کوبا، کاماگوئی، اولگین، سانتا کلارا، گوانتانامو",
        "mines": {"cobalt_mine": {"name": "معدن کوبالت", "output_res": "cobalt", "amount": 15000}},
        "factories": {"cu_refinery": {"name": "پالایشگاه", "income": 80000, "cost": 200000, "consumes": "oil", "produces": "chemicals"}}
    }
}

ALLOWED_COUNTRIES = list(COUNTRY_DB.keys())
pool = None
temp = {}

async def init_db():
    global pool
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS countries (
                user_id BIGINT PRIMARY KEY,
                username TEXT, name TEXT, status TEXT DEFAULT 'pending', 
                gdp BIGINT DEFAULT 500000000, mil_budget BIGINT DEFAULT 35000000, 
                jets INT DEFAULT 0, refineries INT DEFAULT 0,
                army INT DEFAULT 100000, satisfaction INT DEFAULT 50, tax_rate INT DEFAULT 10,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS infrastructure (
                id SERIAL PRIMARY KEY, user_id BIGINT, sector_type TEXT, name TEXT, income BIGINT DEFAULT 0, created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id SERIAL PRIMARY KEY, user_id BIGINT, order_text TEXT, category TEXT, status TEXT DEFAULT 'pending', ai_analysis_raw TEXT, created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        for res in RESOURCES.keys():
            await conn.execute(f"ALTER TABLE countries ADD COLUMN IF NOT EXISTS res_{res} BIGINT DEFAULT 0")
    logger.info("Database initialized (22 Countries, 1979 Historic Stats).")

def kb(rows):
    return InlineKeyboardMarkup(rows)

def fmt_money(dollars):
    try:
        d = int(dollars)
    except:
        return "0 دلار"
    if d >= 1_000_000_000:
        return f"${d/1_000_000_000:.2f} میلیارد دلار"
    if d >= 1_000_000:
        return f"${d/1_000_000:.1f} میلیون دلار"
    if d >= 1_000:
        return f"${d/1_000:.0f} هزار دلار"
    return f"${d:,.0f} دلار"

def _safe_parse_json(raw) -> dict:
    if isinstance(raw, dict):
        return raw
    if not raw or not isinstance(raw, str):
        return {}
    start, end = raw.find('{'), raw.rfind('}')
    if start == -1 or end == -1:
        return {}
    s = raw[start:end + 1].replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(s)
    except:
        pass
    try:
        return ast.literal_eval(s)
    except:
        pass
    try:
        return ast.literal_eval(s.replace("true", "True").replace("false", "False").replace("null", "None"))
    except:
        pass
    return {}

def _clean_persian_text(text: str) -> str:
    if not isinstance(text, str):
        return ""
    return re.sub(r'[^\u0600-\u06FF0-9\s\.\,\!\?\:\-\؛\(\)\[\]\«\»\n]', '', text).strip()

async def ask_ai(prompt: str, system_prompt: str = "You are a game master API. Output raw JSON only.") -> str:
    url = f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/ai/run/@cf/meta/llama-3.3-70b-instruct-fp8-fast"
    headers = {"Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}", "Content-Type": "application/json"}
    payload = {"messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}], "max_tokens": 1500, "temperature": 0.7}
    
    def fallback(reason, narrative):
        return json.dumps({"success": False, "reason": reason, "narrative_short": narrative, "narrative_long": narrative}, ensure_ascii=False)

    for attempt in range(2):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, json=payload, timeout=90.0)
                if response.status_code == 429:
                    if attempt == 0:
                        await asyncio.sleep(5)
                        continue
                    return fallback("محدودیت روزانه", "سهمیه AI تمام شده.")
                if response.status_code != 200:
                    if attempt == 0:
                        await asyncio.sleep(3)
                        continue
                    return fallback(f"خطای سرویس ({response.status_code})", "سرویس در دسترس نیست.")
                res_data = response.json()
                if res_data.get("success"):
                    resp = res_data["result"]["response"]
                    return json.dumps(resp, ensure_ascii=False) if isinstance(resp, dict) else str(resp)
                else:
                    if attempt == 0:
                        await asyncio.sleep(3)
                        continue
                    return fallback("مدل خطا داد", "پاسخ‌دهی نبود.")
        except httpx.TimeoutException:
            if attempt == 0:
                await asyncio.sleep(2)
                continue
            return fallback("تایم اوت", "سرویس پاسخگو نبود.")
        except Exception as e:
            if attempt == 0:
                await asyncio.sleep(2)
                continue
            return fallback("خطای شبکه", "ارتباط برقرار نشد.")

def _build_prompt(country: dict, order_text: str, category: str) -> str:
    if category == "political":
        narrative_rule = "The narrative MUST be a highly dramatic, grandiloquent political speech."
    elif category == "military":
        narrative_rule = "The narrative MUST be an epic war report."
    else:
        narrative_rule = "The narrative MUST be a dramatic economic news report."

    return f"""You are the strict Game Master of a grand strategy game set in 1979.
Analyze the order based on the country's GDP, Military Budget, and resources, and write TWO Persian narratives.

COUNTRY STATS (1979):
- Name: {country['name']}
- GDP: ${country['gdp']:,}
- Military Budget: ${country['mil_budget']:,}
- Army Personnel: {country['army']}
- Fighter Jets: {country['jets']}
- Refinery Capacity: {country['refineries']:,} bpd
- Satisfaction: {country.get('satisfaction', 50)}%

ORDER CATEGORY: {category}
ORDER: "{order_text}"

ECONOMY & MILITARY RULES:
1. All wealth is in EXACT US DOLLARS.
2. Military actions are funded by the Military Budget. Economic actions cost from the overall GDP.
3. Building a NEW REFINERY costs $500,000,000 and adds 1 refinery unit.
4. Buying 1 FIGHTER JET costs $30,000,000.
5. If cost > available funds, "success" MUST be false and all changes MUST be 0.
6. Calculate changes (gdp_change, mil_budget_change, jets_change, refineries_change) logically.

STRICT RULES:
1. Output MUST be valid JSON.
2. "narrative_short": 1-sentence breaking news in Persian (max 150 chars). No newlines.
3. "narrative_long": Detailed epic report in Persian (max 800 chars). No newlines.
4. Use ONLY Persian alphabet. No English/Chinese/Russian letters.

EXACT JSON FORMAT:
{{
  "success": true/false,
  "reason": "Strict Persian reason (max 100 chars)",
  "gdp_change": integer,
  "mil_budget_change": integer,
  "jets_change": integer,
  "refineries_change": integer,
  "satisfaction_change": integer (-10 to +10),
  "narrative_short": "Persian short news...",
  "narrative_long": "Persian epic report..."
}}
"""

async def analyze_and_apply_order(order_id: int):
    try:
        return await asyncio.wait_for(_analyze_inner(order_id), timeout=120.0)
    except asyncio.TimeoutError:
        data = {"success": False, "reason": "پردازش طول کشید", "narrative_short": "به تعویق افتاد.", "narrative_long": "به تعویق افتاد."}
        async with pool.acquire() as conn:
            await conn.execute("UPDATE orders SET status='ai_analyzed', ai_analysis_raw=$1 WHERE id=$2", json.dumps(data, ensure_ascii=False), order_id)
        return data

async def _analyze_inner(order_id: int):
    async with pool.acquire() as conn:
        order = await conn.fetchrow("SELECT * FROM orders WHERE id = $1", order_id)
        if not order:
            return {"success": False, "reason": "سفارش یافت نشد", "narrative_short": "", "narrative_long": ""}
        country = await conn.fetchrow("SELECT * FROM countries WHERE user_id = $1", order["user_id"])
    
    prompt = _build_prompt(dict(country), order["order_text"], order["category"])
    ai_response = await ask_ai(prompt, system_prompt="You are a strict JSON-only API. Use ONLY Persian characters.")
    data = _safe_parse_json(ai_response)

    if "success" not in data or "narrative_long" not in data:
        data = {"success": False, "reason": "پاسخ نامعتبر بود", "narrative_short": "خطا", "narrative_long": "نیاز به بررسی دستی.", "gdp_change": 0, "mil_budget_change": 0, "jets_change": 0, "refineries_change": 0, "satisfaction_change": 0}

    for k in ["narrative_short", "narrative_long", "reason"]:
        if k in data:
            data[k] = _clean_persian_text(str(data[k]))

    if data.get("success"):
        try:
            g_change = int(data.get("gdp_change") or 0)
            m_change = int(data.get("mil_budget_change") or 0)
            j_change = int(data.get("jets_change") or 0)
            r_change = int(data.get("refineries_change") or 0)
            s_change = int(data.get("satisfaction_change") or 0)
        except:
            data = {"success": False, "reason": "خطای عددی", "narrative_short": "", "narrative_long": "", "gdp_change": 0, "mil_budget_change": 0, "jets_change": 0, "refineries_change": 0, "satisfaction_change": 0}
        else:
            if country["gdp"] + g_change < 0 or country["mil_budget"] + m_change < 0:
                data = {"success": False, "reason": "ورشکستگی! بودجه کافی نیست.", "gdp_change": 0, "mil_budget_change": 0, "jets_change": 0, "refineries_change": 0, "satisfaction_change": -5, "narrative_short": "اقتصاد فروپاشید.", "narrative_long": "با خالی شدن خزانه ملی، طرح پیشنهادی با شکست سختی مواجه شد."}
            else:
                new_sat = max(0, min(100, country.get("satisfaction", 50) + s_change))
                data["satisfaction_change"] = new_sat - country.get("satisfaction", 50)
                async with pool.acquire() as conn:
                    await conn.execute(
                        "UPDATE countries SET gdp = GREATEST(0, gdp + $1), mil_budget = GREATEST(0, mil_budget + $2), jets = GREATEST(0, jets + $3), refineries = GREATEST(0, refineries + $4), satisfaction = $5 WHERE user_id = $6", 
                        g_change, m_change, j_change, r_change, new_sat, order["user_id"]
                    )

    async with pool.acquire() as conn:
        await conn.execute("UPDATE orders SET status='ai_analyzed', ai_analysis_raw=$1 WHERE id=$2", json.dumps(data, ensure_ascii=False), order_id)
    return data

async def set_commands(app):
    await app.bot.set_my_commands([
        BotCommand("start", "ثبت‌نام"), BotCommand("country", "اطلاعات کشور"), 
        BotCommand("economy", "انبار منابع"), BotCommand("factory", "مدیریت کارخانه‌ها"),
        BotCommand("mines", "معادن"), BotCommand("order", "دستور جدید"), 
        BotCommand("admin", "پنل ادمین"), BotCommand("turn", "پردازش نوبت (ادمین)")
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    async with pool.acquire() as conn:
        c = await conn.fetchrow("SELECT * FROM countries WHERE user_id = $1", uid)
    if c:
        if c["status"] == "active":
            await context.bot.send_message(uid, f"✅ کشور {c['name']} فعال است.")
        elif c["status"] == "pending":
            await context.bot.send_message(uid, "⏳ در انتظار تایید.")
        return
    temp[uid] = {"step": "SELECT_COUNTRY"}
    countries_list = "، ".join(ALLOWED_COUNTRIES)
    await context.bot.send_message(uid, f"🏛️ **Welcome to rustabad RP (1979)**\n\nلطفاً نام کشور خود را انتخاب کنید:\n\n{countries_list}", parse_mode="Markdown")

async def country_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with pool.acquire() as conn:
        c = await conn.fetchrow("SELECT * FROM countries WHERE user_id = $1", update.effective_user.id)
    if not c or c["status"] != "active":
        return
    data = COUNTRY_DB.get(c['name'])
    cities = data['cities'] if data else "نامشخص"
    text = (
        f"🏛️ *کشور: {c['name']}* (۱۹۷۹)\n"
        f"🏙️ *شهرها و استان‌ها:* {cities}\n\n"
        f"📈 GDP: {fmt_money(c['gdp'])}\n"
        f"🛡 بودجه نظامی: {fmt_money(c['mil_budget'])}\n"
        f"✈️ جنگنده‌ها: {c['jets']:,} فروند\n"
        f"🏭 ظرفیت پالایش: {c['refineries']:,} بشکه در روز\n"
        f"🎖 ارتش: {c['army']:,} نفر\n"
        f"❤️ رضایت: {c.get('satisfaction', 50)}%"
    )
    await context.bot.send_message(update.effective_user.id, text, parse_mode="Markdown")

async def economy_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with pool.acquire() as conn:
        c = await conn.fetchrow("SELECT * FROM countries WHERE user_id = $1", update.effective_user.id)
    if not c:
        return
    res_text = "".join([f"{v}: {c.get(f'res_{k}', 0):,}\n" for k, v in RESOURCES.items() if c.get(f'res_{k}', 0) > 0]) or "انبار خالی است.\n"
    await context.bot.send_message(update.effective_user.id, f"💰 *اقتصاد {c['name']}*\n🏦 GDP: {fmt_money(c['gdp'])}\n\n📦 *انبار:*\n{res_text}", parse_mode="Markdown")

async def mines_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with pool.acquire() as conn:
        c = await conn.fetchrow("SELECT * FROM countries WHERE user_id = $1", update.effective_user.id)
    if not c:
        return
    data = COUNTRY_DB.get(c['name'])
    if not data:
        return
    text = f"⛏ *معادن {c['name']}*\n\n"
    for m in data['mines'].values():
        text += f"🔹 {m['name']}\n📦 {m['amount']:,} واحد {RESOURCES.get(m['output_res'], m['output_res'])} در هر نوبت\n\n"
    await context.bot.send_message(update.effective_user.id, text, parse_mode="Markdown")

async def factory_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with pool.acquire() as conn:
        c = await conn.fetchrow("SELECT * FROM countries WHERE user_id = $1", update.effective_user.id)
        infras = await conn.fetch("SELECT sector_type, count(*) as count FROM infrastructure WHERE user_id = $1 GROUP BY sector_type", update.effective_user.id)
    if not c:
        return
    counts = {r['sector_type']: r['count'] for r in infras}
    data = COUNTRY_DB.get(c['name'])
    if not data:
        return
    rows = []
    for k, f in data['factories'].items():
        if counts.get(k, 0) < 5:
            rows.append([InlineKeyboardButton(f"🏭 {f['name']} | {fmt_money(f['cost'])}", callback_data=f"fact_build_{k}")])
    await context.bot.send_message(update.effective_user.id, f"🏭 *کارخانه‌ها {c['name']}*\n\nبرای ساخت کلیک کنید:", parse_mode="Markdown", reply_markup=kb(rows))

async def order_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    async with pool.acquire() as conn:
        c = await conn.fetchrow("SELECT * FROM countries WHERE user_id = $1", uid)
    if not c or c["status"] != "active":
        return await update.message.reply_text("⚠️ مجاز نیستید.")
    if not context.args:
        return await update.message.reply_text("⚠️ مثال: `/order سرمایه‌گذاری ۱۰ میلیون دلاری`")
    temp[uid] = {"order_text": " ".join(context.args), "step": "ORDER_CATEGORY"}
    await update.message.reply_text("دسته‌بندی؟", reply_markup=kb([[InlineKeyboardButton("💰 اقتصادی", callback_data="cat_economic")], [InlineKeyboardButton("🏛️ سیاسی", callback_data="cat_political")], [InlineKeyboardButton("⚔️ نظامی", callback_data="cat_military")]]))

async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    await update.message.reply_text("👑 **پنل ادمین**", reply_markup=kb([
        [InlineKeyboardButton("📋 لیست کشورها", callback_data="adm_list")],
        [InlineKeyboardButton("⏳ پردازش نوبت", callback_data="adm_next_turn")],
        [InlineKeyboardButton("💰 تنظیم GDP", callback_data="adm_set_gdp")]
    ]), parse_mode="Markdown")

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text.strip()
    t = temp.get(uid, {})
    
    if t.get("step") == "SELECT_COUNTRY":
        if text not in ALLOWED_COUNTRIES:
            return await context.bot.send_message(uid, "❌ کشور نامعتبر.")
        async with pool.acquire() as conn:
            taken = await conn.fetchval("SELECT 1 FROM countries WHERE name = $1 AND status != 'rejected'", text)
            if taken:
                return await context.bot.send_message(uid, "❌ قبلاً انتخاب شده.")
            
            data = COUNTRY_DB[text]
            await conn.execute(
                "INSERT INTO countries (user_id, username, name, status, gdp, mil_budget, jets, refineries) VALUES ($1, $2, $3, 'pending', $4, $5, $6, $7)", 
                uid, update.effective_user.username or "بدون", text, data['gdp_init'], data['mil_budget_init'], data['jets_init'], data['refineries_init']
            )
        temp.pop(uid, None)
        await context.bot.send_message(uid, "⏳ در انتظار تایید.")
        await context.bot.send_message(ADMIN_ID, f"📥 **درخواست جدید**\n🌍 {text}\n🆔 `{uid}`", parse_mode="Markdown", reply_markup=kb([[InlineKeyboardButton("✅ تایید", callback_data=f"adm_ok_{uid}"), InlineKeyboardButton("❌ رد", callback_data=f"adm_rej_{uid}")]]))
        
    elif t.get("step") == "ADMIN_SET_GDP_ID" and uid == ADMIN_ID:
        try:
            temp[uid] = {"step": "ADMIN_SET_GDP_AMOUNT", "target_id": int(text)}
            await update.message.reply_text("مقدار GDP (دلار):")
        except:
            await update.message.reply_text("❌ عدد وارد کنید.")
            
    elif t.get("step") == "ADMIN_SET_GDP_AMOUNT" and uid == ADMIN_ID:
        try:
            async with pool.acquire() as conn:
                await conn.execute("UPDATE countries SET gdp = $1 WHERE user_id = $2", int(text), t["target_id"])
            temp.pop(uid, None)
            await update.message.reply_text("✅ تنظیم شد.")
        except:
            await update.message.reply_text("❌ عدد وارد کنید.")

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cb = update.callback_query
    data = cb.data
    uid = cb.from_user.id
    t = temp.get(uid, {})
    await cb.answer()
    
    if data.startswith("adm_ok_"):
        target = int(data.split("_")[2])
        async with pool.acquire() as conn:
            await conn.execute("UPDATE countries SET status = 'active' WHERE user_id = $1", target)
        await cb.edit_message_text("✅ تایید شد.")
        await context.bot.send_message(target, "🎉 کشور شما تایید شد!")
        
    elif data.startswith("adm_rej_"):
        target = int(data.split("_")[2])
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM countries WHERE user_id = $1", target)
        await cb.edit_message_text("❌ رد شد.")
        
    elif data == "adm_list":
        async with pool.acquire() as conn:
            countries = await conn.fetch("SELECT * FROM countries WHERE status = 'active'")
        txt = "📊 **لیست کشورها:**\n\n" + "".join([f"🏛️ {c['name']} | GDP: {fmt_money(c['gdp'])}\n" for c in countries])
        await cb.edit_message_text(txt, parse_mode="Markdown", reply_markup=kb([[InlineKeyboardButton("🔙 بازگشت", callback_data="adm_back")]]))
        
    elif data == "adm_next_turn":
        await cb.edit_message_text("⏳ در حال پردازش...")
        await process_turn(context)
        
    elif data == "adm_set_gdp":
        await cb.edit_message_text("🆔 آیدی کاربر:")
        temp[uid] = {"step": "ADMIN_SET_GDP_ID"}
        
    elif data == "adm_back":
        await cb.edit_message_text("👑 **پنل ادمین**", reply_markup=kb([[InlineKeyboardButton("📋 لیست کشورها", callback_data="adm_list")], [InlineKeyboardButton("⏳ پردازش نوبت", callback_data="adm_next_turn")], [InlineKeyboardButton("💰 تنظیم GDP", callback_data="adm_set_gdp")]]), parse_mode="Markdown")

    elif data.startswith("cat_"):
        ot = t.get("order_text")
        temp.pop(uid, None)
        if not ot:
            return await cb.edit_message_text("⚠️ منقضی شده.")
        async with pool.acquire() as conn:
            oid = await conn.fetchval("INSERT INTO orders (user_id, order_text, category) VALUES ($1, $2, $3) RETURNING id", uid, ot, data.replace("cat_", ""))
            c = await conn.fetchrow("SELECT * FROM countries WHERE user_id = $1", uid)
        await context.bot.send_message(ADMIN_ID, f"📜 **دستور از {c['name']}**\n📝 {ot}", parse_mode="Markdown", reply_markup=kb([[InlineKeyboardButton("✅ تایید", callback_data=f"ord_appr_{oid}")], [InlineKeyboardButton("❌ رد", callback_data=f"ord_rej_{oid}")]]))
        await cb.edit_message_text("⏳ ارسال به ادمین.")
        
    elif data.startswith("ord_appr_"):
        oid = int(data.split("_")[2])
        await cb.edit_message_text("⏳ تحلیل...")
        await send_analysis(cb, context, oid)
        
    elif data.startswith("ord_rej_"):
        oid = int(data.split("_")[2])
        async with pool.acquire() as conn:
            await conn.execute("UPDATE orders SET status = 'rejected' WHERE id = $1", oid)
        await cb.edit_message_text("❌ رد شد.")
        
    elif data.startswith("pub_short_") or data.startswith("pub_long_"):
        is_short = "pub_short_" in data
        oid = int(data.split("_")[2])
        await cb.answer("در حال ارسال...")
        async with pool.acquire() as conn:
            order = await conn.fetchrow("SELECT * FROM orders WHERE id = $1", oid)
        try:
            ai_data = json.loads(order["ai_analysis_raw"] or "{}")
        except:
            ai_data = {}
        text_to_send = ai_data.get('narrative_short', '') if is_short else ai_data.get('narrative_long', '')
        if CHANNEL_ID:
            try:
                await context.bot.send_message(int(CHANNEL_ID.strip()), f"📢 بیانیه رسمی\n\n{text_to_send}")
                async with pool.acquire() as conn:
                    await conn.execute("UPDATE orders SET status = 'published' WHERE id = $1", oid)
                await cb.edit_message_text("✅ در کانال منتشر شد.")
            except Exception as e:
                await cb.edit_message_text(f"❌ خطا: {e}\n(چک کن ربات ادمین باشه)")
        else:
            await cb.edit_message_text("⚠️ آیدی کانال تنظیم نشده.")
            
    elif data == "cancel_pub":
        await cb.edit_message_text("❌ لغو شد.")
        
    elif data.startswith("fact_build_"):
        sector = data.replace("fact_build_", "")
        async with pool.acquire() as conn:
            c = await conn.fetchrow("SELECT * FROM countries WHERE user_id = $1", uid)
        req = COUNTRY_DB.get(c['name'], {}).get('factories', {}).get(sector)
        if not req:
            return
        if c['gdp'] < req['cost']:
            return await cb.answer("❌ GDP کافی نیست!", show_alert=True)
        async with pool.acquire() as conn:
            await conn.execute("UPDATE countries SET gdp = gdp - $1 WHERE user_id = $2", req['cost'], uid)
            await conn.execute("INSERT INTO infrastructure (user_id, sector_type, name, income) VALUES ($1, $2, $3, $4)", uid, sector, req['name'], req['income'])
        await cb.answer("✅ ساخته شد!", show_alert=True)

async def send_analysis(update_or_cb, context, order_id):
    ai_data = await analyze_and_apply_order(order_id)
    st = "✅ موفق" if ai_data.get("success") else "❌ ناموفق"
    ch = ""
    if ai_data.get("success"):
        ch = f"\n📈 GDP: {ai_data.get('gdp_change',0):+,} $ | ✈️ جنگنده: {ai_data.get('jets_change',0):+,} | 🏭 پالایشگاه: {ai_data.get('refineries_change',0):+,} | ❤️ رضایت: {ai_data.get('satisfaction_change',0):+,}\n"
    txt = f"🧠 تحلیل (70B)\n\n📌 وضعیت: {st}\n📝 دلیل: {ai_data.get('reason', '')}\n{ch}\n📰 **خلاصه:**\n{ai_data.get('narrative_short', '')}\n\n📖 **کامل:**\n{ai_data.get('narrative_long', '')}"
    btn = kb([[InlineKeyboardButton("📢 خلاصه", callback_data=f"pub_short_{order_id}"), InlineKeyboardButton("📜 کامل", callback_data=f"pub_long_{order_id}")], [InlineKeyboardButton("❌ لغو", callback_data="cancel_pub")]])
    if isinstance(update_or_cb, CallbackQuery):
        try:
            await update_or_cb.edit_message_text(txt, reply_markup=btn)
            return
        except:
            pass
    await context.bot.send_message(update_or_cb.from_user.id, txt, reply_markup=btn)

async def process_turn(context):
    async with pool.acquire() as conn:
        countries = await conn.fetch("SELECT * FROM countries WHERE status = 'active'")
        for c in countries:
            c_data = COUNTRY_DB.get(c['name'])
            if not c_data:
                continue
            updates = {}
            for m in c_data['mines'].values():
                updates[f'res_{m["output_res"]}'] = c.get(f'res_{m["output_res"]}', 0) + m['amount']
            if updates:
                set_clause = ", ".join([f"{k} = {v}" for k, v in updates.items()])
                await conn.execute(f"UPDATE countries SET {set_clause} WHERE user_id = $1", c['user_id'])
            
        infras = await conn.fetch("SELECT * FROM infrastructure")
        for i in infras:
            c = await conn.fetchrow("SELECT * FROM countries WHERE user_id = $1", i['user_id'])
            fact = COUNTRY_DB.get(c['name'], {}).get('factories', {}).get(i['sector_type'])
            if not fact:
                continue
            if c.get(f'res_{fact["consumes"]}', 0) >= 1000:
                await conn.execute(f"UPDATE countries SET res_{fact['consumes']} = res_{fact['consumes']} - 1000, res_{fact['produces']} = res_{fact['produces']} + 500, gdp = gdp + $1 WHERE user_id = $2", fact['income'], c['user_id'])
    await context.bot.send_message(ADMIN_ID, "✅ نوبت پردازش شد. منابع استخراج و درآمد به GDP اضافه شد.")

async def post_init(app):
    await init_db()
    await set_commands(app)
    await app.bot.delete_webhook(drop_pending_updates=True)

def main():
    app = Application.builder().token(TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("country", country_cmd))
    app.add_handler(CommandHandler("economy", economy_cmd))
    app.add_handler(CommandHandler("mines", mines_cmd))
    app.add_handler(CommandHandler("factory", factory_cmd))
    app.add_handler(CommandHandler("order", order_cmd))
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(CommandHandler("turn", process_turn))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    
    rh = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
    if rh:
        port = int(os.environ.get("PORT", 10000))
        app.run_webhook(listen="0.0.0.0", port=port, url_path=TOKEN, webhook_url=f"https://{rh}/{TOKEN}")
    else:
        app.run_polling()

if __name__ == "__main__":
    main()
