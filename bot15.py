import os
import time
import json
import logging
import asyncpg
import random
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
    "wheat": "🌾 گندم", "iron_ore": "⛏ سنگ آهن", "bauxite": "🪨 بوکسیت",
    "copper_ore": "🟤 سنگ مس", "titanium_ore": "⚙️ سنگ تیتانیوم", "gold": "🏵 طلا",
    "uranium": "☢ اورانیوم", "rare_earth": "💎 فلزات نادر", "crude_oil": "🛢 نفت خام",
    "steel": "🏗 فولاد", "aluminum": "🔩 آلومینیوم", "copper": "🔌 مس",
    "titanium": "🛡 تیتانیوم", "power": "⚡️ برق", "chemicals": "🧪 مواد شیمیایی",
    "explosives_base": "💥 مواد منفجره پایه", "car_parts": "⚙️ قطعات خودرو",
    "aero_parts": "🚀 قطعات هوافضا", "electronics": "📟 الکترونیک", "tnt": "🧨 TNT",
}

START_RES = {
    "power": 1000, "crude_oil": 1000, "steel": 1000, "iron_ore": 1000, "wheat": 2000,
}

BUILDINGS = {
    "iron_mine": {"name": "⛏ معدن آهن", "type": "mining", "cost": 10000, "workers": 5000, "build_workers": 5000, "input": {"power": 10}, "output": {"iron_ore": 20}, "income": 5000},
    "bauxite_mine": {"name": "🪨 معدن بوکسیت", "type": "mining", "cost": 12000, "workers": 5000, "build_workers": 5000, "input": {"power": 10}, "output": {"bauxite": 20}, "income": 6000},
    "copper_mine": {"name": "🟤 معدن مس", "type": "mining", "cost": 11000, "workers": 5000, "build_workers": 5000, "input": {"power": 10}, "output": {"copper_ore": 20}, "income": 5500},
    "oil_well": {"name": "🛢 چاه نفت", "type": "extractive", "cost": 15000, "workers": 8000, "build_workers": 8000, "input": {"power": 15}, "output": {"crude_oil": 30}, "income": 7500},
    "gold_mine": {"name": "🏵 معدن طلا", "type": "mining", "cost": 25000, "workers": 6000, "build_workers": 6000, "input": {"power": 30}, "output": {"gold": 10}, "income": 12500},
    "rare_earth_mine": {"name": "💎 معدن فلزات نادر", "type": "mining", "cost": 30000, "workers": 8000, "build_workers": 8000, "input": {"power": 30}, "output": {"rare_earth": 10}, "income": 15000},
    "power_plant": {"name": "⚡️ نیروگاه برق", "type": "industrial", "cost": 20000, "workers": 15000, "build_workers": 10000, "input": {"crude_oil": 10, "steel": 5}, "output": {"power": 200}, "income": 10000},
    "steel_mill": {"name": "🏗 کارخانه فولاد", "type": "industrial", "cost": 20000, "workers": 15000, "build_workers": 10000, "input": {"iron_ore": 20, "power": 20}, "output": {"steel": 10}, "income": 10000},
    "aluminum_smelter": {"name": "🔩 کارخانه آلومینیوم", "type": "industrial", "cost": 22000, "workers": 15000, "build_workers": 10000, "input": {"bauxite": 20, "power": 30}, "output": {"aluminum": 10}, "income": 11000},
    "copper_refinery": {"name": "🔌 پالایشگاه مس", "type": "industrial", "cost": 18000, "workers": 12000, "build_workers": 10000, "input": {"copper_ore": 20, "power": 20}, "output": {"copper": 10}, "income": 9000},
    "oil_refinery": {"name": "🛢 پالایشگاه نفت", "type": "industrial", "cost": 30000, "workers": 20000, "build_workers": 10000, "input": {"crude_oil": 30, "power": 40}, "output": {"chemicals": 10, "explosives_base": 5}, "income": 15000},
    "car_parts_factory": {"name": "⚙️ کارخانه قطعات خودرو", "type": "industrial", "cost": 50000, "workers": 20000, "build_workers": 15000, "input": {"steel": 10, "aluminum": 10}, "output": {"car_parts": 10}, "income": 25000},
    "electronics_factory": {"name": "📟 کارخانه الکترونیک", "type": "industrial", "cost": 60000, "workers": 20000, "build_workers": 15000, "input": {"copper": 10, "gold": 5}, "output": {"electronics": 10}, "income": 30000},
    "tnt_factory": {"name": "🧨 خط تولید TNT", "type": "industrial", "cost": 80000, "workers": 25000, "build_workers": 15000, "input": {"explosives_base": 10, "chemicals": 10}, "output": {"tnt": 5}, "income": 40000},
    "wheat_farm": {"name": "🌾 مزرعه گندم", "type": "agricultural", "cost": 5000, "workers": 5000, "build_workers": 5000, "output": {"wheat": 100}, "income": 2500},
    "bazaar": {"name": "🏪 بازار محلی", "type": "commercial", "cost": 10000, "workers": 8000, "build_workers": 5000, "income": 5000},
    "bank": {"name": "🏦 بانک مرکزی", "type": "commercial", "cost": 40000, "workers": 15000, "build_workers": 10000, "income": 20000},
    "house": {"name": "🏠 خانه‌های مسکونی", "type": "residential", "cost": 5000, "workers": 1000, "build_workers": 2000, "pop": 100000, "happiness": 1},
    "park": {"name": "🌳 پارک و فضای سبز", "type": "residential", "cost": 8000, "workers": 2000, "build_workers": 2000, "happiness": 2},
    "hospital": {"name": "🏥 بیمارستان", "type": "welfare", "cost": 20000, "workers": 10000, "build_workers": 8000, "income": 0, "maintenance": 5000},
    "school": {"name": "🏫 مدرسه", "type": "welfare", "cost": 15000, "workers": 8000, "build_workers": 8000, "income": 0, "maintenance": 3000},
}

MARKET_PRICES = {
    "wheat": 40, "iron_ore": 50, "bauxite": 60, "copper_ore": 70,
    "crude_oil": 80, "gold": 400, "rare_earth": 500, "power": 30,
    "steel": 200, "aluminum": 220, "copper": 250, "chemicals": 300, "explosives_base": 600,
    "car_parts": 1000, "electronics": 1500, "tnt": 5000
}

MARKET_CATS = {
    "raw": ["wheat", "iron_ore", "bauxite", "copper_ore", "gold", "rare_earth", "crude_oil"],
    "processed": ["steel", "aluminum", "copper", "power", "chemicals", "explosives_base"],
    "parts": ["car_parts", "electronics"],
    "final": ["tnt"],
}

ZONE_TYPES = {
    "residential": "🏘️ مسکونی", "industrial": "🏭 صنعتی",
    "agricultural": "🌾 کشاورزی", "extractive": "⛽ استخراجی",
    "mining": "⛏️ معدنی", "commercial": "🏪 تجاری",
    "welfare": "🏥 رفاهی",
}

ZONE_SIZES = {
    "small": {"name": "کوچک", "capacity": 3, "cost": 5000},
    "medium": {"name": "متوسط", "capacity": 6, "cost": 10000},
    "large": {"name": "بزرگ", "capacity": 10, "cost": 20000},
}

TIER_INFO = {
    1: {"name": "جنگ جهانی دوم (۱۹۴۰-۱۹۴۵)", "science": 10},
    2: {"name": "جنگ سرد (۱۹۵۰-۱۹۹۰)", "science": 50},
    3: {"name": "مدرن و امروزی (۲۰۰۰-اکنون)", "science": 100},
}

MILITARY_COMPANIES = {
    # ========== سطح ۱ ==========
    "mosin": {"name": "مسین (Mosin)", "tier": 1, "spec": "small_arms", "country": "شوروی", "founding_cost": 20000000},
    "steyr": {"name": "اشتایر (Steyr)", "tier": 1, "spec": "small_arms", "country": "اتریش", "founding_cost": 22000000},
    "walther": {"name": "والتر (Walther)", "tier": 1, "spec": "small_arms", "country": "آلمان", "founding_cost": 25000000},
    "springfield": {"name": "اسپرینگفیلد", "tier": 1, "spec": "small_arms", "country": "آمریکا", "founding_cost": 25000000},
    "enfield": {"name": "انفیلد (Enfield)", "tier": 1, "spec": "small_arms", "country": "بریتانیا", "founding_cost": 28000000},
    "mauser": {"name": "مایزر (Mauser)", "tier": 1, "spec": "small_arms", "country": "آلمان", "founding_cost": 30000000},
    "browning": {"name": "براونینگ", "tier": 1, "spec": "small_arms", "country": "آمریکا", "founding_cost": 30000000},
    "colt": {"name": "کلت (Colt)", "tier": 1, "spec": "small_arms", "country": "آمریکا", "founding_cost": 32000000},
    "skoda": {"name": "اشکودا (Skoda)", "tier": 1, "spec": "tanks", "country": "چکسلواکی", "founding_cost": 30000000},
    "vickers": {"name": "ویکرز (Vickers)", "tier": 1, "spec": "tanks", "country": "بریتانیا", "founding_cost": 33000000},
    "daimler_benz": {"name": "دایملر-بنز", "tier": 1, "spec": "tanks", "country": "آلمان", "founding_cost": 34000000},
    "man": {"name": "ام‌آان (MAN)", "tier": 1, "spec": "tanks", "country": "آلمان", "founding_cost": 35000000},
    "chrysler_ww2": {"name": "کرایسلر (نسل جنگ)", "tier": 1, "spec": "tanks", "country": "آمریکا", "founding_cost": 36000000},
    "henschel": {"name": "هنشل (Henschel)", "tier": 1, "spec": "tanks", "country": "آلمان", "founding_cost": 38000000},
    "vickers_armstrong": {"name": "ویکرز آرمسترانگ", "tier": 1, "spec": "artillery", "country": "بریتانیا", "founding_cost": 32000000},
    "bofors": {"name": "بوفورس (Bofors)", "tier": 1, "spec": "artillery", "country": "سوئد", "founding_cost": 34000000},
    "rheinmetall": {"name": "راینمتال (نسل اول)", "tier": 1, "spec": "artillery", "country": "آلمان", "founding_cost": 37000000},
    "krupp": {"name": "کروپ (Krupp)", "tier": 1, "spec": "artillery", "country": "آلمان", "founding_cost": 39000000},
    "yakovlev": {"name": "یاکوولف (Yakovlev)", "tier": 1, "spec": "aircraft", "country": "شوروی", "founding_cost": 30000000},
    "ilyushin": {"name": "ایلیوشین (Ilyushin)", "tier": 1, "spec": "aircraft", "country": "شوروی", "founding_cost": 32000000},
    "mitsubishi_ww2": {"name": "میتسوبیشی (نسل جنگ)", "tier": 1, "spec": "aircraft", "country": "ژاپن", "founding_cost": 33000000},
    "republic_aviation": {"name": "ریپابلیک اوییشن", "tier": 1, "spec": "aircraft", "country": "آمریکا", "founding_cost": 33000000},
    "heinkel": {"name": "هاینکل (Heinkel)", "tier": 1, "spec": "aircraft", "country": "آلمان", "founding_cost": 34000000},
    "avro": {"name": "آورو (Avro)", "tier": 1, "spec": "aircraft", "country": "بریتانیا", "founding_cost": 34000000},
    "supermarine": {"name": "سوپرمارین", "tier": 1, "spec": "aircraft", "country": "بریتانیا", "founding_cost": 35000000},
    "junkers": {"name": "یونکرس (Junkers)", "tier": 1, "spec": "aircraft", "country": "آلمان", "founding_cost": 35000000},
    "tupolev_ww2": {"name": "توپولف (نسل جنگ)", "tier": 1, "spec": "aircraft", "country": "شوروی", "founding_cost": 36000000},
    "focke_wulf": {"name": "فوکه-وولف", "tier": 1, "spec": "aircraft", "country": "آلمان", "founding_cost": 36000000},
    "north_american": {"name": "نورث امریکن", "tier": 1, "spec": "aircraft", "country": "آمریکا", "founding_cost": 37000000},
    "messerschmitt": {"name": "مسرشمیت", "tier": 1, "spec": "aircraft", "country": "آلمان", "founding_cost": 38000000},
    "boeing": {"name": "بوئینگ (نسل جنگ)", "tier": 1, "spec": "aircraft", "country": "آمریکا", "founding_cost": 39000000},
    "kure_naval": {"name": "کارخانه دریایی کوره (سازنده یاماتو)", "tier": 1, "spec": "ships", "country": "ژاپن", "founding_cost": 40000000},

    # ========== سطح ۲ ==========
    "beretta": {"name": "برتا (Beretta)", "tier": 2, "spec": "small_arms", "country": "ایتالیا", "founding_cost": 50000000},
    "uzi": {"name": "اوزی (Uzi)", "tier": 2, "spec": "small_arms", "country": "اسرائیل", "founding_cost": 50000000},
    "saab": {"name": "ساب (Gripen)", "tier": 2, "spec": "aircraft", "country": "سوئد", "founding_cost": 50000000},
    "bac": {"name": "بی‌ای‌سی (Jaguar)", "tier": 2, "spec": "aircraft", "country": "بریتانیا", "founding_cost": 50000000},
    "panavia": {"name": "پاناویا (Tornado)", "tier": 2, "spec": "aircraft", "country": "اروپا", "founding_cost": 50000000},
    "hughes": {"name": "هیوز (AIM-54)", "tier": 2, "spec": "missiles", "country": "آمریکا", "founding_cost": 50000000},
    "vympel": {"name": "ویمپل (R-73)", "tier": 2, "spec": "missiles", "country": "شوروی", "founding_cost": 50000000},
    "norinco": {"name": "نورینکو (Type 99)", "tier": 2, "spec": "tanks", "country": "چین", "founding_cost": 50000000},
    "mitsubishi_heavy": {"name": "میتسوبیشی هوی", "tier": 2, "spec": "tanks", "country": "ژاپن", "founding_cost": 50000000},
    "kharkiv": {"name": "خارکوف (T-64)", "tier": 2, "spec": "tanks", "country": "شوروی", "founding_cost": 50000000},
    "fn_herstal": {"name": "اف‌ان هرستال", "tier": 2, "spec": "small_arms", "country": "بلژیک", "founding_cost": 70000000},
    "heckler_koch": {"name": "هکلر و کخ (H&K)", "tier": 2, "spec": "small_arms", "country": "آلمان", "founding_cost": 75000000},
    "kalashnikov": {"name": "کالاشنیکوف (AK)", "tier": 2, "spec": "small_arms", "country": "شوروی", "founding_cost": 80000000},
    "kirov": {"name": "کیروف (T-80)", "tier": 2, "spec": "tanks", "country": "شوروی", "founding_cost": 75000000},
    "grumman": {"name": "گرومن (F-14)", "tier": 2, "spec": "aircraft", "country": "آمریکا", "founding_cost": 75000000},
    "mbda": {"name": "ام‌بی‌دی‌ای (Exocet)", "tier": 2, "spec": "missiles", "country": "اروپا", "founding_cost": 75000000},
    "krauss_maffei": {"name": "کراوس-مفای (Leopard)", "tier": 2, "spec": "tanks", "country": "آلمان", "founding_cost": 80000000},
    "dassault": {"name": "داسو (Mirage)", "tier": 2, "spec": "aircraft", "country": "فرانسه", "founding_cost": 80000000},
    "northrop": {"name": "نورثروپ (F-5/B-2)", "tier": 2, "spec": "aircraft", "country": "آمریکا", "founding_cost": 82000000},
    "general_dynamics": {"name": "جنرال داینامیکس (M1)", "tier": 2, "spec": "tanks", "country": "آمریکا", "founding_cost": 85000000},
    "mcdonnell_douglas": {"name": "مک‌دانل داگلاس", "tier": 2, "spec": "aircraft", "country": "آمریکا", "founding_cost": 85000000},
    "mig": {"name": "میگ (MiG-29/31)", "tier": 2, "spec": "aircraft", "country": "شوروی", "founding_cost": 85000000},
    "almaz_antey": {"name": "آلماز-آنتی (S-300)", "tier": 2, "spec": "missiles", "country": "شوروی", "founding_cost": 85000000},
    "tupolev": {"name": "توپولف (Tu-95/160)", "tier": 2, "spec": "aircraft", "country": "شوروی", "founding_cost": 88000000},
    "uralvagonzavod": {"name": "اورال‌واگن‌زاود (T-72)", "tier": 2, "spec": "tanks", "country": "شوروی", "founding_cost": 90000000},
    "raytheon": {"name": "ریتئون (Patriot)", "tier": 2, "spec": "missiles", "country": "آمریکا", "founding_cost": 90000000},
    "sukhoi": {"name": "سوخو (Su-27/30/35)", "tier": 2, "spec": "aircraft", "country": "شوروی", "founding_cost": 95000000},
    "lockheed": {"name": "لاکهید (F-16/F-117)", "tier": 2, "spec": "aircraft", "country": "آمریکا", "founding_cost": 95000000},

    # ========== سطح ۳ ==========
    "glock": {"name": "گلاک (Glock)", "tier": 3, "spec": "small_arms", "country": "اتریش", "founding_cost": 50000000},
    "sig_sauer": {"name": "زیگ ساور", "tier": 3, "spec": "small_arms", "country": "سوئیس", "founding_cost": 50000000},
    "norinco_modern": {"name": "نورینکو مدرن", "tier": 3, "spec": "tanks", "country": "چین", "founding_cost": 50000000},
    "suparco": {"name": "سازمان فضایی پاکستان", "tier": 3, "spec": "missiles", "country": "پاکستان", "founding_cost": 50000000},
    "pof": {"name": "کارخانه‌های مهمات‌سازی پاکستان", "tier": 3, "spec": "small_arms", "country": "پاکستان", "founding_cost": 50000000},
    "hesa": {"name": "صنایع هواپیماسازی ایران (HESA)", "tier": 3, "spec": "aircraft", "country": "ایران", "founding_cost": 50000000},
    "barij": {"name": "صنایع شیمیایی بریج", "tier": 3, "spec": "artillery", "country": "ایران", "founding_cost": 50000000},
    "shahid_bagheri": {"name": "صنایع شهید باقری (پهپاد)", "tier": 3, "spec": "drones", "country": "ایران", "founding_cost": 50000000},
    "general_atomics": {"name": "جنرال اتمیکس (MQ-9)", "tier": 3, "spec": "drones", "country": "آمریکا", "founding_cost": 70000000},
    "baykar": {"name": "بایکار (TB2)", "tier": 3, "spec": "drones", "country": "ترکیه", "founding_cost": 70000000},
    "iai": {"name": "صنایع هوافضای اسرائیل", "tier": 3, "spec": "drones", "country": "اسرائیل", "founding_cost": 70000000},
    "elbit": {"name": "ال‌بیت سیستمز", "tier": 3, "spec": "drones", "country": "اسرائیل", "founding_cost": 70000000},
    "mig_modern": {"name": "میگ (MiG-35)", "tier": 3, "spec": "aircraft", "country": "روسیه", "founding_cost": 75000000},
    "hanwha": {"name": "هانوا (K9)", "tier": 3, "spec": "artillery", "country": "کره جنوبی", "founding_cost": 75000000},
    "rafael": {"name": "رافائل (Iron Dome)", "tier": 3, "spec": "missiles", "country": "اسرائیل", "founding_cost": 75000000},
    "dio": {"name": "سازمان صنایع دفاع (DIO)", "tier": 3, "spec": "tanks", "country": "ایران", "founding_cost": 75000000},
    "roketsan": {"name": "صنایع موشکی روکسان", "tier": 3, "spec": "missiles", "country": "ترکیه", "founding_cost": 75000000},
    "aselsan": {"name": "آسلان (ASELSAN)", "tier": 3, "spec": "drones", "country": "ترکیه", "founding_cost": 75000000},
    "iaio": {"name": "سازمان صنایع هوایی ایران", "tier": 3, "spec": "aircraft", "country": "ایران", "founding_cost": 78000000},
    "qods": {"name": "صنایع هوایی قدس (شاهد)", "tier": 3, "spec": "drones", "country": "ایران", "founding_cost": 78000000},
    "blackwater": {"name": "بلک‌واتر / کانستلیس", "tier": 3, "spec": "small_arms", "country": "آمریکا", "founding_cost": 78000000},
    "wagner": {"name": "گروه واگنر (PMC)", "tier": 3, "spec": "small_arms", "country": "روسیه", "founding_cost": 78000000},
    "ktrv": {"name": "KTRV (Kalibr)", "tier": 3, "spec": "missiles", "country": "روسیه", "founding_cost": 80000000},
    "tai": {"name": "صنایع هوافضای ترکیه (KAAN)", "tier": 3, "spec": "aircraft", "country": "ترکیه", "founding_cost": 80000000},
    "hyundai_rotem": {"name": "هیوندای روتم (K2)", "tier": 3, "spec": "tanks", "country": "کره جنوبی", "founding_cost": 80000000},
    "rheinmetall_defence": {"name": "راینمتال دیفنس", "tier": 3, "spec": "artillery", "country": "آلمان", "founding_cost": 80000000},
    "aio": {"name": "سازمان صنایع هوافضا (AIO)", "tier": 3, "spec": "missiles", "country": "ایران", "founding_cost": 80000000},
    "sami": {"name": "صنایع نظامی سعودی (SAMI)", "tier": 3, "spec": "tanks", "country": "عربستان", "founding_cost": 80000000},
    "avic": {"name": "AVIC (J-20)", "tier": 3, "spec": "aircraft", "country": "چین", "founding_cost": 82000000},
    "krauss_maffei_modern": {"name": "کراوس-مفای (Leopard 2A7)", "tier": 3, "spec": "tanks", "country": "آلمان", "founding_cost": 82000000},
    "kai": {"name": "KAI (KF-21)", "tier": 3, "spec": "aircraft", "country": "کره جنوبی", "founding_cost": 83000000},
    "casc": {"name": "CASC (DF-41)", "tier": 3, "spec": "missiles", "country": "چین", "founding_cost": 83000000},
    "irgc_asf": {"name": "نیروی هوافضای سپاه (IRGC)", "tier": 3, "spec": "missiles", "country": "ایران", "founding_cost": 83000000},
    "edge_group": {"name": "گروه ادج (EDGE)", "tier": 3, "spec": "drones", "country": "امارات", "founding_cost": 85000000},
    "tupolev_modern": {"name": "توپولف (Tu-160)", "tier": 3, "spec": "aircraft", "country": "روسیه", "founding_cost": 85000000},
    "boeing_defense": {"name": "بوئینگ دیفنس (F-15EX)", "tier": 3, "spec": "aircraft", "country": "آمریکا", "founding_cost": 85000000},
    "dassault_aviation": {"name": "داسو اوییشن (Rafale)", "tier": 3, "spec": "aircraft", "country": "فرانسه", "founding_cost": 85000000},
    "fincantieri": {"name": "فینکانتیری", "tier": 3, "spec": "ships", "country": "ایتالیا", "founding_cost": 85000000},
    "bae_systems": {"name": "بی‌ای‌ئی سیستمز", "tier": 3, "spec": "aircraft", "country": "بریتانیا", "founding_cost": 88000000},
    "airbus_defence": {"name": "ایرباس دیفنس", "tier": 3, "spec": "aircraft", "country": "اروپا", "founding_cost": 88000000},
    "uac": {"name": "یونایتد ایرکرافت (UAC)", "tier": 3, "spec": "aircraft", "country": "روسیه", "founding_cost": 88000000},
    "raytheon_tech": {"name": "ریتئون تکنولوژیز", "tier": 3, "spec": "missiles", "country": "آمریکا", "founding_cost": 88000000},
    "almaz_antey_modern": {"name": "آلماز-آنتی (S-400)", "tier": 3, "spec": "missiles", "country": "روسیه", "founding_cost": 88000000},
    "uralvagonzavod_modern": {"name": "اورال‌واگن‌زاود (T-14)", "tier": 3, "spec": "tanks", "country": "روسیه", "founding_cost": 88000000},
    "palantir": {"name": "پالانتیر (هوش مصنوعی نظامی)", "tier": 3, "spec": "drones", "country": "آمریکا", "founding_cost": 90000000},
    "naval_group": {"name": "نووال گروپ (FREMM)", "tier": 3, "spec": "ships", "country": "فرانسه", "founding_cost": 90000000},
    "huntington_ingalls": {"name": "هانتینگتون اینگالز", "tier": 3, "spec": "ships", "country": "آمریکا", "founding_cost": 95000000},
    "sevmash": {"name": "سِوْماش (Borei)", "tier": 3, "spec": "ships", "country": "روسیه", "founding_cost": 95000000},
    "northrop_grumman": {"name": "نورثروپ گرومن (B-21)", "tier": 3, "spec": "aircraft", "country": "آمریکا", "founding_cost": 95000000},
    "sukhoi_modern": {"name": "سوخو (Su-57)", "tier": 3, "spec": "aircraft", "country": "روسیه", "founding_cost": 100000000},
    "lockheed_martin": {"name": "لاکهید مارتین (F-35/F-22)", "tier": 3, "spec": "aircraft", "country": "آمریکا", "founding_cost": 100000000},
}

MILITARY_RECIPES = {
    "small_arms": {"input": {"steel": 10, "electronics": 5}, "output": {"small_arms": 50}, "power": 1},
    "tanks": {"input": {"steel": 20, "electronics": 10, "aluminum": 5}, "output": {"tanks": 5}, "power": 10},
    "aircraft": {"input": {"aluminum": 15, "titanium": 10, "electronics": 5}, "output": {"aircraft": 3}, "power": 20},
    "missiles": {"input": {"tnt": 5, "electronics": 10, "aluminum": 5}, "output": {"missiles": 4}, "power": 30},
    "drones": {"input": {"electronics": 10, "rare_earth": 5, "aluminum": 5}, "output": {"drones": 6}, "power": 15},
    "ships": {"input": {"steel": 50, "aluminum": 20, "electronics": 10}, "output": {"ships": 1}, "power": 100},
    "artillery": {"input": {"steel": 15, "chemicals": 10}, "output": {"artillery": 8}, "power": 15},
}

EQUIPMENT_NAMES = {
    "small_arms": "🔫 سلاح سبک", "tanks": "🛡 تانک", "aircraft": "✈️ هواپیما",
    "missiles": "🚀 موشک", "drones": "🛸 پهپاد", "ships": "🚢 ناو", "artillery": "💥 توپخانه"
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
    if d < 0:
        return f"🔴 بدهی {fmt_money(-amount)}"
    if d >= 1_000_000_000: return f"{d/1_000_000_000:.2f} میلیارد دلار"
    if d >= 1_000_000: return f"{d/1_000_000:.1f} میلیون دلار"
    if d >= 1_000: return f"{d/1_000:.0f} هزار دلار"
    return f"{d:.0f} دلار"

def fmt_date(year, month, day):
    months = ["ژانویه", "فوریه", "مارس", "آپریل", "مه", "ژوئن", 
              "ژوئیه", "اوت", "سپتامبر", "اکتبر", "نوامبر", "دسامبر"]
    return f"{day} {months[month-1]} {year}"

async def get_temp(uid):
    async with pool.acquire() as conn:
        row = await conn.fetchval("SELECT state_json FROM user_temp_state WHERE user_id = $1", uid)
        return json.loads(row) if row else {}

async def set_temp(uid, data):
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO user_temp_state (user_id, state_json) VALUES ($1, $2) ON CONFLICT (user_id) DO UPDATE SET state_json = $2",
            uid, json.dumps(data)
        )

async def del_temp(uid):
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM user_temp_state WHERE user_id = $1", uid)

async def get_free_build_workers(uid):
    async with pool.acquire() as conn:
        s = await conn.fetchrow("SELECT population, infrastructure_budget FROM country_stats WHERE user_id = $1", uid)
        if not s:
            return 0
        inf_b = (s["infrastructure_budget"] or 0) / 100.0
        build_rate = 0.02 + (inf_b * 0.005)
        max_build_workers = int(s["population"] * build_rate)
        await conn.execute("DELETE FROM worker_cooldowns WHERE release_time <= NOW()")
        busy = await conn.fetchval("SELECT COALESCE(SUM(workers), 0) FROM worker_cooldowns WHERE user_id = $1", uid)
    return max(0, max_build_workers - busy)

async def init_db():
    global pool
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=3, command_timeout=60)
    async with pool.acquire() as conn:
        await conn.execute("CREATE TABLE IF NOT EXISTS countries (user_id BIGINT PRIMARY KEY, username TEXT, name TEXT, leader TEXT, age INT, reign TEXT, gov TEXT, gov_sub TEXT, religion TEXT, rel_sub TEXT, expert TEXT, map_region TEXT, flag_id TEXT, status TEXT, happiness INT, science TEXT, ban_reason TEXT)")
        await conn.execute("CREATE TABLE IF NOT EXISTS pending (user_id BIGINT PRIMARY KEY, username TEXT, name TEXT, leader TEXT, age INT, reign TEXT, gov TEXT, gov_sub TEXT, religion TEXT, rel_sub TEXT, expert TEXT, map_region TEXT, flag_id TEXT)")
        await conn.execute("CREATE TABLE IF NOT EXISTS spam_banned (user_id BIGINT PRIMARY KEY)")
        await conn.execute("CREATE TABLE IF NOT EXISTS user_temp_state (user_id BIGINT PRIMARY KEY, state_json TEXT)")
        await conn.execute("CREATE TABLE IF NOT EXISTS pending_cities (user_id BIGINT PRIMARY KEY, city_data TEXT)")
        await conn.execute("CREATE TABLE IF NOT EXISTS game_state (id INT PRIMARY KEY DEFAULT 1, current_year INT DEFAULT 2075, current_month INT DEFAULT 9, current_day INT DEFAULT 1, total_turns INT DEFAULT 0, last_update TIMESTAMP DEFAULT NOW())")
        await conn.execute("CREATE TABLE IF NOT EXISTS country_stats (user_id BIGINT PRIMARY KEY, gdp BIGINT DEFAULT 500000, treasury BIGINT DEFAULT 150000, population BIGINT DEFAULT 15000000, tax_rate INT DEFAULT 0, infrastructure INT DEFAULT 25, happiness INT DEFAULT 60, science_base INT DEFAULT 10, science_applied INT DEFAULT 10, science_military INT DEFAULT 10, science_space INT DEFAULT 5, research_budget INT DEFAULT 0, military_budget INT DEFAULT 0, education_budget INT DEFAULT 0, infrastructure_budget INT DEFAULT 0, welfare_budget INT DEFAULT 0, army INT DEFAULT 0, unemployment INT DEFAULT 0, last_build_time TIMESTAMP DEFAULT NULL)")
        await conn.execute("CREATE TABLE IF NOT EXISTS cities (id SERIAL PRIMARY KEY, user_id BIGINT, name TEXT, area TEXT)")
        await conn.execute("CREATE TABLE IF NOT EXISTS city_zones (id SERIAL PRIMARY KEY, user_id BIGINT, city_id INT, zone_type TEXT, name TEXT, size TEXT, capacity INT, used INT DEFAULT 0)")
        await conn.execute("CREATE TABLE IF NOT EXISTS zone_buildings (id SERIAL PRIMARY KEY, zone_id INT, building_key TEXT)")
        await conn.execute("CREATE TABLE IF NOT EXISTS country_resources (user_id BIGINT PRIMARY KEY, wheat BIGINT DEFAULT 0, iron_ore BIGINT DEFAULT 0, bauxite BIGINT DEFAULT 0, copper_ore BIGINT DEFAULT 0, titanium_ore BIGINT DEFAULT 0, gold BIGINT DEFAULT 0, uranium BIGINT DEFAULT 0, rare_earth BIGINT DEFAULT 0, crude_oil BIGINT DEFAULT 0, steel BIGINT DEFAULT 0, aluminum BIGINT DEFAULT 0, copper BIGINT DEFAULT 0, titanium BIGINT DEFAULT 0, power BIGINT DEFAULT 0, chemicals BIGINT DEFAULT 0, explosives_base BIGINT DEFAULT 0, car_parts BIGINT DEFAULT 0, aero_parts BIGINT DEFAULT 0, electronics BIGINT DEFAULT 0, tnt BIGINT DEFAULT 0)")
        await conn.execute("CREATE TABLE IF NOT EXISTS resource_capacities (user_id BIGINT PRIMARY KEY, wheat BIGINT DEFAULT 1000000, iron_ore BIGINT DEFAULT 500000, bauxite BIGINT DEFAULT 500000, copper_ore BIGINT DEFAULT 500000, titanium_ore BIGINT DEFAULT 500000, gold BIGINT DEFAULT 100000, uranium BIGINT DEFAULT 100000, rare_earth BIGINT DEFAULT 100000, crude_oil BIGINT DEFAULT 1000000, steel BIGINT DEFAULT 500000, aluminum BIGINT DEFAULT 500000, copper BIGINT DEFAULT 500000, titanium BIGINT DEFAULT 500000, power BIGINT DEFAULT 1000000, chemicals BIGINT DEFAULT 500000, explosives_base BIGINT DEFAULT 500000, car_parts BIGINT DEFAULT 100000, aero_parts BIGINT DEFAULT 100000, electronics BIGINT DEFAULT 100000, tnt BIGINT DEFAULT 50000)")
        
        await conn.execute("ALTER TABLE cities ADD COLUMN IF NOT EXISTS area TEXT")
        await conn.execute("ALTER TABLE country_stats ADD COLUMN IF NOT EXISTS last_build_time TIMESTAMP DEFAULT NULL")
        await conn.execute("ALTER TABLE country_resources DROP COLUMN IF EXISTS water")
        await conn.execute("ALTER TABLE resource_capacities DROP COLUMN IF EXISTS water")
        
        await conn.execute("CREATE TABLE IF NOT EXISTS exchange_offers (id SERIAL PRIMARY KEY, seller_id BIGINT, resource TEXT, amount BIGINT, price_per_unit BIGINT)")
        await conn.execute("CREATE TABLE IF NOT EXISTS military_companies (id SERIAL PRIMARY KEY, user_id BIGINT, company_key TEXT, custom_name TEXT, level INT DEFAULT 1)")
        await conn.execute("CREATE TABLE IF NOT EXISTS country_equipment (user_id BIGINT PRIMARY KEY, small_arms BIGINT DEFAULT 0, tanks BIGINT DEFAULT 0, aircraft BIGINT DEFAULT 0, missiles BIGINT DEFAULT 0, drones BIGINT DEFAULT 0, ships BIGINT DEFAULT 0, artillery BIGINT DEFAULT 0)")
        await conn.execute("CREATE TABLE IF NOT EXISTS worker_cooldowns (id SERIAL PRIMARY KEY, user_id BIGINT, workers INT, release_time TIMESTAMP)")
        
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
        await conn.execute("INSERT INTO country_equipment (user_id) VALUES ($1) ON CONFLICT DO NOTHING", uid)

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
        await conn.execute("DELETE FROM pending_cities WHERE user_id=$1", uid)
        await conn.execute("DELETE FROM military_companies WHERE user_id=$1", uid)
        await conn.execute("DELETE FROM country_equipment WHERE user_id=$1", uid)
        await conn.execute("DELETE FROM worker_cooldowns WHERE user_id=$1", uid)
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
        r = await conn.fetchrow("SELECT current_year, current_month, current_day, total_turns FROM game_state WHERE id=1")
        return {"year": r["current_year"], "month": r["current_month"], "day": r["current_day"], "turns": r["total_turns"]}

async def set_commands(application):
    cmds = [
        BotCommand("start", "شروع / ثبت کشور"),
        BotCommand("country", "پروفایل کشور"),
        BotCommand("economy", "مدیریت بودجه"),
        BotCommand("tax", "مدیریت مالیات"),
        BotCommand("military", "نیروهای نظامی و پیمانکار"),
        BotCommand("companies", "شرکت‌های صنایع نظامی"),
        BotCommand("science", "مرکز تحقیقات"),
        BotCommand("fire", "اخراج سرباز (مثال: /fire 1000)"),
        BotCommand("date", "تاریخ بازی"),
        BotCommand("cities", "مدیریت شهرها"),
        BotCommand("zones", "مدیریت نواحی"),
        BotCommand("infra", "ساخت زیرساخت"),
        BotCommand("market", "بورس کالا"),
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
            if len(cities) == 0:
                await context.bot.send_message(chat_id, "⚠️ باید ابتدا شهرهای خود را تاسیس کنید.\nدستور: /cities")
            else:
                await context.bot.send_message(chat_id, "✅ کشور شما فعال است. از /economy، /zones و /infra استفاده کنید.")
        elif c["status"] == "banned":
            await context.bot.send_message(chat_id, "🚫 کشور شما مسدود شده است.")
        else:
            await context.bot.send_message(chat_id, "⏳ در انتظار تایید ادمین.")
        return
    await set_temp(uid, {"username": update.effective_user.username or update.effective_user.first_name, "step": "NAME"})
    await context.bot.send_message(chat_id, "🏛️ نام کشور خود را وارد کنید:")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await del_temp(update.effective_user.id)
    await update.message.reply_text("❌ لغو شد.")

async def date_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    gd = await get_game_date()
    await context.bot.send_message(update.effective_chat.id, f"📅 تاریخ بازی: {fmt_date(gd['year'], gd['month'], gd['day'])}\n🔄 تعداد نوبت‌ها: {gd['turns']}")

async def country_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    c = await get_country(uid)
    if not c:
        return
    s = await get_stats(uid)
    if not s:
        return
    await context.bot.send_message(
        update.effective_chat.id,
        f"🏛️ کشور: {c['name']}\n"
        f"📍 محل استقرار: {c.get('map_region', '—')}\n"
        f"👤 رهبر: {c['leader']}\n"
        f"⚙️ حکومت: {c['gov_sub']}\n"
        f"☪️ دین: {c['religion']}\n"
        f"🏭 تخصص: {c['expert']}\n\n"
        f"👥 جمعیت: {s['population']:,}\n"
        f"🎖 ارتش: {s['army']:,}\n"
        f"💸 نرخ مالیات: {s['tax_rate']}٪\n"
        f"😊 رضایت مردمی: {s['happiness']}٪\n"
        f"💰 خزانه: {fmt_money(s['treasury'])}\n"
        f"📈 GDP: {fmt_money(s['gdp'])}",
        parse_mode="Markdown",
    )

async def economy_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    c = await get_country(uid)
    if not c or c["status"] != "approved":
        return
    s = await get_stats(uid)
    if s["treasury"] == 150000 and s["military_budget"] == 0 and s["research_budget"] == 0:
        await set_temp(uid, {"step": "BUDGET_SET", "mil": 0, "sci": 0, "wel": 0, "inf": 0})
        await show_budget_panel(update.effective_chat.id, context, await get_temp(uid))
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

async def military_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    c = await get_country(uid)
    if not c or c["status"] != "approved":
        return
    s = await get_stats(uid)
    if not s:
        return
    mil_b = s["military_budget"] / 100.0
    recruit_rate = 0.2 + (mil_b * 1.0) 
    max_army = int(s["population"] * (recruit_rate / 100.0))
    inf_b = s["infrastructure_budget"] / 100.0
    worker_rate = 12.0 + (inf_b * 1.0)
    max_workers = int(s["population"] * (worker_rate / 100.0))
    build_rate = 0.02 + (inf_b * 0.005)
    max_build_workers = int(s["population"] * build_rate)
    free_build_workers = await get_free_build_workers(uid)
    
    text = (
        f"🪖 *نیروهای نظامی {c['name']}*\n\n"
        f"👥 جمعیت کل: {s['population']:,}\n"
        f"🎖 سربازان فعلی: {s['army']:,}\n"
        f"📊 نرخ جذب پایه: ۰.۲٪\n"
        f"💰 بودجه نظامی: {s['military_budget']}٪ (نرخ جذب نهایی: {recruit_rate:.2f}٪)\n"
        f"⚔️ حداکثر ظرفیت ارتش: {max_army:,}\n\n"
        f"👷‍♂️ *نیروی کار (تولیدی):*\n"
        f"📈 نرخ کارگر: {worker_rate:.2f}٪ از جمعیت\n"
        f"🔨 حداکثر کارگر در دسترس: {max_workers:,}\n\n"
        f"👷‍♂️ *پیمانکاران ساخت‌وساز:*\n"
        f"📈 ظرفیت کل: {max_build_workers:,}\n"
        f"🟢 آزاد فعلی: {free_build_workers:,}\n\n"
        f"⚠️ _حقوق ماهانه هر سرباز ۱,۰۰۰ دلار است._"
    )
    await context.bot.send_message(update.effective_chat.id, text, parse_mode="Markdown")

async def fire_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("⚠️ برای اخراج سرباز بنویس: `/fire 1000` (تعداد)")
        return
    amount = int(context.args[0])
    s = await get_stats(uid)
    if s["army"] >= amount:
        async with pool.acquire() as conn:
            await conn.execute("UPDATE country_stats SET army = army - $1 WHERE user_id = $2", amount, uid)
        await update.message.reply_text(f"✅ {amount:,} سرباز اخراج شدند.")
    else:
        await update.message.reply_text("❌ تعداد سربازان شما کمتر از این عدد است.")

async def tax_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    c = await get_country(uid)
    if not c or c["status"] != "approved":
        return
    s = await get_stats(uid)
    
    text = (
        f"💸 *مدیریت مالیات {c['name']}*\n\n"
        f"📊 نرخ مالیات فعلی: {s['tax_rate']}٪\n"
        f"😊 رضایت مردمی: {s['happiness']}٪\n\n"
        f"⚠️ *راهنما:*\n"
        f"• مالیات زیر ۱۰٪: رضایت بالا می‌ره\n"
        f"• مالیات بالای ۱۵٪: رضایت کم می‌شه\n"
        f"• رضایت زیر ۳۰٪: شورش و ضربه اقتصادی\n"
        f"• رضایت زیر ۱۵٪: احتمال انقلاب!\n\n"
        f"نرخ مالیات جدید را انتخاب کنید:"
    )
    rows = []
    row = []
    for t in [0, 5, 10, 15, 20, 25, 30]:
        row.append(InlineKeyboardButton(f"{t}٪", callback_data=f"settax_{t}"))
        if len(row) == 4:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    await context.bot.send_message(update.effective_chat.id, text, parse_mode="Markdown", reply_markup=kb(rows))

async def science_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    c = await get_country(uid)
    if not c or c["status"] != "approved":
        return
    s = await get_stats(uid)
    if not s:
        return
        
    current_sci = s["science_base"]
    sci_b = s["research_budget"] / 100.0
    sci_growth = 0.003 + sci_b * 0.05
    growth_percent = sci_growth * 100
    
    if current_sci >= 100:
        next_tier = "حداکثر سطح (Tier 3)"
        progress_bar = "🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩 100%"
        remaining_text = "شما به بالاترین سطح فناوری رسیده‌اید!"
    elif current_sci >= 50:
        next_tier = "سطح ۳ (علم ۱۰۰)"
        needed = 100
        percent = int((current_sci / 100) * 100)
        filled = int(percent / 10)
        progress_bar = "🟩" * filled + "⬜️" * (10 - filled) + f" {percent}%"
        turns_left = int((100 - current_sci) / (current_sci * sci_growth)) if sci_growth > 0 else 0
        remaining_text = f"تا باز شدن شرکت‌های سطح ۳: {needed - current_sci} امتیاز علم (حدود {turns_left} نوبت)"
    elif current_sci >= 10:
        next_tier = "سطح ۲ (علم ۵۰)"
        needed = 50
        percent = int((current_sci / 50) * 100)
        filled = int(percent / 10)
        progress_bar = "🟩" * filled + "⬜️" * (10 - filled) + f" {percent}%"
        turns_left = int((50 - current_sci) / (current_sci * sci_growth)) if sci_growth > 0 else 0
        remaining_text = f"تا باز شدن شرکت‌های سطح ۲: {needed - current_sci} امتیاز علم (حدود {turns_left} نوبت)"
    else:
        next_tier = "سطح ۱"
        progress_bar = "⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️ 0%"
        remaining_text = "در حال پیشرفت..."

    text = (
        f"🔬 *مرکز تحقیقات و فناوری {c['name']}*\n\n"
        f"📊 امتیاز علم فعلی: *{current_sci}*\n"
        f"📈 رشد فعلی: *{growth_percent:.2f}٪* در هر نوبت\n"
        f"💰 بودجه علمی: {s['research_budget']}٪\n\n"
        f"🎯 سطح بعدی: {next_tier}\n"
        f"[{progress_bar}]\n"
        f"💡 {remaining_text}\n\n"
        f"🏢 *شرکت‌های در دسترس:*\n"
    )
    
    available_companies = []
    for key, comp in MILITARY_COMPANIES.items():
        if comp["tier"] == 1 and current_sci >= 10:
            available_companies.append(comp["name"])
        elif comp["tier"] == 2 and current_sci >= 50:
            available_companies.append(comp["name"])
        elif comp["tier"] == 3 and current_sci >= 100:
            available_companies.append(comp["name"])
            
    if available_companies:
        text += "\n".join([f"✅ {name}" for name in available_companies[:10]])
        if len(available_companies) > 10:
            text += f"\n... و {len(available_companies) - 10} شرکت دیگر"
    else:
        text += "هنوز هیچ شرکتی باز نکرده‌اید."
        
    await context.bot.send_message(update.effective_chat.id, text, parse_mode="Markdown")

async def cities_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    c = await get_country(uid)
    if not c or c["status"] != "approved":
        return
    cities = await get_cities(uid)
    if len(cities) > 0:
        txt = "🏙️ شهرهای شما:\n\n" + "\n".join(f"🔹 {city['name']} (مساحت: {city.get('area', 'نامشخص')})" for city in cities)
        await context.bot.send_message(update.effective_chat.id, txt)
        return
    await set_temp(uid, {"step": "CITY_COUNT"})
    await context.bot.send_message(update.effective_chat.id, "🏙️ چه تعداد شهر می‌خواهید تاسیس کنید؟ (عددی بین ۳ تا ۱۵ را بفرستید):")

async def zones_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    cities = await get_cities(uid)
    if len(cities) == 0:
        await context.bot.send_message(update.effective_chat.id, "❌ ابتدا باید شهر بسازید. /cities")
        return
    rows = [[InlineKeyboardButton(f"🏙️ {city['name']}", callback_data=f"city_view_{city['id']}")] for city in cities]
    await context.bot.send_message(update.effective_chat.id, "🏙️ یک شهر برای مدیریت نواحی انتخاب کنید:", reply_markup=kb(rows))

async def infra_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    cities = await get_cities(uid)
    if len(cities) == 0:
        await context.bot.send_message(update.effective_chat.id, "❌ ابتدا باید شهر بسازید. /cities")
        return
    rows = [[InlineKeyboardButton(f"🏙️ {city['name']}", callback_data=f"infra_city_{city['id']}")] for city in cities]
    await context.bot.send_message(update.effective_chat.id, "🏗️ یک شهر برای ساخت زیرساخت انتخاب کنید:", reply_markup=kb(rows))

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

async def market_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    c = await get_country(uid)
    if not c or c["status"] != "approved":
        return
    
    text = "📈 *بورس کالای کشورها*\n\nاینجا می‌تونی منابع خودت رو بفروشی، یا منابع دیگران رو بخری."
    rows = [
        [InlineKeyboardButton("🛒 مشاهده کالاهای موجود (خرید)", callback_data="mkt_list_0")],
        [InlineKeyboardButton("💰 ثبت آگهی فروش", callback_data="mkt_sell_menu")]
    ]
    await context.bot.send_message(update.effective_chat.id, text, parse_mode="Markdown", reply_markup=kb(rows))

async def show_exchange_list(chat_id, msg_id, context, uid, page):
    per_page = 5
    offset = page * per_page
    
    async with pool.acquire() as conn:
        total = await conn.fetchval("SELECT COUNT(*) FROM exchange_offers")
        offers = await conn.fetch(
            "SELECT * FROM exchange_offers ORDER BY id DESC LIMIT $1 OFFSET $2",
            per_page, offset
        )
    
    if not offers:
        text = "📭 در حال حاضر هیچ کالایی برای فروش در بورس نیست."
        try:
            await context.bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=text, reply_markup=kb([[InlineKeyboardButton("🔙 بازگشت", callback_data="mkt_back")]]))
        except Exception:
            pass
        return

    text = "📈 *بورس کالا:*\n\n"
    buttons = []
    for o in offers:
        seller = await get_country(o["seller_id"])
        seller_name = seller["name"] if seller else "ناشناس"
        res_name = RESOURCES.get(o["resource"], o["resource"])
        price = o["price_per_unit"]
        text += f"🔸 {o['amount']:,} عدد {res_name}\n"
        text += f"   💵 قیمت هر واحد: {fmt_money(price)}\n"
        text += f"   👤 فروشنده: {seller_name}\n\n"
        
        buttons.append([InlineKeyboardButton(
            f"خرید {o['amount']} {res_name} (هر واحد {fmt_money(price)})", 
            callback_data=f"mkt_buyoffer_{o['id']}"
        )])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ قبلی", callback_data=f"mkt_list_{page-1}"))
    nav.append(InlineKeyboardButton("🔙 بازگشت به بورس", callback_data="mkt_back"))
    if offset + per_page < total:
        nav.append(InlineKeyboardButton("➡️ بعدی", callback_data=f"mkt_list_{page+1}"))
    buttons.append(nav)
    
    try:
        await context.bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=text, parse_mode="Markdown", reply_markup=kb(buttons))
    except Exception:
        pass

async def companies_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    c = await get_country(uid)
    if not c or c["status"] != "approved":
        return
    s = await get_stats(uid)
    
    async with pool.acquire() as conn:
        my_companies = await conn.fetch("SELECT * FROM military_companies WHERE user_id = $1", uid)
        
    text = f"🏭 *مجتمع صنایع نظامی {c['name']}*\n\n"
    text += f"🔬 سطح علم پایه: {s['science_base']}\n\n"
    
    rows = []
    if my_companies:
        text += "شرکت‌های تحت مالکیت شما:\n"
        for mc in my_companies:
            base = MILITARY_COMPANIES.get(mc["company_key"], {})
            disp_name = mc["custom_name"] or base.get("name", "ناشناس")
            spec = EQUIPMENT_NAMES.get(base.get("spec"), "نامشخص")
            text += f"🏢 {disp_name} - تخصص: {spec} (سطح {mc['level']})\n"
            rows.append([InlineKeyboardButton(f"⚙️ مدیریت {disp_name}", callback_data=f"comp_manage_{mc['id']}")])
    else:
        text += "شما هنوز هیچ شرکت نظامی ندارید."
        
    rows.append([InlineKeyboardButton("➕ تاسیس شرکت جدید", callback_data="comp_new")])
    await context.bot.send_message(update.effective_chat.id, text, parse_mode="Markdown", reply_markup=kb(rows))

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

# ---------- CALLBACK HANDLER ----------

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cb = update.callback_query
    data = cb.data or ""
    uid = cb.from_user.id
    chat_id = cb.message.chat.id
    msg_id = cb.message.message_id
    t = await get_temp(uid)
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

    # ----- TAX -----
    if data.startswith("settax_"):
        try: new_tax = int(data.split("_")[1])
        except: return
        if new_tax < 0 or new_tax > 30:
            await cb.answer("❌ نرخ مالیات باید بین ۰ تا ۳۰ باشد!", show_alert=True)
            return
        async with pool.acquire() as conn:
            await conn.execute("UPDATE country_stats SET tax_rate = $1 WHERE user_id = $2", new_tax, uid)
        
        s = await get_stats(uid)
        c = await get_country(uid)
        text = (
            f"💸 *مدیریت مالیات {c['name']}*\n\n"
            f"📊 نرخ مالیات فعلی: {s['tax_rate']}٪\n"
            f"😊 رضایت مردمی: {s['happiness']}٪\n\n"
            f"⚠️ *راهنما:*\n"
            f"• مالیات زیر ۱۰٪: رضایت بالا می‌ره\n"
            f"• مالیات بالای ۱۵٪: رضایت کم می‌شه\n"
            f"• رضایت زیر ۳۰٪: شورش و ضربه اقتصادی\n"
            f"• رضایت زیر ۱۵٪: احتمال انقلاب!\n\n"
            f"نرخ مالیات جدید را انتخاب کنید:"
        )
        rows = []
        row = []
        for t in [0, 5, 10, 15, 20, 25, 30]:
            row.append(InlineKeyboardButton(f"{t}٪", callback_data=f"settax_{t}"))
            if len(row) == 4:
                rows.append(row)
                row = []
        if row:
            rows.append(row)
        await edit(text, kb(rows))
        await cb.answer(f"✅ نرخ مالیات به {new_tax}٪ تغییر یافت.")
        return

    # ----- BUDGET -----
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
            await del_temp(uid)
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
        await set_temp(uid, t)
        await show_budget_panel(chat_id, context, t)
        return

    # ----- REGISTRATION FLOW -----
    if data.startswith("reign_"):
        mp = {"reign_5": "۵ سال", "reign_10": "۱۰ سال", "reign_20": "۲۰ سال", "reign_30": "۳۰ سال", "reign_life": "مادام‌العمر"}
        t["reign"] = mp.get(data, "۱۰ سال")
        t["step"] = "GOV"
        await set_temp(uid, t)
        rows = [[InlineKeyboardButton(v, callback_data=f"gov_{k}")] for k, v in GOVS.items()]
        await edit("⚙️ *حکومت*:", kb(rows))
        return

    if data.startswith("gov_") and not data.startswith("govsub_"):
        gk = data.replace("gov_", "")
        if gk not in GOVS:
            return
        t["gov"] = GOVS[gk]
        t["step"] = "GOV_SUB"
        await set_temp(uid, t)
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
        await set_temp(uid, t)
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
            await set_temp(uid, t)
            rows = [[InlineKeyboardButton(v, callback_data=f"exp_{k}")] for k, v in EXPERTS.items()]
            await edit("🏭 *تخصص*:", kb(rows))
            return
        t["step"] = "REL_SUB"
        await set_temp(uid, t)
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
        await set_temp(uid, t)
        rows = [[InlineKeyboardButton(v, callback_data=f"exp_{k}")] for k, v in EXPERTS.items()]
        await edit("🏭 *تخصص*:", kb(rows))
        return

    if data.startswith("exp_"):
        ek = data.replace("exp_", "")
        if ek not in EXPERTS:
            return
        t["expert"] = EXPERTS[ek]
        t["step"] = "MAP_REGION"
        await set_temp(uid, t)
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
        await set_temp(uid, t)
        await edit(f"✅ منطقه جهانی: *{code}*\n\n🖼️ حالا عکس پرچم کشورت رو بفرست:")
        return

    # ----- MARKET / BOURSE -----
    if data == "mkt_back":
        text = "📈 *بورس کالای کشورها*\n\nاینجا می‌تونی منابع خودت رو بفروشی، یا منابع دیگران رو بخری."
        rows = [
            [InlineKeyboardButton("🛒 مشاهده کالاهای موجود (خرید)", callback_data="mkt_list_0")],
            [InlineKeyboardButton("💰 ثبت آگهی فروش", callback_data="mkt_sell_menu")]
        ]
        await edit(text, kb(rows))
        return

    if data.startswith("mkt_list_"):
        try: page = int(data.split("_")[2])
        except: page = 0
        await show_exchange_list(chat_id, msg_id, context, uid, page)
        return

    if data == "mkt_sell_menu":
        res = await get_resources(uid)
        if not res:
            return
        rows = []
        for k, v in res.items():
            if k != "user_id" and v > 0:
                rows.append([InlineKeyboardButton(f"فروش {RESOURCES.get(k, k)} (موجودی: {v:,})", callback_data=f"mkt_sellres_{k}")])
        rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="mkt_back")])
        await edit("💰 *ثبت آگهی فروش*\n\nچه منبعی را می‌خواهید بفروشید؟", kb(rows))
        return

    if data.startswith("mkt_sellres_"):
        res_key = data[len("mkt_sellres_"):]
        t["sell_res"] = res_key
        t["step"] = "SELL_AMOUNT"
        await set_temp(uid, t)
        await edit(f"📝 چه تعداد *{RESOURCES.get(res_key, res_key)}* را می‌خواهید بفروشید؟\n(عدد را بفرستید)")
        return

    if data.startswith("mkt_buyoffer_"):
        try: offer_id = int(data.split("_")[2])
        except: return
        
        async with pool.acquire() as conn:
            offer = await conn.fetchrow("SELECT * FROM exchange_offers WHERE id = $1", offer_id)
        
        if not offer:
            await cb.answer("❌ این آگهی حذف شده است.", show_alert=True)
            return
            
        if offer["seller_id"] == uid:
            await cb.answer("❌ شما نمی‌توانید کالای خودتان را بخرید!", show_alert=True)
            return

        total_cost = offer["amount"] * offer["price_per_unit"]
        s = await get_stats(uid)
        
        if s["treasury"] < total_cost:
            await cb.answer(f"❌ خزانه کافی نیست! نیاز: {fmt_money(total_cost)}", show_alert=True)
            return

        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("UPDATE country_stats SET treasury = treasury - $1 WHERE user_id = $2", total_cost, uid)
                await conn.execute(f"UPDATE country_resources SET {offer['resource']} = {offer['resource']} + $1 WHERE user_id = $2", offer["amount"], uid)
                await conn.execute("UPDATE country_stats SET treasury = treasury + $1 WHERE user_id = $2", total_cost, offer["seller_id"])
                await conn.execute("DELETE FROM exchange_offers WHERE id = $1", offer_id)
        
        await cb.answer(f"✅ با موفقیت {offer['amount']} عدد {RESOURCES.get(offer['resource'])} خریدید!", show_alert=True)
        await show_exchange_list(chat_id, msg_id, context, uid, 0)
        return

    # ----- COMPANIES -----
    if data == "comp_new":
        s = await get_stats(uid)
        max_tier = 1
        if s["science_base"] >= 100:
            max_tier = 3
        elif s["science_base"] >= 50:
            max_tier = 2
            
        rows = []
        if max_tier >= 1:
            rows.append([InlineKeyboardButton(f"🪖 سطح ۱ - {TIER_INFO[1]['name']}", callback_data="comp_tier_1_0")])
        if max_tier >= 2:
            rows.append([InlineKeyboardButton(f"⚔️ سطح ۲ - {TIER_INFO[2]['name']}", callback_data="comp_tier_2_0")])
        if max_tier >= 3:
            rows.append([InlineKeyboardButton(f"🚀 سطح ۳ - {TIER_INFO[3]['name']}", callback_data="comp_tier_3_0")])
        rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="comp_back")])
        
        text = f"🏭 *تاسیس شرکت نظامی*\n\n🔬 سطح علم شما: {s['science_base']}\n\nیک سطح فناوری را انتخاب کنید:"
        await edit(text, kb(rows))
        return

    if data.startswith("comp_tier_"):
        parts = data.split("_")
        try:
            tier = int(parts[2])
            page = int(parts[3])
        except:
            return
        await show_company_tier(chat_id, msg_id, context, uid, tier, page)
        return

    if data.startswith("comp_found_"):
        comp_key = data[len("comp_found_"):]
        comp = MILITARY_COMPANIES.get(comp_key)
        if not comp:
            return
            
        cost = comp.get("founding_cost", 50000)
        s = await get_stats(uid)
        if s["treasury"] < cost:
            await cb.answer(f"❌ خزانه کافی نیست!\nهزینه تاسیس: {fmt_money(cost)}", show_alert=True)
            return
            
        async with pool.acquire() as conn:
            exists = await conn.fetchval("SELECT COUNT(*) FROM military_companies WHERE user_id = $1 AND company_key = $2", uid, comp_key)
            if exists > 0:
                await cb.answer("❌ شما قبلاً این شرکت را تاسیس کرده‌اید!", show_alert=True)
                return
                
            await conn.execute("UPDATE country_stats SET treasury = treasury - $1 WHERE user_id = $2", cost, uid)
            await conn.execute("INSERT INTO military_companies (user_id, company_key) VALUES ($1, $2)", uid, comp_key)
            
        await cb.answer(f"✅ {comp['name']} با موفقیت تاسیس شد!", show_alert=True)
        await companies_cmd(update, context)
        return

    if data == "comp_back":
        await companies_cmd(update, context)
        return

    if data.startswith("comp_manage_"):
        try: mc_id = int(data.split("_")[2])
        except: return
        
        async with pool.acquire() as conn:
            mc = await conn.fetchrow("SELECT * FROM military_companies WHERE id = $1 AND user_id = $2", mc_id, uid)
        if not mc:
            await cb.answer("❌ شرکت پیدا نشد!", show_alert=True)
            return
            
        base = MILITARY_COMPANIES.get(mc["company_key"], {})
        spec = base.get("spec")
        recipe = MILITARY_RECIPES.get(spec, {})
        
        text = f"🏢 *مدیریت شرکت: {mc['custom_name'] or base.get('name')}*\n\n"
        text += f"📦 تخصص: {EQUIPMENT_NAMES.get(spec)}\n"
        text += f"🔬 سطح شرکت: {mc['level']}\n\n"
        text += "📋 *فرمول تولید در هر نوبت:*\n"
        for k, v in recipe.get("input", {}).items():
            text += f"  - {RESOURCES.get(k, k)}: {v}\n"
        for k, v in recipe.get("output", {}).items():
            text += f"  - خروجی: {EQUIPMENT_NAMES.get(k)}: {v}\n"
            
        rows = [
            [InlineKeyboardButton("✏️ تغییر نام شرکت", callback_data=f"comp_rename_{mc['id']}")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="comp_back")]
        ]
        await edit(text, kb(rows))
        return

    if data.startswith("comp_rename_"):
        try: mc_id = int(data.split("_")[2])
        except: return
        
        t["step"] = "RENAME_COMPANY"
        t["target_company_id"] = mc_id
        await set_temp(uid, t)
        await edit("✏️ نام جدید شرکت خود را وارد کنید:\n(نام انگلیسی یا فارسی)")
        return

    # ----- ZONES -----
    if data.startswith("city_view_"):
        cid = int(data.split("_")[2])
        regs = await get_city_zones(cid)
        text = "🏙️ نواحی شهر:\n\n" + ("\n".join(f"📍 {r['name']} ({r['used']}/{r['capacity']})" for r in regs) if regs else "خالی")
        rows = []
        if len(regs) < 3:
            rows.append([InlineKeyboardButton("➕ تاسیس ناحیه جدید", callback_data=f"newreg_{cid}")])
        rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="back_cities")])
        await edit(text, kb(rows))
        return

    if data.startswith("newreg_") and not data.startswith("newreg_type_") and not data.startswith("newreg_size_"):
        cid = int(data.split("_")[1])
        t["newreg_city"] = cid
        await set_temp(uid, t)
        rows = [[InlineKeyboardButton(v, callback_data=f"newreg_type_{k}")] for k, v in ZONE_TYPES.items()]
        rows.append([InlineKeyboardButton("🔙 انصراف", callback_data="back_cities")])
        await edit("🏗️ نوع ناحیه جدید:", kb(rows))
        return

    if data.startswith("newreg_type_"):
        rt = data[len("newreg_type_"):]
        if rt not in ZONE_TYPES:
            return
        t["newreg_type"] = rt
        await set_temp(uid, t)
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
        await del_temp(uid)
        await edit("✅ ناحیه ساخته شد! از /zones برای مدیریت استفاده کنید.")
        return

    if data == "back_cities":
        cities = await get_cities(uid)
        if len(cities) == 0:
            await edit("❌ ابتدا باید شهر بسازید. /cities")
            return
        rows = [[InlineKeyboardButton(f"🏙️ {city['name']}", callback_data=f"city_view_{city['id']}")] for city in cities]
        await edit("🏙️ یک شهر برای مدیریت نواحی انتخاب کنید:", kb(rows))
        return

    # ----- INFRASTRUCTURE -----
    if data.startswith("infra_city_"):
        cid = int(data.split("_")[2])
        zones = await get_city_zones(cid)
        if not zones:
            await cb.answer("این شهر هنوز ناحیه‌ای ندارد! ابتدا از /zones ناحیه بسازید.", show_alert=True)
            return
        rows = [[InlineKeyboardButton(f"📍 {r['name']} ({r['used']}/{r['capacity']})", callback_data=f"infra_zone_{r['id']}")] for r in zones]
        rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="back_infra_cities")])
        await edit("🏗️ یک ناحیه برای ساخت زیرساخت انتخاب کنید:", kb(rows))
        return

    if data == "back_infra_cities":
        cities = await get_cities(uid)
        if len(cities) == 0:
            await edit("❌ ابتدا باید شهر بسازید. /cities")
            return
        rows = [[InlineKeyboardButton(f"🏙️ {city['name']}", callback_data=f"infra_city_{city['id']}")] for city in cities]
        await edit("🏗️ یک شهر برای ساخت زیرساخت انتخاب کنید:", kb(rows))
        return

    if data.startswith("infra_zone_"):
        rid = int(data.split("_")[2])
        reg = await get_one_zone(rid, uid)
        if not reg:
            await cb.answer("ناحیه پیدا نشد!", show_alert=True)
            return
        if reg["used"] >= reg["capacity"]:
            await cb.answer("ظرفیت این ناحیه پر است!", show_alert=True)
            return
        avail = [(k, v) for k, v in BUILDINGS.items() if v["type"] == reg["zone_type"]]
        if not avail:
            await cb.answer("زیرساختی برای این نوع ناحیه تعریف نشده!", show_alert=True)
            return
        t["bld_zone_id"] = rid
        await set_temp(uid, t)
        rows = [[InlineKeyboardButton(f"{v['name']} | {fmt_money(v['cost'])}", callback_data=f"infra_make_{k}")] for k, v in avail]
        rows.append([InlineKeyboardButton("🔙 بازگشت به نواحی", callback_data=f"infra_city_{reg['city_id']}")])
        await edit("🏗️ زیرساخت مورد نظر را انتخاب کنید:", kb(rows))
        return

    if data.startswith("infra_make_"):
        bk = data[len("infra_make_"):]
        if bk not in BUILDINGS:
            await cb.answer("زیرساخت نامعتبر!", show_alert=True)
            return
        b = BUILDINGS[bk]
        s = await get_stats(uid)
        
        free_build_workers = await get_free_build_workers(uid)
        required = b.get("build_workers", 5000)
        
        if free_build_workers < required:
            await cb.answer(
                f"⏳ پیمانکار ساخت‌وساز آزاد کافی نیست!\n"
                f"نیاز این بیلد: {required:,} نفر\n"
                f"آزاد شما: {free_build_workers:,} نفر\n\n"
                f"(بقیه پیمانکارها مشغول ساخت قبلی هستند)",
                show_alert=True
            )
            return
        
        if not s or s["treasury"] < b["cost"]:
            await cb.answer("❌ خزانه کافی نیست!", show_alert=True)
            return
        rid = t.get("bld_zone_id")
        if not rid:
            await cb.answer("جلسه منقضی شده، دوباره از /infra شروع کن.", show_alert=True)
            return
            
        async with pool.acquire() as conn:
            await conn.execute("UPDATE country_stats SET treasury = treasury - $1 WHERE user_id = $2", b["cost"], uid)
            await conn.execute("INSERT INTO zone_buildings (zone_id, building_key) VALUES ($1, $2)", rid, bk)
            await conn.execute("UPDATE city_zones SET used = used + 1 WHERE id = $1", rid)
            await conn.execute(
                "INSERT INTO worker_cooldowns (user_id, workers, release_time) VALUES ($1, $2, NOW() + INTERVAL '3 hours')",
                uid, required
            )
        
        await cb.answer(f"✅ ساخته شد! {required:,} پیمانکار برای ۳ ساعت مشغول شدند.", show_alert=True)
        
        reg = await get_one_zone(rid, uid)
        avail = [(k, v) for k, v in BUILDINGS.items() if v["type"] == reg["zone_type"]]
        rows = [[InlineKeyboardButton(f"{v['name']} | {fmt_money(v['cost'])}", callback_data=f"infra_make_{k}")] for k, v in avail]
        rows.append([InlineKeyboardButton("🔙 بازگشت به نواحی", callback_data=f"infra_city_{reg['city_id']}")])
        
        new_free = await get_free_build_workers(uid)
        await edit(f"✅ *{b['name']}* ساخته شد!\n\n"
                   f"👷‍♂️ پیمانکار در حال کار: {required:,}\n"
                   f"⏳ زمان آزادسازی: ۳ ساعت\n"
                   f"🟢 پیمانکار آزاد فعلی: {new_free:,}\n\n"
                   f"می‌توانید زیرساخت بعدی را انتخاب کنید:", kb(rows))
        return

    # ----- ADMIN PANEL -----
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
            await cb.answer("❌ خطای داخلی در خواندن آیدی.", show_alert=True)
            return
        p = await get_pending(tu)
        if not p:
            try:
                await cb.message.delete()
            except Exception:
                pass
            await context.bot.send_message(chat_id, "⚠️ این درخواست قبلاً پردازش شده یا وجود ندارد.")
            return
        if action == "ok":
            await save_country(tu, p)
            await delete_pending(tu)
            try:
                await context.bot.send_message(tu, "🎉 کشور شما تایید شد! حالا از /economy استفاده کنید و سپس /cities برای ساخت شهر.")
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

    if data.startswith("appr_city_") and uid == ADMIN_ID:
        try: tu = int(data.split("_")[2])
        except: return
        async with pool.acquire() as conn:
            row = await conn.fetchval("SELECT city_data FROM pending_cities WHERE user_id = $1", tu)
        if not row:
            await cb.answer("اطلاعات شهرها پیدا نشد.", show_alert=True)
            return
        
        cities_list = json.loads(row)
        await set_temp(uid, {
            "step": "ADMIN_CITY_AREA", 
            "target_uid": tu, 
            "city_list": cities_list, 
            "current_index": 0, 
            "areas": []
        })
        await edit(f"📐 مساحت شهر ۱ را وارد کنید:\n🏙️ *{cities_list[0]}*")
        return

    if data.startswith("rej_city_") and uid == ADMIN_ID:
        try: tu = int(data.split("_")[2])
        except: return
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM pending_cities WHERE user_id = $1", tu)
        try: await context.bot.send_message(tu, "❌ درخواست شهرهای شما رد شد.")
        except: pass
        try: await cb.message.delete()
        except: pass
        await context.bot.send_message(chat_id, "❌ درخواست شهرها رد شد.")
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
            await cb.answer("❌ آیدی نامعتبر.", show_alert=True)
            return
        c = await get_country(tu)
        if not c:
            await cb.answer("❌ این کشور پیدا نشد (شاید حذف شده).", show_alert=True)
            return
        st = "✅ فعال" if c["status"] == "approved" else "🚫 مسدود" if c["status"] == "banned" else "⏳ در انتظار"
        text = (
            f"🏛️ *{c['name']}*\n\n"
            f"📍 محل استقرار: {c.get('map_region', '—')}\n"
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
        await set_temp(uid, {"step": "BAN_REASON", "targetUid": tu})
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
        buttons.append([InlineKeyboardButton(f"🔍 {c['user_id']} - {c['name']}", callback_data=f"adm_view_{c['user_id']}")])
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

async def show_company_tier(chat_id, msg_id, context, uid, tier, page):
    companies = [(k, v) for k, v in MILITARY_COMPANIES.items() if v["tier"] == tier]
    per_page = 6
    start = page * per_page
    end = start + per_page
    page_companies = companies[start:end]
    
    rows = []
    for key, comp in page_companies:
        cost = comp.get("founding_cost", 50000)
        rows.append([InlineKeyboardButton(f"{comp['name']} - {fmt_money(cost)}", callback_data=f"comp_found_{key}")])
    
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ قبلی", callback_data=f"comp_tier_{tier}_{page-1}"))
    nav.append(InlineKeyboardButton("🔙 بازگشت", callback_data="comp_new"))
    if end < len(companies):
        nav.append(InlineKeyboardButton("➡️ بعدی", callback_data=f"comp_tier_{tier}_{page+1}"))
    if nav:
        rows.append(nav)
    
    text = f"🏭 *شرکت‌های سطح {tier} - {TIER_INFO[tier]['name']}*\n\n"
    text += f"صفحه {page+1} از {((len(companies)-1) // per_page) + 1}\n"
    text += f"تعداد شرکت‌ها در این سطح: {len(companies)}"
    
    try:
        await context.bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=text, parse_mode="Markdown", reply_markup=kb(rows))
    except Exception:
        pass

# ---------- MESSAGE HANDLERS ----------

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = (update.message.text or "").strip()
    t = await get_temp(uid)
    if not t:
        return

    if t.get("step") == "NAME":
        if len(text) < 3 or len(text) > 25:
            await update.message.reply_text("❌ ۳ تا ۲۵ حرف:")
            return
        t["name"] = text
        t["step"] = "LEADER"
        await set_temp(uid, t)
        await update.message.reply_text("👤 نام رهبر:")
        
    elif t.get("step") == "LEADER":
        t["leader"] = text
        t["step"] = "AGE"
        await set_temp(uid, t)
        await update.message.reply_text("🎂 سن رهبر (۳۵-۴۵):")
        
    elif t.get("step") == "AGE":
        if not text.isdigit() or not (35 <= int(text) <= 45):
            await update.message.reply_text("عدد بین ۳۵ تا ۴۵:")
            return
        t["age"] = int(text)
        t["step"] = "REIGN"
        await set_temp(uid, t)
        rows = [[
            InlineKeyboardButton("۱۰ سال", callback_data="reign_10"),
            InlineKeyboardButton("۲۰ سال", callback_data="reign_20"),
            InlineKeyboardButton("مادام‌العمر", callback_data="reign_life"),
        ]]
        await update.message.reply_text("⏳ مدت حکومت:", reply_markup=kb(rows))
        
    elif t.get("step") == "CITY_COUNT":
        if not text.isdigit() or not (3 <= int(text) <= 15):
            await update.message.reply_text("❌ لطفاً یک عدد بین ۳ تا ۱۵ وارد کنید:")
            return
        t["city_count"] = int(text)
        t["city_list"] = []
        t["step"] = "CITY_NAME"
        await set_temp(uid, t)
        await update.message.reply_text(f"✅ قرار است {text} شهر بسازید.\nنام شهر شماره ۱ را وارد کنید:")
        
    elif t.get("step") == "CITY_NAME":
        city_list = t.get("city_list", [])
        city_list.append(text)
        t["city_list"] = city_list
        
        if len(city_list) < t["city_count"]:
            t["step"] = "CITY_NAME"
            await set_temp(uid, t)
            await update.message.reply_text(f"✅ ثبت شد. نام شهر شماره {len(city_list)+1} را وارد کنید:")
        else:
            city_names_str = "\n".join([f"🔹 {name}" for name in city_list])
            txt = f"🏙️ *درخواست تاسیس شهرها*\n\n👤 کاربر: @{update.effective_user.username or 'None'}\n🆔 `{uid}`\n\n{city_names_str}"
            btn = [[
                InlineKeyboardButton("✅ تایید و تنظیم مساحت", callback_data=f"appr_city_{uid}"),
                InlineKeyboardButton("❌ رد درخواست", callback_data=f"rej_city_{uid}")
            ]]
            
            async with pool.acquire() as conn:
                await conn.execute(
                    "INSERT INTO pending_cities (user_id, city_data) VALUES ($1, $2) ON CONFLICT (user_id) DO UPDATE SET city_data = $2",
                    uid, json.dumps(city_list)
                )
            
            try:
                await context.bot.send_message(ADMIN_ID, txt, parse_mode="Markdown", reply_markup=kb(btn))
                await update.message.reply_text("⏳ درخواست شهرهای شما برای ادمین ارسال شد. منتظر تایید باشید.")
            except Exception:
                await update.message.reply_text("❌ خطا در ارسال به ادمین.")
            await del_temp(uid)

    elif t.get("step") == "ADMIN_CITY_AREA" and uid == ADMIN_ID:
        cities_list = t["city_list"]
        idx = t["current_index"]
        
        t["areas"].append(text)
        t["current_index"] += 1
        
        if t["current_index"] < len(cities_list):
            await set_temp(uid, t)
            next_city = cities_list[t["current_index"]]
            await update.message.reply_text(f"✅ مساحت ثبت شد.\n\n📐 مساحت شهر {t['current_index']+1} را وارد کنید:\n🏙️ *{next_city}*", parse_mode="Markdown")
        else:
            tu = t["target_uid"]
            areas = t["areas"]
            async with pool.acquire() as conn:
                for cname, carea in zip(cities_list, areas):
                    await conn.execute("INSERT INTO cities (user_id, name, area) VALUES ($1, $2, $3)", tu, cname, carea)
                await conn.execute("DELETE FROM pending_cities WHERE user_id = $1", tu)
            
            try:
                await context.bot.send_message(tu, "🎉 درخواست شهرهای شما تایید شد! حالا از /economy برای تنظیم بودجه یا /zones استفاده کنید.")
            except Exception:
                pass
            await update.message.reply_text("✅ تمام شهرها با موفقیت تایید و ثبت شدند.")
            await del_temp(uid)

    elif t.get("step") == "SELL_AMOUNT":
        if not text.isdigit() or int(text) <= 0:
            await update.message.reply_text("❌ لطفاً یک عدد معتبر وارد کنید:")
            return
        amount = int(text)
        res_key = t.get("sell_res")
        res = await get_resources(uid)
        if res.get(res_key, 0) < amount:
            await update.message.reply_text(f"❌ شما {amount} عدد {RESOURCES.get(res_key)} ندارید!")
            return
        t["sell_amount"] = amount
        t["step"] = "SELL_PRICE"
        await set_temp(uid, t)
        await update.message.reply_text(f"💵 قیمت هر واحد *{RESOURCES.get(res_key)}* را به دلار وارد کنید:\n(مثلاً 150)", parse_mode="Markdown")

    elif t.get("step") == "SELL_PRICE":
        if not text.isdigit() or int(text) <= 0:
            await update.message.reply_text("❌ لطفاً یک قیمت معتبر (عدد) وارد کنید:")
            return
        price = int(text)
        res_key = t.get("sell_res")
        amount = t.get("sell_amount")
        
        async with pool.acquire() as conn:
            await conn.execute(f"UPDATE country_resources SET {res_key} = {res_key} - $1 WHERE user_id = $2", amount, uid)
            await conn.execute(
                "INSERT INTO exchange_offers (seller_id, resource, amount, price_per_unit) VALUES ($1, $2, $3, $4)",
                uid, res_key, amount, price
            )
        
        await del_temp(uid)
        await update.message.reply_text(f"✅ آگهی فروش {amount:,} عدد {RESOURCES.get(res_key)} با قیمت هر واحد {fmt_money(price)} در بورس ثبت شد.")

    elif t.get("step") == "RENAME_COMPANY":
        mc_id = t.get("target_company_id")
        async with pool.acquire() as conn:
            await conn.execute("UPDATE military_companies SET custom_name = $1 WHERE id = $2 AND user_id = $3", text, mc_id, uid)
        await del_temp(uid)
        await update.message.reply_text(f"✅ نام شرکت با موفقیت به «{text}» تغییر یافت.")

    elif t.get("step") == "BAN_REASON" and uid == ADMIN_ID:
        tu = t.get("targetUid")
        await set_status(tu, "banned", text)
        await del_temp(uid)
        await update.message.reply_text(f"🚫 مسدود شد.\n📝 دلیل: {text}")
        try:
            await context.bot.send_message(tu, f"🚫 کشور شما مسدود شد.\n📝 دلیل: {text}")
        except Exception:
            pass


async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    t = await get_temp(uid)
    if not t or t.get("step") != "FLAG":
        return
    taken = await get_taken_map_regions()
    if t.get("map_region") in taken:
        await del_temp(uid)
        await update.message.reply_text(f"❌ منطقه {t.get('map_region')} همین الان گرفته شد. /start")
        return
    t["flag_id"] = update.message.photo[-1].file_id
    await save_pending(uid, t)
    await del_temp(uid)
    await context.bot.send_message(
        ADMIN_ID, "📥 درخواست جدید ثبت شد!",
        reply_markup=kb([[InlineKeyboardButton("مشاهده", callback_data="adm_pending")]]),
    )
    await update.message.reply_text("⏳ ارسال شد. منتظر تایید.")


# ---------- TURN CYCLE ----------

async def process_turn(force: bool = False) -> bool:
    async with pool.acquire() as conn:
        async with conn.transaction():
            state = await conn.fetchrow(
                "SELECT current_year, current_month, current_day, total_turns, last_update FROM game_state WHERE id=1 FOR UPDATE"
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
                total_workers_needed = 0
                total_income = 0
                pop_gain = 0

                mil_b = (stats.get("military_budget") or 0) / 100.0
                inf_b = (stats.get("infrastructure_budget") or 0) / 100.0
                sci_b = (stats.get("research_budget") or 0) / 100.0
                wel_b = (stats.get("welfare_budget") or 0) / 100.0
                edu_b = (stats.get("education_budget") or 0) / 100.0

                recruit_rate = 0.002 + (mil_b * 0.01) 
                new_army = int(stats["population"] * recruit_rate)
                
                worker_rate = 0.12 + (inf_b * 0.05) 
                max_workers = int(stats["population"] * worker_rate)

                for bkey in bkeys:
                    bdef = BUILDINGS.get(bkey)
                    if bdef:
                        total_workers_needed += bdef.get("workers", 0)

                efficiency = 1.0
                if total_workers_needed > max_workers:
                    efficiency = max_workers / total_workers_needed

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
                        res[k] = res.get(k, 0) + int(v * efficiency)
                        
                    total_income += int(bdef.get("income", 0) * efficiency)
                    pop_gain += bdef.get("pop", 0)

                my_companies = await conn.fetch("SELECT * FROM military_companies WHERE user_id = $1", user_id)
                equip_row = await conn.fetchrow("SELECT * FROM country_equipment WHERE user_id = $1 FOR UPDATE", user_id)
                equip = dict(equip_row) if equip_row else {}
                
                for mc in my_companies:
                    base = MILITARY_COMPANIES.get(mc["company_key"], {})
                    spec = base.get("spec")
                    recipe = MILITARY_RECIPES.get(spec, {})
                    
                    inputs = recipe.get("input", {})
                    if not all(res.get(k, 0) >= v for k, v in inputs.items()):
                        continue
                        
                    for k, v in inputs.items():
                        res[k] = res.get(k, 0) - v
                    for k, v in recipe.get("output", {}).items():
                        equip[k] = equip.get(k, 0) + v
                        
                cols = [k for k in res.keys() if k != "user_id"]
                set_clause = ", ".join(f"{k}=${i+2}" for i, k in enumerate(cols))
                await conn.execute(
                    f"UPDATE country_resources SET {set_clause} WHERE user_id=$1",
                    user_id, *[res[k] for k in cols],
                )
                
                ecols = [k for k in equip.keys() if k != "user_id"]
                eset_clause = ", ".join(f"{k}=${i+2}" for i, k in enumerate(ecols))
                await conn.execute(
                    f"UPDATE country_equipment SET {eset_clause} WHERE user_id=$1",
                    user_id, *[equip[k] for k in ecols],
                )

                gdp_income = int(stats["gdp"] * 0.05)
                tax_income = int(stats["population"] * stats["tax_rate"] * 0.0001)
                
                total_budget_percent = (stats["military_budget"] + stats["research_budget"] + stats["welfare_budget"] + stats["infrastructure_budget"]) / 100.0
                budget_cost = int(stats["gdp"] * total_budget_percent * 0.05)
                
                army_upkeep = int(new_army * 1.0)
                worker_upkeep = int(total_workers_needed * 0.1)
                
                maintenance_cost = 0
                for bkey in bkeys:
                    bdef = BUILDINGS.get(bkey)
                    if bdef and "maintenance" in bdef:
                        maintenance_cost += bdef["maintenance"]

                treasury_delta = (gdp_income * 1000) + (tax_income * 1000) - (budget_cost * 1000) - (army_upkeep * 1000) - (worker_upkeep * 1000) - (maintenance_cost * 1000)

                wheat_needed = stats["population"] // 30000
                wheat_shortage = False
                if res.get("wheat", 0) >= wheat_needed:
                    res["wheat"] -= wheat_needed
                else:
                    res["wheat"] = 0
                    wheat_shortage = True

                pop_growth = 0.005 + wel_b * 0.02 + inf_b * 0.01
                new_pop = int((stats["population"] + pop_gain) * (1 + pop_growth))
                sci_growth = 0.003 + sci_b * 0.05 + edu_b * 0.02
                new_sci_base = int(stats.get("science_base", 10) * (1 + sci_growth))
                new_sci_appl = int(stats.get("science_applied", 10) * (1 + sci_growth * 0.8))
                gdp_growth = 0.01 + sci_b * 0.02 + inf_b * 0.03 + mil_b * 0.005 + wel_b * 0.01
                new_gdp = int(stats["gdp"] * (1 + gdp_growth))

                new_satisfaction = float(stats.get("happiness", 60))
                if stats["tax_rate"] > 15:
                    new_satisfaction -= (stats["tax_rate"] - 15) * 0.5
                elif stats["tax_rate"] < 10:
                    new_satisfaction += (10 - stats["tax_rate"]) * 0.3
                
                new_satisfaction += wel_b * 5
                
                if wheat_shortage:
                    new_satisfaction -= 15
                
                new_satisfaction += (60 - new_satisfaction) * 0.05
                new_satisfaction = max(0.0, min(100.0, new_satisfaction))
                new_satisfaction_int = int(new_satisfaction)
                
                if new_satisfaction_int < 30:
                    new_gdp = int(new_gdp * 0.8)
                    treasury_delta -= 20000 * 1000
                    
                if new_satisfaction_int < 15:
                    if random.random() < 0.4:
                        await conn.execute("UPDATE countries SET gov_sub = $1 WHERE user_id = $2", "🔒 دیکتاتوری نظامی", user_id)
                        new_satisfaction_int = 35

                await conn.execute(
                    """UPDATE country_stats SET
                       treasury = treasury + $1,
                       population = $2,
                       gdp = $3,
                       science_base = $4,
                       science_applied = $5,
                       army = $6,
                       happiness = $7
                       WHERE user_id = $8""",
                    treasury_delta, new_pop, new_gdp, new_sci_base, new_sci_appl, new_army, new_satisfaction_int, user_id,
                )
                
                cols2 = [k for k in res.keys() if k != "user_id"]
                set_clause2 = ", ".join(f"{k}=${i+2}" for i, k in enumerate(cols2))
                await conn.execute(
                    f"UPDATE country_resources SET {set_clause2} WHERE user_id=$1",
                    user_id, *[res[k] for k in cols2],
                )

            new_day = state["current_day"] + 15
            new_month = state["current_month"]
            new_year = state["current_year"]
            if new_day > 30:
                new_day -= 30
                new_month += 1
                if new_month > 12:
                    new_month = 1
                    new_year += 1

            await conn.execute(
                """UPDATE game_state
                   SET current_year=$1, current_month=$2, current_day=$3,
                       total_turns=total_turns+1, last_update=NOW()
                   WHERE id=1""",
                new_year, new_month, new_day,
            )
            logger.info("Turn advanced to %s/%s/%s", new_year, new_month, new_day)
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
        ran = await process
