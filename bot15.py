import os
import logging
import asyncio
import asyncpg
import httpx
import json
import ast
import re
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand, CallbackQuery
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_ID = 8849773822
DATABASE_URL = os.environ.get("DATABASE_URL", "")
CHANNEL_ID = os.environ.get("CHANNEL_ID", "")
GROUP_ID = os.environ.get("GROUP_ID", "")
TOPIC_ID = os.environ.get("TOPIC_ID", "")
CLOUDFLARE_API_TOKEN = os.environ.get("CLOUDFLARE_API_TOKEN", "")
CLOUDFLARE_ACCOUNT_ID = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")

RESOURCES = {
    "oil": "🛢 نفت خام", "coal": "🪨 زغال سنگ", "iron": "⛏ سنگ آهن",
    "copper": "🟤 سنگ مس", "titanium": "⚙️ سنگ تیتانیوم", "uranium": "☢ سنگ اورانیوم",
    "tungsten": "🔫 سنگ تنگستن", "cobalt": "🔋 سنگ کوبالت", "chromium": "✨ سنگ کروم",
    "rare_earth": "💎 فلزات کمیاب", "steel": "🏗 فولاد", "chemicals": "🧪 مواد شیمیایی",
    "tank_armor": "🛡 آلیاژ زره", "jet_engine": "🚀 سوپرآلیاژ جت", "electronics": "📟 الکترونیک", "ammo": "🔫 مهمات",
    "gold": "🏵 طلا", "lead": "🔘 سرب", "zinc": "⚪ روی", "phosphate": "🧪 فسفات", "sulfur": "🟡 گوگرد"
}

GOVERNMENTS = {
    "communist": {"name": "☭ کمونیستی", "subs": {"marxist": "مارکسیسم-لنینیسم", "stalinist": "استالینیسم", "maoist": "مائوئیسم"}},
    "dictator": {"name": "✊ دیکتاتوری", "subs": {"military": "نظامی", "personal": "فردی", "party": "حزبی"}},
    "democracy": {"name": "🗳️ دموکراسی", "subs": {"parliamentary": "پارلمانی", "presidential": "ریاستی", "federal": "فدرال"}},
    "monarchy": {"name": "👑 سلطنتی", "subs": {"absolute": "مطلقه", "constitutional": "مشروطه", "empire": "امپراتوری"}},
    "republic": {"name": "🏛️ جمهوری", "subs": {"secular": "سکولار", "islamic": "اسلامی", "socialist": "سوسیالیستی"}},
    "religious": {"name": "🕌 دینی", "subs": {"shia_theo": "تئوکراسی شیعه", "suni_theo": "تئوکراسی سنی", "velayat": "ولایت فقیه"}}
}

AIRCRAFT_SPECS = {
    "F-14": "سرعت 2.34 ماخ | رادار AWG-9 (300km) | AIM-54 (200km) | AIM-7 (80km) | AIM-9 (18km) | مانور عالی | بال متغیر | خدمه: 2 نفر",
    "F-15": "سرعت 2.5 ماخ | رادار APG-63 (150km) | AIM-7 (80km) | AIM-9 (18km) | مانور فوق‌العاده | خدمه: 1 نفر",
    "F-16": "سرعت 2 ماخ | رادار APG-66 (60km) | AIM-9 (18km) | مانور فوق‌العاده | خدمه: 1 نفر",
    "F-4": "سرعت 2.23 ماخ | رادار APQ-120 (80km) | AIM-7 (80km) | AIM-9 (18km) | توپ 20mm | خدمه: 2 نفر",
    "MiG-21": "سرعت 2.1 ماخ | رادار RP-21 (19km) | R-3S (8km) | R-60 (8km) | مانور خوب | خدمه: 1 نفر",
    "MiG-23": "سرعت 2.35 ماخ | رادار RP-23 (70km) | R-23 (35km) | R-60 (8km) | مانور خوب | خدمه: 1 نفر",
    "MiG-25": "سرعت 2.83 ماخ | رادار RP-25 (100km) | R-40 (80km) | مانور ضعیف | خدمه: 1 نفر",
    "Mirage F1": "سرعت 2.2 ماخ | رادار Cyrano IV (60km) | R.530 (30km) | R.550 (10km) | توپ 30mm | خدمه: 1 نفر"
}

def get_radar_range(asset_name):
    if not asset_name:
        return 40
    for key, spec in AIRCRAFT_SPECS.items():
        if key.lower() in asset_name.lower():
            m = re.search(r'\((\d+)km\)', spec)
            if m:
                return int(m.group(1))
    return 40

PILOT_DB = {
    "ایران": 5000, "آمریکا": 25000, "شوروی": 30000, "چین": 10000, "عراق": 2000,
    "اسرائیل": 2500, "مصر": 3000, "سوریه": 2000, "بریتانیا": 5000, "فرانسه": 3000,
    "آلمان غربی": 4000, "آلمان شرقی": 2000, "ژاپن": 3500, "هند": 3855, "پاکستان": 3000,
    "ترکیه": 3000, "برزیل": 1500, "آرژانتین": 1500, "کره جنوبی": 2500, "کره شمالی": 3000,
    "ویتنام": 1500, "کوبا": 1000, "عربستان": 800
}

MILITARY_DB = {
    "ایران": {"نیروی هوایی": "F-14A Tomcat: 77 | F-4 Phantom II: 190 | F-5 Tiger II: 166", "نیروی زمینی": "Chieftain: 894 | M60 Patton: 460 | M47 Patton: 400 | Scorpion: 250", "توپخانه": "M101 105mm: 330 | M114 155mm: 100 | M107 175mm: 100 | M110 203mm: 100 | BM-21 Grad: 64", "نیروی دریایی": "ناوشکن Battle: 1 | ناوشکن Sumner: 2 | ناوچه Alvand: 4 | قایق موشک‌انداز Kaman: 10", "پدافند هوایی": "MIM-23 Hawk | توپ ضدهوایی ۱۸۰۰ عراده", "سلاح سبک": "H&K G3"},
    "آمریکا": {"نیروی هوایی": "F-15A/B: 310 | F-4: 968 | A-10: 144 | F-111: 350 | B-52: 346 | F-16: 156", "نیروی زمینی": "M60A3: 2560 | M48A5: 2067 | M551: 59", "توپخانه": "M101A1 105mm: 1500 | M109A1 155mm: 2000 | M107 175mm: 750 | M110 203mm: 750", "نیروی دریایی": "ناو هواپیمابر: 13 | رزمناو: 28 | ناوشکن: 97 | زیردریایی SSN: 80", "پدافند هوایی": "MIM-72 Chaparral | M163 Vulcan | FIM-43 Redeye", "سلاح سبک": "M16A1 | M1911A1"},
    "شوروی": {"نیروی هوایی": "MiG-23/27: 800 | MiG-25: 25 | Su-17/20/22: 500 | Su-24: 100 | Tu-95: 113 | Tu-22M: 150", "نیروی زمینی": "T-64/T-72/T-80: +20000 | T-62/T-55/T-54: 50000", "توپخانه": "D-30 122mm: 4379 | 2S1 Gvozdika: 2751 | 2S3 Akatsiya: 2325 | 2S7 Pion: 347 | BM-21: 4520", "نیروی دریایی": "ناو Kiev: 2 | Kirov: 1 | Kara: 7 | زیردریایی هسته‌ای: 180", "پدافند هوایی": "SA-2 | SA-3 | SA-5 | SA-10", "سلاح سبک": "AK-74 | AKM"},
    "چین": {"نیروی هوایی": "J-5: 1400 | J-6: 1000 | J-7: 75 | Q-5: 300 | H-6: 100", "نیروی زمینی": "Type 59: +9000 | Type 69: چند صد | T-34: چند صد", "توپخانه": "Type 54 122mm: 10000 | Type 59 130mm: 4000 | Type 66 152mm: 1000", "نیروی دریایی": "زیردریایی: 54 | ناوشکن/ناوچه: 16 | قایق گشتی: 763", "پدافند هوایی": "SA-2", "سلاح سبک": "Type 56"},
    "عراق": {"نیروی هوایی": "MiG-21: 115 | MiG-23: 80 | Su-20/22: 70 | Tu-22: 12 | Mirage F1EQ: 12", "نیروی زمینی": "T-54/55/62: 1700 | T-72: 100", "توپخانه": "D-30 122mm: 100 | M-46 130mm: 100 | GHN-45 155mm: 200 | 2S1 122mm: 100", "نیروی دریایی": "OSA-I: 4 | OSA-II: 8 | P-6: 12", "پدافند هوایی": "SA-2 | SA-3 | SA-6", "سلاح سبک": "AK-47 | Tabuk"},
    "اسرائیل": {"نیروی هوایی": "F-15A/B: 24 | F-4E: 90 | A-4: 270 | Kfir-C2: 80", "نیروی زمینی": "Centurion: 1000 | M60: 810 | M48: 650 | Merkava: 40", "توپخانه": "M109 155mm: 120 | M107 175mm: 60 | M110 203mm: 48 | M101 105mm: 500", "نیروی دریایی": "Reshef: 10 | Saar: 12 | Type 206: 3", "پدافند هوایی": "MIM-72 Chaparral | M163 Vulcan", "سلاح سبک": "Galil | Uzi | M16A1"},
    "مصر": {"نیروی هوایی": "MiG-21: 208 | MiG-17: 50 | Su-7: 120 | Tu-16: 25 | Mirage 5: 60", "نیروی زمینی": "T-54/55: 850 | T-62: 750 | M60A3: 60", "توپخانه": "D-30 122mm: 300 | M-46 130mm: 200 | 2S1 122mm: 100", "نیروی دریایی": "Skory: 4 | Romeo: 6 | OSA-I: 8 | Komar: 5", "پدافند هوایی": "SA-2: 360 | SA-3: 200 | SA-6: 75", "سلاح سبک": "AK-47"},
    "سوریه": {"نیروی هوایی": "MiG-21: 172 | MiG-23: 140 | MiG-25: 25 | Su-20/22: 30", "نیروی زمینی": "T-54/55: 1500 | T-62: 800 | T-72: 65", "توپخانه": "2S1 122mm: 100 | 2S3 152mm: 50 | D-30 122mm: 300", "نیروی دریایی": "OSA-I/II: 12 | Komar: 2", "پدافند هوایی": "SA-2 | SA-3 | SA-6", "سلاح سبک": "AK-47"},
    "بریتانیا": {"نیروی هوایی": "Phantom: 40 | Jaguar: 52 | Harrier: 26 | Buccaneer: 24 | Vulcan: 50", "نیروی زمینی": "Chieftain: 640", "توپخانه": "Abbot 105mm: 100 | M109 155mm: 50", "نیروی دریایی": "Hermes: 1 | Type 42: 7 | Type 22: 2 | Resolution (SSBN): 4", "پدافند هوایی": "Rapier | Bloodhound", "سلاح سبک": "L1A1 SLR"},
    "فرانسه": {"نیروی هوایی": "Mirage F1C: 90 | Mirage IIIE: 30 | Jaguar: 174 | Mirage IV: 34", "نیروی زمینی": "AMX-30: 1360", "توپخانه": "AMX-30 AuF1 155mm: 110 | TR 155mm: 20", "نیروی دریایی": "Clemenceau: 2 | Colbert: 1 | Redoutable (SSBN): 4", "پدافند هوایی": "Roland | MIM-23 Hawk", "سلاح سبک": "FAMAS"},
    "آلمان غربی": {"نیروی هوایی": "F-4F: 175 | RF-4E: 88 | F-104G: 144 | Tornado: 10", "نیروی زمینی": "Leopard 1: 2400 | Leopard 2: 100 | M48: 650", "توپخانه": "M109G 155mm: 586 | FH-70 155mm: 215 | LARS 110mm: 209", "نیروی دریایی": "Type 206: 18 | Lütjens: 3 | Bremen: 6", "پدافند هوایی": "Roland | Gepard", "سلاح سبک": "H&K G3"},
    "آلمان شرقی": {"نیروی هوایی": "MiG-21: 252 | MiG-23: 81 | Su-7: 80 | MiG-17: 30", "نیروی زمینی": "T-54/55: 2500 | T-72: 549 | T-34: 600", "توپخانه": "2S1 122mm: 200 | 2S3 152mm: 100 | D-30 122mm: 300", "نیروی دریایی": "Koni: 3 | OSA-I: 15 | Shershen: 18", "پدافند هوایی": "SA-4 | SA-6 | SA-7", "سلاح سبک": "AK-47 | AK-74"},
    "ژاپن": {"نیروی هوایی": "F-4EJ: 140 | RF-4E: 14 | F-1: 77", "نیروی زمینی": "Type 74: 740", "توپخانه": "Type 75 155mm: 200 | Type 74 105mm: 100", "نیروی دریایی": "ناوشکن: 60 | زیردریایی: 16", "پدافند هوایی": "MIM-23 Hawk", "سلاح سبک": "Howa Type 64"},
    "هند": {"نیروی هوایی": "MiG-21: 300 | Su-7: 120 | Jaguar: 88 | MiG-23BN: 53", "نیروی زمینی": "T-54/55: 950 | T-72: 70 | Vijayanta: 1100", "توپخانه": "D-30 122mm: 500 | M-46 130mm: 300", "نیروی دریایی": "Vikrant: 1 | Foxtrot: 8", "پدافند هوایی": "SA-2", "سلاح سبک": "Ishapore 2A1"},
    "پاکستان": {"نیروی هوایی": "Mirage III: 65 | Mirage 5: 52 | J-6: 175 | F-7P: 74", "نیروی زمینی": "Type 59: 1000 | M48", "توپخانه": "D-30 122mm: 200 | M-46 130mm: 100", "نیروی دریایی": "ناوشکن: 1 | ناوچه: 8 | زیردریایی: 9", "پدافند هوایی": "SA-2", "سلاح سبک": "G3 | AK-47"},
    "ترکیه": {"نیروی هوایی": "F-4E: 80 | RF-4E: 8 | F-104G: 72 | F-5: 24", "نیروی زمینی": "M48: 3000 | M47", "توپخانه": "M101 105mm: 500 | M114 155mm: 300", "نیروی دریایی": "ناوشکن: 13 | زیردریایی: 15", "پدافند هوایی": "Rapier", "سلاح سبک": "G3"},
    "برزیل": {"نیروی هوایی": "Mirage III: 15 | F-5E: 36 | AT-26: 50", "نیروی زمینی": "M41: 250 | M3A1: 220 | X1A2: 25", "توپخانه": "M101 105mm: 300 | M114 155mm: 100", "نیروی دریایی": "Minas Gerais: 1 | Oberon: 3 | GUPPY: 7", "پدافند هوایی": "Roland", "سلاح سبک": "FN FAL"},
    "آرژانتین": {"نیروی هوایی": "Mirage IIIEA: 16 | Dagger: 35 | A-4: 16 | Pucara: 30", "نیروی زمینی": "TAM: 350 | AMX-13", "توپخانه": "CITER 155mm: 87 | OTO Melara 105mm: 80", "نیروی دریایی": "Veinticinco de Mayo: 1 | Belgrano: 1", "پدافند هوایی": "Roland", "سلاح سبک": "FN FAL"},
    "کره جنوبی": {"نیروی هوایی": "F-4D/E: 128 | F-5A/B: 44 | F-5E/F: 160", "نیروی زمینی": "M47: 350 | M48", "توپخانه": "M109 155mm: 200 | M101 105mm: 500", "نیروی دریایی": "ناوشکن: 60 | زیردریایی: 16", "پدافند هوایی": "MIM-23 Hawk", "سلاح سبک": "M16A1"},
    "کره شمالی": {"نیروی هوایی": "MiG-21: 120 | MiG-19: 130 | MiG-17: 107 | Su-7: 20", "نیروی زمینی": "T-54/55: 2000 | T-62: 300 | T-34: 300", "توپخانه": "D-30 122mm: 1000 | M-46 130mm: 500 | BM-21: 500", "نیروی دریایی": "زیردریایی: 20 | OSA: 52", "پدافند هوایی": "SA-2", "سلاح سبک": "AK-47"},
    "ویتنام": {"نیروی هوایی": "MiG-21: 120 | MiG-19: 70 | MiG-17: 70 | F-5: 20", "نیروی زمینی": "T-54/55: 1600 | Type 59: 160 | PT-76: 450", "توپخانه": "D-30 122mm: 500 | M-46 130mm: 300", "نیروی دریایی": "OSA: 8 | مین‌روب: 5", "پدافند هوایی": "SA-2: 360", "سلاح سبک": "AK-47"},
    "کوبا": {"نیروی هوایی": "MiG-23BN: 25 | MiG-21: 78 | MiG-19: 40", "نیروی زمینی": "T-54/55: 630 | T-62: 50 | T-34: 350", "توپخانه": "D-30 122mm: 200 | M-46 130mm: 100", "نیروی دریایی": "Foxtrot: 2 | OSA-II: 13", "پدافند هوایی": "SA-2 | SA-3", "سلاح سبک": "AK-47"},
    "عربستان": {"نیروی هوایی": "F-5E: 70 | F-5F: 20", "نیروی زمینی": "M47 | M41", "توپخانه": "M101 105mm: 200 | M109 155mm: 100", "نیروی دریایی": "قایق‌های گشتی", "پدافند هوایی": "MIM-23 Hawk", "سلاح سبک": "FN FAL"}
}

PERSONNEL_DB = {
    "ایران": "ارتش (Artesh): ۴۲۰,۰۰۰ نفر | سپاه پاسداران (تازه تاسیس): ۱۰۰,۰۰۰ نفر",
    "آمریکا": "ارتش: ۷۵۴,۰۰۰ نفر | نیروی هوایی: ۵۵۵,۰۰۰ نفر | نیروی دریایی: ۵۲۹,۰۰۰ نفر | تفنگداران: ۱۸۵,۰۰۰ نفر",
    "شوروی": "ارتش: ۲,۰۰۰,۰۰۰ نفر | نیروی هوایی: ۵۱۰,۰۰۰ نفر | نیروی دریایی: ۴۵۰,۰۰۰ نفر | پدافند: ۵۵۰,۰۰۰ نفر",
    "چین": "ارتش: ۴,۰۰۰,۰۰۰ نفر | نیروی هوایی: ۴۹۰,۰۰۰ نفر | نیروی دریایی: ۲۸۰,۰۰۰ نفر",
    "عراق": "ارتش: ۱۹۰,۰۰۰ نفر | نیروی هوایی: ۲۸,۰۰۰ نفر | نیروی دریایی: ۴,۰۰۰ نفر",
    "اسرائیل": "ارتش: ۱۳۵,۰۰۰ نفر | نیروی هوایی: ۲۱,۰۰۰ نفر | نیروی دریایی: ۶,۶۰۰ نفر",
    "مصر": "ارتش: ۲۳۵,۰۰۰ نفر | نیروی هوایی: ۲۵,۰۰۰ نفر | نیروی دریایی: ۱۵,۰۰۰ نفر | پدافند: ۸۵,۰۰۰ نفر",
    "سوریه": "ارتش: ۱۷۰,۰۰۰ نفر | نیروی هوایی: ۴۰,۰۰۰ نفر | نیروی دریایی: ۴,۰۰۰ نفر",
    "بریتانیا": "ارتش: ۱۳۸,۶۰۰ نفر | نیروی هوایی: ۷۹,۷۰۰ نفر | نیروی دریایی: ۶۵,۹۰۰ نفر",
    "فرانسه": "ارتش: ۳۱۴,۷۲۲ نفر | نیروی هوایی: ۱۰۲,۰۰۰ نفر | نیروی دریایی: ۶۸,۰۰۰ نفر",
    "آلمان غربی": "ارتش: ۳۴۰,۰۰۰ نفر | نیروی هوایی: ۱۱۱,۰۰۰ نفر | نیروی دریایی: ۳۸,۰۰۰ نفر",
    "آلمان شرقی": "ارتش: ۱۰۷,۰۰۰ نفر | نیروی هوایی: ۳۶,۰۰۰ نفر | نیروی دریایی: ۱۶,۰۰۰ نفر",
    "ژاپن": "ارتش: ۱۵۰,۰۰۰ نفر | نیروی هوایی: ۵۰,۵۰۰ نفر | نیروی دریایی: ۵۱,۰۰۰ نفر",
    "هند": "ارتش: ۹۵۰,۰۰۰ نفر | نیروی هوایی: ۱۰۰,۰۰۰ نفر | نیروی دریایی: ۴۰,۰۰۰ نفر",
    "پاکستان": "ارتش: ۴۰۰,۰۰۰ نفر | نیروی هوایی: ۳۵,۰۰۰ نفر | نیروی دریایی: ۱۵,۰۰۰ نفر",
    "ترکیه": "ارتش: ۴۵۰,۰۰۰ نفر | نیروی هوایی: ۵۰,۰۰۰ نفر | نیروی دریایی: ۴۰,۰۰۰ نفر",
    "برزیل": "ارتش: ۱۷۰,۰۰۰ نفر | نیروی هوایی: ۴۱,۴۰۰ نفر | نیروی دریایی: ۴۵,۸۰۰ نفر",
    "آرژانتین": "ارتش: ۸۳,۵۰۰ نفر | نیروی هوایی: ۲۰,۰۰۰ نفر | نیروی دریایی: ۳۳,۰۰۰ نفر",
    "کره جنوبی": "ارتش: ۵۶۰,۰۰۰ نفر | نیروی هوایی: ۳۰,۰۰۰ نفر | نیروی دریایی: ۲۰,۰۰۰ نفر",
    "کره شمالی": "ارتش: ۵۰۰,۰۰۰ نفر | نیروی هوایی: ۴۵,۰۰۰ نفر | نیروی دریایی: ۲۰,۰۰۰ نفر",
    "ویتنام": "ارتش: ۶۰۰,۰۰۰ نفر | نیروی هوایی: ۱۲,۰۰۰ نفر | نیروی دریایی: ۳,۰۰۰ نفر",
    "کوبا": "ارتش: ۱۳۰,۰۰۰ نفر | نیروی هوایی: ۱۵,۰۰۰ نفر | نیروی دریایی: ۵,۰۰۰ نفر",
    "عربستان": "ارتش: ۴۰,۰۰۰ نفر | نیروی هوایی: ۱۰,۰۰۰ نفر | نیروی دریایی: ۱,۷۰۰ نفر"
}

FACTORY_DB = {
    "آمریکا": {"F-15": "سنت لوئیس (میزوری)", "F-16": "فورت ورث (تگزاس)", "M1": "لیما (اوهایو)", "M60": "دیترویت (میشیگان)", "SSN": "گراتون (کنتیکت)"},
    "شوروی": {"MiG-23": "مسکو (کارخانه ۳۰)", "Su-17": "کامسومولسک", "T-72": "نیژنی تاگیل", "T-64": "خارکف", "SSBN": "سوردوینسک"},
    "ایران": {"F-14": "اصفهان (مونتاژ)", "M60": "تهران (مونتاژ)"},
    "بریتانیا": {"Chieftain": "لیدز", "Tornado": "والتون"},
    "فرانسه": {"Mirage": "بوردو"},
    "اسرائیل": {"Kfir": "لود", "Merkava": "تل هشومر"},
    "آلمان غربی": {"Leopard": "مونیخ"}
}

TECH_TREE = {
    "ایران": {
        "موشک فاتح-۱۱۰": {"cost": 500000000, "turns": 3, "next": "موشک سجیل", "desc": "موشک بالستیک کوتاه‌برد دقیق"},
        "موشک سجیل": {"cost": 1500000000, "turns": 5, "next": "موشک خرمشهر-۴", "desc": "موشک بالستیک میان‌برد سوخت جامد"},
        "موشک خرمشهر-۴": {"cost": 3000000000, "turns": 8, "next": "None", "desc": "موشک بالستیک سنگین و دوربرد"}
    },
    "شوروی": {
        "MiG-29 Fulcrum": {"cost": 2000000000, "turns": 4, "next": "Su-27 Flanker", "desc": "جنگنده برتری هوایی نسل چهارم"},
        "Su-27 Flanker": {"cost": 5000000000, "turns": 6, "next": "Su-30 Flanker-C", "desc": "جنگنده سنگین دو موتوره با برد بالا"},
        "Su-30 Flanker-C": {"cost": 8000000000, "turns": 8, "next": "Su-35 Flanker-E", "desc": "جنگنده چندمنظوره با رادار پیشرفته"}
    },
    "آمریکا": {
        "F-117 Nighthawk": {"cost": 3000000000, "turns": 5, "next": "F-22 Raptor", "desc": "جنگنده رادارگریز (استیلث)"},
        "F-22 Raptor": {"cost": 20000000000, "turns": 15, "next": "None", "desc": "جنگنده برتری هوایی نسل پنجم"}
    }
}

COUNTRY_DB = {
    "ایران": {"gdp_init": 90400000000, "mil_budget_init": 4000000000, "army_init": 520000, "tanks_init": 1735, "jets_init": 450, "refineries_init": 1175000, "cities": "تهران، اصفهان، مشهد، تبریز، شیراز، اهواز، کرمانشاه، قم، آبادان", "mines": {"oil_well": {"name": "میدان نفتی مارون و اهواز", "output_res": "oil", "amount": 3000000}, "copper_mine": {"name": "معدن مس سرچشمه", "output_res": "copper", "amount": 40000}, "iron_mine": {"name": "معدن سنگ آهن بافق", "output_res": "iron", "amount": 60000}}, "factories": {"abadan_refinery": {"name": "پالایشگاه آبادان", "income": 250000, "cost": 500000, "consumes": "oil", "produces": "chemicals"}, "isfahan_steel": {"name": "ذوب آهن اصفهان", "income": 150000, "cost": 350000, "consumes": "iron", "produces": "steel"}}},
    "آمریکا": {"gdp_init": 2627333000000, "mil_budget_init": 548272000000, "army_init": 2013233, "tanks_init": 7835, "jets_init": 3000, "refineries_init": 17050000, "cities": "نیویورک، کالیفرنیا، تگزاس، فلوریدا، آلاسکا، ایلینوی", "mines": {"oil_well": {"name": "میدان تگزاس و پرودو بی", "output_res": "oil", "amount": 9000000}, "iron_mine": {"name": "آهن میشیگان", "output_res": "iron", "amount": 80000}, "coal_mine": {"name": "زغال آپالاش", "output_res": "coal", "amount": 300000}}, "factories": {"baytown_refinery": {"name": "پالایشگاه اکسون بیتون", "income": 600000, "cost": 1200000, "consumes": "oil", "produces": "chemicals"}, "bethlehem_steel": {"name": "فولاد بتلهم", "income": 400000, "cost": 800000, "consumes": "iron", "produces": "steel"}}},
    "شوروی": {"gdp_init": 1300000000000, "mil_budget_init": 165000000000, "army_init": 3658000, "tanks_init": 50000, "jets_init": 8479, "refineries_init": 10000000, "cities": "مسکو، لنینگراد، کی‌یف، مینسک، تفلیس، باکو", "mines": {"oil_well": {"name": "میدان تیومن", "output_res": "oil", "amount": 11900000}, "iron_mine": {"name": "آهن کورسک", "output_res": "iron", "amount": 250000}, "uranium_mine": {"name": "اورانیوم قزاقستان", "output_res": "uranium", "amount": 50000}}, "factories": {"omsk_refinery": {"name": "پالایشگاه اومسک", "income": 600000, "cost": 1200000, "consumes": "oil", "produces": "chemicals"}, "magnitogorsk": {"name": "فولاد مگنیتوگورسک", "income": 400000, "cost": 700000, "consumes": "iron", "produces": "steel"}}},
    "چین": {"gdp_init": 263698000000, "mil_budget_init": 40000000000, "army_init": 5120000, "tanks_init": 10000, "jets_init": 5000, "refineries_init": 2000000, "cities": "پکن، شانگهای، تیانجین", "mines": {"coal_mine": {"name": "زغال شانشی", "output_res": "coal", "amount": 250000}, "iron_mine": {"name": "آهن آنشان", "output_res": "iron", "amount": 90000}}, "factories": {"anshan_steel": {"name": "فولاد آنشان", "income": 180000, "cost": 400000, "consumes": "iron", "produces": "steel"}}},
    "عراق": {"gdp_init": 118000000000, "mil_budget_init": 11350000000, "army_init": 222000, "tanks_init": 1900, "jets_init": 339, "refineries_init": 450000, "cities": "بغداد، بصره، موصل، کرکوک", "mines": {"oil_well": {"name": "میدان کرکوک", "output_res": "oil", "amount": 3500000}}, "factories": {"baiji_refinery": {"name": "پالایشگاه بیجی", "income": 200000, "cost": 400000, "consumes": "oil", "produces": "chemicals"}}},
    "اسرائیل": {"gdp_init": 23000000000, "mil_budget_init": 13269000000, "army_init": 172000, "tanks_init": 3050, "jets_init": 576, "refineries_init": 218000, "cities": "اورشلیم، تل‌آویو، حیفا", "mines": {"copper_mine": {"name": "مس تیمنا", "output_res": "copper", "amount": 10000}}, "factories": {"haifa_refinery": {"name": "پالایشگاه حیفا", "income": 150000, "cost": 300000, "consumes": "oil", "produces": "chemicals"}}},
    "مصر": {"gdp_init": 19000000000, "mil_budget_init": 1165000000, "army_init": 445000, "tanks_init": 1600, "jets_init": 568, "refineries_init": 180000, "cities": "قاهره، اسکندریه، سوئز", "mines": {"oil_well": {"name": "نفت خلیج سوئز", "output_res": "oil", "amount": 527000}}, "factories": {"suez_refinery": {"name": "پالایشگاه سوئز", "income": 120000, "cost": 250000, "consumes": "oil", "produces": "chemicals"}}},
    "سوریه": {"gdp_init": 12300000000, "mil_budget_init": 2400000000, "army_init": 230000, "tanks_init": 2600, "jets_init": 262, "refineries_init": 116000, "cities": "دمشق، حلب، حمص", "mines": {"oil_well": {"name": "نفت کرچوک", "output_res": "oil", "amount": 180000}}, "factories": {"homs_refinery": {"name": "پالایشگاه حمص", "income": 100000, "cost": 200000, "consumes": "oil", "produces": "chemicals"}}},
    "بریتانیا": {"gdp_init": 181000000000, "mil_budget_init": 18000000000, "army_init": 215000, "tanks_init": 640, "jets_init": 1796, "refineries_init": 1000000, "cities": "لندن، بیرمنگام، گلاسکو", "mines": {"coal_mine": {"name": "زغال یورکشایر", "output_res": "coal", "amount": 122000000}, "oil_well": {"name": "نفت فورتیس", "output_res": "oil", "amount": 1000000}}, "factories": {"pembroke_refinery": {"name": "پالایشگاه پمبروک", "income": 250000, "cost": 500000, "consumes": "oil", "produces": "chemicals"}, "port_talbot": {"name": "فولاد پورت تالبوت", "income": 200000, "cost": 450000, "consumes": "coal", "produces": "steel"}}},
    "فرانسه": {"gdp_init": 537000000000, "mil_budget_init": 18000000000, "army_init": 484722, "tanks_init": 1360, "jets_init": 477, "refineries_init": 1500000, "cities": "پاریس، مارسی، لیون", "mines": {"iron_mine": {"name": "آهن لورن", "output_res": "iron", "amount": 30000}}, "factories": {"le_havre_refinery": {"name": "پالایشگاه لو هاور", "income": 350000, "cost": 700000, "consumes": "oil", "produces": "chemicals"}}},
    "آلمان غربی": {"gdp_init": 881000000000, "mil_budget_init": 64008000000, "army_init": 495000, "tanks_init": 5000, "jets_init": 577, "refineries_init": 1500000, "cities": "دوسلدورف، کلن، مونیخ", "mines": {"coal_mine": {"name": "زغال رور", "output_res": "coal", "amount": 200000000}}, "factories": {"rheinland_refinery": {"name": "پالایشگاه راینلند", "income": 350000, "cost": 700000, "consumes": "oil", "produces": "chemicals"}, "thyssen_steel": {"name": "فولاد تیسن", "income": 300000, "cost": 650000, "consumes": "coal", "produces": "steel"}}},
    "آلمان شرقی": {"gdp_init": 170000000000, "mil_budget_init": 4500000000, "army_init": 173100, "tanks_init": 3140, "jets_init": 335, "refineries_init": 0, "cities": "برلین شرقی، روستوک، لایپزیگ", "mines": {"coal_mine": {"name": "لیگنیت", "output_res": "coal", "amount": 250000000}}, "factories": {"leuna_chem": {"name": "شیمیایی لویونا", "income": 150000, "cost": 300000, "consumes": "coal", "produces": "chemicals"}}},
    "ژاپن": {"gdp_init": 1055012000000, "mil_budget_init": 21225000000, "army_init": 250000, "tanks_init": 740, "jets_init": 227, "refineries_init": 5000000, "cities": "توکیو، اوساکا، ناگویا", "mines": {"coal_mine": {"name": "زغال هوکایدو", "output_res": "coal", "amount": 20000}}, "factories": {"yokkaichi_refinery": {"name": "پالایشگاه یوکای‌ایچی", "income": 400000, "cost": 700000, "consumes": "oil", "produces": "chemicals"}}},
    "هند": {"gdp_init": 152062000000, "mil_budget_init": 11190000000, "army_init": 1000000, "tanks_init": 2790, "jets_init": 625, "refineries_init": 500000, "cities": "دهلی نو، بمبئی، کلکته", "mines": {"iron_mine": {"name": "آهن بیهار", "output_res": "iron", "amount": 60000}}, "factories": {"bhilai_steel": {"name": "فولاد بیلای", "income": 150000, "cost": 350000, "consumes": "iron", "produces": "steel"}}},
    "پاکستان": {"gdp_init": 25798000000, "mil_budget_init": 1979000000, "army_init": 400000, "tanks_init": 1000, "jets_init": 247, "refineries_init": 100000, "cities": "اسلام‌آباد، کراچی، لاهور", "mines": {"iron_mine": {"name": "آهن کلاباغ", "output_res": "iron", "amount": 20000}}, "factories": {"karachi_refinery": {"name": "پالایشگاه کراچی", "income": 100000, "cost": 250000, "consumes": "oil", "produces": "chemicals"}}},
    "ترکیه": {"gdp_init": 126394000000, "mil_budget_init": 4733000000, "army_init": 500000, "tanks_init": 3000, "jets_init": 300, "refineries_init": 400000, "cities": "آنکارا، استانبول، ازمیر", "mines": {"chromium_mine": {"name": "کروم گولنار", "output_res": "chromium", "amount": 40000}}, "factories": {"izmit_refinery": {"name": "پالایشگاه ایزمیت", "income": 120000, "cost": 250000, "consumes": "oil", "produces": "chemicals"}}},
    "برزیل": {"gdp_init": 186976000000, "mil_budget_init": 6811000000, "army_init": 257000, "tanks_init": 350, "jets_init": 205, "refineries_init": 1000000, "cities": "برازیلیا، سائوپائولو، ریو", "mines": {"iron_mine": {"name": "آهن کاراخاس", "output_res": "iron", "amount": 80000}}, "factories": {"volta_redonda": {"name": "فولاد ولتا ردوندا", "income": 150000, "cost": 300000, "consumes": "iron", "produces": "steel"}}},
    "آرژانتین": {"gdp_init": 73916000000, "mil_budget_init": 14098000000, "army_init": 133500, "tanks_init": 350, "jets_init": 132, "refineries_init": 600000, "cities": "بوئنوس آیرس، کوردوبا", "mines": {"copper_mine": {"name": "مس ال تنیته", "output_res": "copper", "amount": 20000}}, "factories": {"la_plata_refinery": {"name": "پالایشگاه لا پلاتا", "income": 100000, "cost": 250000, "consumes": "oil", "produces": "chemicals"}}},
    "کره جنوبی": {"gdp_init": 66947000000, "mil_budget_init": 8819000000, "army_init": 600000, "tanks_init": 350, "jets_init": 520, "refineries_init": 600000, "cities": "سئول، بوسان، اینچئون", "mines": {"tungsten_mine": {"name": "تنگستن سانگ‌دونگ", "output_res": "tungsten", "amount": 15000}}, "factories": {"pohang_steel": {"name": "فولاد پوهانگ", "income": 150000, "cost": 300000, "consumes": "iron", "produces": "steel"}}},
    "کره شمالی": {"gdp_init": 9490000000, "mil_budget_init": 2000000000, "army_init": 600000, "tanks_init": 2300, "jets_init": 565, "refineries_init": 50000, "cities": "پیونگ‌یانگ، هامهونگ", "mines": {"coal_mine": {"name": "زغال آنجو", "output_res": "coal", "amount": 50000}}, "factories": {"kimchaek_steel": {"name": "فولاد کیم‌چک", "income": 100000, "cost": 200000, "consumes": "coal", "produces": "steel"}}},
    "ویتنام": {"gdp_init": 7140000000, "mil_budget_init": 1000000000, "army_init": 615000, "tanks_init": 2000, "jets_init": 300, "refineries_init": 0, "cities": "هانوی، هوشی‌مین", "mines": {"coal_mine": {"name": "زغال هونگ گای", "output_res": "coal", "amount": 30000}}, "factories": {"thai_nguyen": {"name": "فولاد تای نگوین", "income": 80000, "cost": 200000, "consumes": "coal", "produces": "steel"}}},
    "کوبا": {"gdp_init": 19584000000, "mil_budget_init": 1500000000, "army_init": 150000, "tanks_init": 800, "jets_init": 168, "refineries_init": 100000, "cities": "هاوانا، سانتیاگو", "mines": {"cobalt_mine": {"name": "کوبالت موآ", "output_res": "cobalt", "amount": 15000}}, "factories": {"nico_lopez_refinery": {"name": "پالایشگاه نیکو لوپز", "income": 80000, "cost": 200000, "consumes": "oil", "produces": "chemicals"}}},
    "عربستان": {"gdp_init": 94600000000, "mil_budget_init": 10500000000, "army_init": 51700, "tanks_init": 550, "jets_init": 90, "refineries_init": 834900, "cities": "ریاض، جده، مکه", "mines": {"oil_well": {"name": "میدان غوار", "output_res": "oil", "amount": 10000000}}, "factories": {"ras_tanura": {"name": "پالایشگاه راس تنوره", "income": 300000, "cost": 600000, "consumes": "oil", "produces": "chemicals"}}}
}

ALLOWED_COUNTRIES = list(COUNTRY_DB.keys())
pool = None
temp = {}
spam_tracker = {}
ai_order_tracker = {}

async def init_db():
    global pool
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS countries (
                user_id BIGINT PRIMARY KEY, username TEXT, name TEXT, status TEXT DEFAULT 'pending',
                leader TEXT, gov_main TEXT, gov_sub TEXT,
                gdp BIGINT DEFAULT 500000000, mil_budget BIGINT DEFAULT 35000000,
                jets INT DEFAULT 0, tanks INT DEFAULT 0, refineries INT DEFAULT 0, army INT DEFAULT 100000,
                pilots INT DEFAULT 0, satisfaction INT DEFAULT 50, tax_rate INT DEFAULT 10,
                alliance TEXT DEFAULT 'none', reputation INT DEFAULT 50,
                researching_tech TEXT DEFAULT 'None', research_turns_left INT DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS deployments (
                id SERIAL PRIMARY KEY, user_id BIGINT, country_name TEXT, region TEXT,
                asset_type TEXT, model TEXT, quantity INT, status TEXT DEFAULT 'active', created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS encounters (
                id SERIAL PRIMARY KEY, order_id BIGINT,
                detector_id BIGINT, detector_country TEXT, detector_asset TEXT, detector_intent TEXT DEFAULT 'pending',
                detected_id BIGINT, detected_country TEXT, detected_asset TEXT, detected_intent TEXT DEFAULT 'pending',
                region TEXT, status TEXT DEFAULT 'awaiting_intent', battle_narrative TEXT, created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS infrastructure (
                id SERIAL PRIMARY KEY, user_id BIGINT, sector_type TEXT, name TEXT, income BIGINT DEFAULT 0, created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id SERIAL PRIMARY KEY, user_id BIGINT, order_text TEXT, category TEXT, status TEXT DEFAULT 'pending',
                ai_analysis_raw TEXT, order_intent TEXT, region TEXT, enemy_user_id BIGINT, target_country TEXT,
                is_public BOOLEAN DEFAULT TRUE, player_approved BOOLEAN DEFAULT FALSE, leader_approved BOOLEAN DEFAULT FALSE,
                final_narrative TEXT, created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        for res in RESOURCES.keys():
            await conn.execute(f"ALTER TABLE countries ADD COLUMN IF NOT EXISTS res_{res} BIGINT DEFAULT 0")
        columns_to_add = [
            ("orders", "is_public", "BOOLEAN DEFAULT TRUE"),
            ("orders", "target_country", "TEXT"),
            ("orders", "order_intent", "TEXT"),
            ("orders", "region", "TEXT"),
            ("orders", "enemy_user_id", "BIGINT"),
            ("orders", "player_approved", "BOOLEAN DEFAULT FALSE"),
            ("orders", "leader_approved", "BOOLEAN DEFAULT FALSE"),
            ("orders", "final_narrative", "TEXT"),
            ("countries", "alliance", "TEXT DEFAULT 'none'"),
            ("countries", "reputation", "INT DEFAULT 50"),
            ("countries", "leader", "TEXT"),
            ("countries", "gov_main", "TEXT"),
            ("countries", "gov_sub", "TEXT"),
            ("countries", "pilots", "INT DEFAULT 0"),
            ("countries", "researching_tech", "TEXT DEFAULT 'None'"),
            ("countries", "research_turns_left", "INT DEFAULT 0"),
        ]
        for table, col, col_type in columns_to_add:
            try:
                await conn.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {col_type}")
            except:
                pass
        await conn.execute("UPDATE countries SET alliance = 'ناتو' WHERE name IN ('آمریکا', 'بریتانیا', 'فرانسه', 'آلمان غربی', 'ترکیه') AND alliance = 'none'")
        await conn.execute("UPDATE countries SET alliance = 'ورشو' WHERE name IN ('شوروی', 'آلمان شرقی') AND alliance = 'none'")
    logger.info("Database initialized (Full V5).")

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
    start = raw.find('{')
    end = raw.rfind('}')
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
    cleaned = re.sub(r'[*_`\[\]<>#|\\]', '', text)
    cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', cleaned)
    return cleaned.strip()

def check_spam(uid):
    if uid == ADMIN_ID:
        return False
    now = time.time()
    if uid not in spam_tracker:
        spam_tracker[uid] = []
    spam_tracker[uid] = [t for t in spam_tracker[uid] if now - t < 60]
    spam_tracker[uid].append(now)
    return len(spam_tracker[uid]) > 15

def check_ai_limit(uid):
    if uid == ADMIN_ID:
        return False
    now = time.time()
    if uid not in ai_order_tracker:
        ai_order_tracker[uid] = []
    ai_order_tracker[uid] = [t for t in ai_order_tracker[uid] if now - t < 60]
    ai_order_tracker[uid].append(now)
    return len(ai_order_tracker[uid]) > 4

async def get_enemy_deployments_str(player_country):
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM deployments WHERE country_name != $1 AND quantity > 0", player_country)
    if not rows:
        return "هیچ نیروی دشمنی مستقر نیست."
    return "\n".join([f"- {r['country_name']}: {r['quantity']} {r['model']} در {r['region']}" for r in rows])

async def ask_ai(prompt: str, system_prompt: str = "You are a strict JSON API. Output RAW JSON only. DO NOT wrap in markdown. DO NOT translate JSON keys. Use Persian ONLY for text values.") -> str:
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
                    if isinstance(resp, dict):
                        return json.dumps(resp, ensure_ascii=False)
                    return str(resp)
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

def _build_prompt(country: dict, order_text: str, category: str, enemy_deployments: str) -> str:
    if category == "political":
        narrative_rule = "The narrative MUST be a highly dramatic political speech."
    elif category == "diplomacy":
        narrative_rule = "The narrative MUST be a formal diplomatic agreement."
    elif category == "military":
        narrative_rule = "The narrative MUST be an epic war report."
    else:
        narrative_rule = "The narrative MUST be a dramatic economic news report."
    current_tech = country.get('researching_tech', 'None')
    tech_info = f"در حال تحقیق: {current_tech}" if current_tech != 'None' else "هیچ تحقیقی در جریان نیست."
    return f"""You are the strict Game Master of a grand strategy game set in 1979.

COUNTRY: {country['name']} | GDP: ${country['gdp']:,} | Mil Budget: ${country['mil_budget']:,}
Army: {country['army']} | Tanks: {country['tanks']} | Jets: {country['jets']} | {tech_info}

ENEMY DEPLOYMENTS GLOBALLY:
{enemy_deployments}

PLAYER ORDER: "{order_text}"
CATEGORY: {category}

CRITICAL GEOPOLITICAL REALITY:
- If the order is historically impossible, REJECT IT (success: false).

CRITICAL MILITARY RULES (DEPLOYMENT):
- If the order is to DEPLOY forces: Extract EXACT number, model, and region.
- Deploying forces DOES NOT consume total jets/tanks. Set "jets_change" and "tanks_change" to 0.

CRITICAL MILITARY INTENT DETECTION (VERY IMPORTANT):
- "گشت", "گشت‌زنی", "گشت و جستجو", "پاترول", "patrol", "مراقبت" → order_intent="patrol", action_type="deploy"
- "حمله", "تهاجم", "یورش", "بمباران", "attack", "شلیک" → order_intent="attack", action_type="attack"
- "اعزام", "انتقال", "استقرار", "deploy", "بفرست" → order_intent="deploy", action_type="deploy"

NARRATIVE RULE:
- If order_intent="patrol": narrative MUST say "گشت‌زنی" and NEVER say "حمله" or "تهاجمی".
- If order_intent="attack": narrative MUST say "حمله" or "تهاجم".
- "گشت و جستجو" is ALWAYS patrol, NEVER attack.

CRITICAL DIPLOMACY:
- Extract "target_country" if diplomatic. If not, "None".

NARRATIVE STYLE: {narrative_rule}
Use ONLY Persian alphabet for values. Keep JSON keys in English.

EXACT JSON FORMAT:
{{
  "success": true/false,
  "reason": "Persian reason",
  "order_intent": "attack/patrol/deploy/economic/political/diplomacy",
  "action_type": "deploy/attack/economic/political/diplomacy",
  "target_country": "USA or None",
  "region": "Alaska or None",
  "deployed_asset": "MiG-23 or None",
  "deployed_quantity": 15,
  "deployment_cost": 5000000,
  "battle_occurred": false,
  "enemy_country": "None",
  "my_losses": 0,
  "enemy_losses": 0,
  "gdp_change": 0,
  "mil_budget_change": 0,
  "jets_change": 0,
  "tanks_change": 0,
  "refineries_change": 0,
  "satisfaction_change": 0,
  "narrative_short": "Persian short news...",
  "narrative_long": "Persian epic report..."
}}
"""

async def apply_battle_changes(context, user_id, country_name, data):
    if not data.get("success"):
        return
    if data.get("action_type") == "deploy" and data.get("region") != "None":
        asset = data.get("deployed_asset")
        qty = int(data.get("deployed_quantity", 0))
        if asset != "None" and qty > 0:
            async with pool.acquire() as conn:
                await conn.execute("INSERT INTO deployments (user_id, country_name, region, asset_type, model, quantity) VALUES ($1, $2, $3, $4, $5, $6)", user_id, country_name, data.get("region"), "aircraft", asset, qty)

async def create_encounter_ask_intent(context, order_id, user_id, country_name, asset, enemy, region):
    async with pool.acquire() as conn:
        enemy_row = await conn.fetchrow("SELECT model FROM deployments WHERE country_name = $1 AND region = $2 AND quantity > 0 LIMIT 1", enemy['country_name'], region)
    enemy_asset = enemy_row['model'] if enemy_row else 'نامشخص'
    our_radar = get_radar_range(asset)
    enemy_radar = get_radar_range(enemy_asset)
    if our_radar >= enemy_radar:
        det_id, det_c, det_a = user_id, country_name, asset
        ed_id, ed_c, ed_a = enemy['user_id'], enemy['country_name'], enemy_asset
        det_range, ed_range = our_radar, enemy_radar
    else:
        det_id, det_c, det_a = enemy['user_id'], enemy['country_name'], enemy_asset
        ed_id, ed_c, ed_a = user_id, country_name, asset
        det_range, ed_range = enemy_radar, our_radar
    async with pool.acquire() as conn:
        enc_id = await conn.fetchval("""
            INSERT INTO encounters (order_id, detector_id, detector_country, detector_asset,
                detected_id, detected_country, detected_asset, region, status)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'radar_contact') RETURNING id
        """, order_id, det_id, det_c, det_a, ed_id, ed_c, ed_a, region)
    kb_radar = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 شلیک موشک و شروع درگیری", callback_data=f"radar_launch_{enc_id}")],
        [InlineKeyboardButton("📻 هشدار رادیویی + اسکورت تا مرز", callback_data=f"radar_warn_{enc_id}")],
        [InlineKeyboardButton("🏃 عقب‌نشینی", callback_data=f"radar_retreat_{enc_id}")]
    ])
    try:
        await context.bot.send_message(det_id, f"📡 **تماس راداری در {region}**\n\nرادار شما ({det_a}) با برد **{det_range}km** دشمن را شناسایی کرد.\nرادار دشمن ({ed_a}) فقط **{ed_range}km** برد دارد.\n\n👤 **دشمن:** {ed_c}\n✈️ **جنگنده:** {ed_a}\n\n**تصمیم شما چیست؟**", reply_markup=kb_radar, parse_mode="Markdown")
    except:
        pass
    return enc_id

async def create_encounter_and_battle(context, order_id, user_id, country_name, asset, enemy, region):
    async with pool.acquire() as conn:
        enc_id = await conn.fetchval("""INSERT INTO encounters (order_id, detector_id, detector_country, detector_asset, detected_id, detected_country, detected_asset, region, detector_intent, detected_intent, status) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'attack', 'attack', 'battle') RETURNING id""", order_id, user_id, country_name, asset, enemy['user_id'], enemy['country_name'], "نیروی نامشخص", region)
        enemy_asset_row = await conn.fetchrow("SELECT model FROM deployments WHERE country_name = $1 AND region = $2 AND quantity > 0 LIMIT 1", enemy['country_name'], region)
        if enemy_asset_row:
            await conn.execute("UPDATE encounters SET detected_asset = $1 WHERE id = $2", enemy_asset_row['model'], enc_id)
        enc = dict(await conn.fetchrow("SELECT * FROM encounters WHERE id = $1", enc_id))
    await simulate_encounter_battle(context, enc_id, enc)
    return enc_id

async def handle_intent_response(context, enc_id, user_id, intent):
    async with pool.acquire() as conn:
        enc = await conn.fetchrow("SELECT * FROM encounters WHERE id = $1", enc_id)
        if not enc or enc['status'] != 'awaiting_intent':
            return
        if user_id == enc['detector_id']:
            await conn.execute("UPDATE encounters SET detector_intent = $1 WHERE id = $2 AND detector_intent = 'pending'", intent, enc_id)
        elif user_id == enc['detected_id']:
            await conn.execute("UPDATE encounters SET detected_intent = $1 WHERE id = $2 AND detected_intent = 'pending'", intent, enc_id)
        else:
            return
        enc = await conn.fetchrow("SELECT * FROM encounters WHERE id = $1", enc_id)
        if enc['detector_intent'] == 'pending' or enc['detected_intent'] == 'pending':
            return
        det_intent = enc['detector_intent']
        ed_intent = enc['detected_intent']
        if det_intent == 'retreat' and ed_intent == 'retreat':
            await conn.execute("UPDATE encounters SET status = 'avoided' WHERE id = $1", enc_id)
            for uid in [enc['detector_id'], enc['detected_id']]:
                try:
                    await context.bot.send_message(uid, "🕊️ هر دو طرف عقب‌نشینی کردند.")
                except:
                    pass
        elif (det_intent == 'retreat' and ed_intent == 'attack') or (ed_intent == 'retreat' and det_intent == 'attack'):
            await conn.execute("UPDATE encounters SET status = 'battle' WHERE id = $1", enc_id)
            await simulate_encounter_battle(context, enc_id, dict(enc))
        elif det_intent == 'retreat' or ed_intent == 'retreat':
            await conn.execute("UPDATE encounters SET status = 'avoided' WHERE id = $1", enc_id)
            for uid in [enc['detector_id'], enc['detected_id']]:
                try:
                    await context.bot.send_message(uid, "🕊️ درگیری رخ نداد، یک طرف عقب‌نشینی کرد.")
                except:
                    pass
        elif det_intent == 'attack' or ed_intent == 'attack':
            await conn.execute("UPDATE encounters SET status = 'battle' WHERE id = $1", enc_id)
            await simulate_encounter_battle(context, enc_id, dict(enc))
        else:
            await conn.execute("UPDATE encounters SET status = 'patrol_only' WHERE id = $1", enc_id)
            for uid in [enc['detector_id'], enc['detected_id']]:
                try:
                    await context.bot.send_message(uid, "🕊️ هر دو طرف فقط گشت‌زنی کردند.")
                except:
                    pass

async def simulate_encounter_battle(context, enc_id, enc):
    async with pool.acquire() as conn:
        det_country = await conn.fetchrow("SELECT * FROM countries WHERE user_id = $1", enc['detector_id'])
        ed_country = await conn.fetchrow("SELECT * FROM countries WHERE user_id = $1", enc['detected_id'])
        await conn.execute("UPDATE encounters SET status = 'resolved' WHERE id = $1", enc_id)
    if not det_country or not ed_country:
        return
    det_spec = "نامشخص"
    ed_spec = "نامشخص"
    for key, spec in AIRCRAFT_SPECS.items():
        if key.lower() in enc['detector_asset'].lower():
            det_spec = spec
        if key.lower() in enc['detected_asset'].lower():
            ed_spec = spec
    det_intent = enc.get('detector_intent', 'attack')
    ed_intent = enc.get('detected_intent', 'attack')
    prompt = f"""You are an elite tactical air combat simulator for the year 1979.
=== AIRCRAFT TECHNICAL ANALYSIS ===
DETECTOR: {enc['detector_country']} | Aircraft: {enc['detector_asset']} | Specs: {det_spec} | Intent: {det_intent.upper()}
DETECTED: {enc['detected_country']} | Aircraft: {enc['detected_asset']} | Specs: {ed_spec} | Intent: {ed_intent.upper()}

=== COMBAT RULES ===
1. BVR PHASE: Compare radar/missiles. Describe evasion (CHAFF, terrain masking). Calculate losses.
2. WVR PHASE: Compare maneuverability. Describe IR missiles, FLARES, GUNS. Calculate losses.
3. PILOT SURVIVAL: For every jet destroyed, determine if pilot(s) EJECTED or DIED. Modern jets have high survival rates.

Output JSON only:
{{
  "detector_losses": integer,
  "detected_losses": integer,
  "detector_pilot_deaths": integer,
  "detected_pilot_deaths": integer,
  "narrative": "Persian detailed tactical report including BVR, WVR, and pilot ejections."
}}"""
    ai_response = await ask_ai(prompt)
    data = _safe_parse_json(ai_response)
    det_losses = max(0, int(data.get('detector_losses', 0)))
    ed_losses = max(0, int(data.get('detected_losses', 0)))
    det_p_deaths = max(0, int(data.get('detector_pilot_deaths', 0)))
    ed_p_deaths = max(0, int(data.get('detected_pilot_deaths', 0)))
    narrative = _clean_persian_text(data.get('narrative', 'نبردی شدید رخ داد.'))
    async with pool.acquire() as conn:
        await conn.execute("UPDATE countries SET jets = GREATEST(0, jets - $1), pilots = GREATEST(0, pilots - $2) WHERE user_id = $3", det_losses, det_p_deaths, enc['detector_id'])
        await conn.execute("UPDATE countries SET jets = GREATEST(0, jets - $1), pilots = GREATEST(0, pilots - $2) WHERE user_id = $3", ed_losses, ed_p_deaths, enc['detected_id'])
        await conn.execute("UPDATE deployments SET quantity = GREATEST(0, quantity - $1) WHERE country_name = $2 AND region = $3", det_losses, enc['detector_country'], enc['region'])
        await conn.execute("UPDATE deployments SET quantity = GREATEST(0, quantity - $1) WHERE country_name = $2 AND region = $3", ed_losses, enc['detected_country'], enc['region'])
        await conn.execute("DELETE FROM deployments WHERE quantity <= 0")
        await conn.execute("UPDATE encounters SET battle_narrative = $1 WHERE id = $2", narrative, enc_id)
        await conn.execute("UPDATE orders SET final_narrative = $1 WHERE id = $2", narrative, enc['order_id'])
        det_data = await conn.fetchrow("SELECT alliance FROM countries WHERE user_id = $1", enc['detector_id'])
        ed_data = await conn.fetchrow("SELECT alliance FROM countries WHERE user_id = $1", enc['detected_id'])
    if det_data and ed_data and det_data['alliance'] != 'none' and det_data['alliance'] != ed_data['alliance']:
        async with pool.acquire() as conn:
            allies = await conn.fetch("SELECT user_id FROM countries WHERE alliance = $1 AND status = 'active' AND user_id != $2", ed_data['alliance'], enc['detected_id'])
        for ally in allies:
            try:
                await context.bot.send_message(ally['user_id'], f"🚨 **فعال شدن پیمان {ed_data['alliance']}!**\n\n{enc['detected_country']} در {enc['region']} مورد حمله قرار گرفت.")
            except:
                pass
    battle_msg = f"⚔️ **نتیجه نبرد در {enc['region']}**\n\n🏴 **{enc['detector_country']}**: {det_losses} فروند، {det_p_deaths} خلبان\n🏳️ **{enc['detected_country']}**: {ed_losses} فروند، {ed_p_deaths} خلبان\n\n📖 **تحلیل:**\n{narrative}"
    for uid in [enc['detector_id'], enc['detected_id']]:
        try:
            await context.bot.send_message(uid, battle_msg, parse_mode="Markdown")
        except:
            pass

async def _analyze_inner(order_id: int, context):
    async with pool.acquire() as conn:
        order = await conn.fetchrow("SELECT * FROM orders WHERE id = $1", order_id)
        if not order:
            return {"success": False, "reason": "سفارش یافت نشد", "narrative_short": "", "narrative_long": ""}
        country = await conn.fetchrow("SELECT * FROM countries WHERE user_id = $1", order["user_id"])
    enemy_str = await get_enemy_deployments_str(country['name'])
    prompt = _build_prompt(dict(country), order["order_text"], order["category"], enemy_str)
    ai_response = await ask_ai(prompt)
    data = _safe_parse_json(ai_response)
    if "success" not in data or "narrative_long" not in data:
        data = {"success": False, "reason": "پاسخ نامعتبر بود", "narrative_short": "خطا", "narrative_long": "بررسی دستی.", "gdp_change": 0, "mil_budget_change": 0, "jets_change": 0, "tanks_change": 0, "refineries_change": 0, "satisfaction_change": 0, "battle_occurred": False, "order_intent": "unknown", "region": "None", "target_country": "None"}
    for k in ["narrative_short", "narrative_long", "reason", "target_country"]:
        if k in data:
            data[k] = _clean_persian_text(str(data[k]))
    order_intent = data.get("order_intent", "deploy")
    region = data.get("region", "None")
    action_type = data.get("action_type", "economic")
    target_country = data.get("target_country", "None")
    deployed_asset = data.get("deployed_asset", "نیروی نامشخص")
    if action_type == "diplomacy" and target_country != "None":
        async with pool.acquire() as conn:
            target_data = await conn.fetchrow("SELECT user_id FROM countries WHERE name = $1 AND status = 'active'", target_country)
        if not target_data:
            data["success"] = False
            data["reason"] = f"{target_country} فعال نیست."
        else:
            async with pool.acquire() as conn:
                await conn.execute("UPDATE orders SET status = 'diplo_pending', target_country = $1, ai_analysis_raw = $2 WHERE id = $3", target_country, json.dumps(data, ensure_ascii=False), order_id)
            try:
                await context.bot.send_message(target_data['user_id'], f"🤝 **درخواست دیپلماتیک از {country['name']}**\n\n📜 متن: {order['order_text']}", reply_markup=kb([[InlineKeyboardButton("✅ قبول", callback_data=f"diplo_accept_{order_id}")], [InlineKeyboardButton("❌ رد", callback_data=f"diplo_reject_{order_id}")]]))
            except:
                pass
            return data
    if data.get("success"):
        try:
            g_change = int(data.get("gdp_change") or 0)
            m_change = int(data.get("mil_budget_change") or 0)
            j_change = int(data.get("jets_change") or 0)
            t_change = int(data.get("tanks_change") or 0)
            r_change = int(data.get("refineries_change") or 0)
            s_change = int(data.get("satisfaction_change") or 0)
            if action_type in ["deploy", "attack"]:
                j_change = 0
                t_change = 0
        except:
            data = {"success": False, "reason": "خطای عددی", "narrative_short": "", "narrative_long": "", "gdp_change": 0, "mil_budget_change": 0, "jets_change": 0, "tanks_change": 0, "refineries_change": 0, "satisfaction_change": 0, "battle_occurred": False, "order_intent": order_intent, "region": region}
        else:
            if country["gdp"] + g_change < 0 or country["mil_budget"] + m_change < 0:
                data = {"success": False, "reason": "ورشکستگی!", "gdp_change": 0, "mil_budget_change": 0, "jets_change": 0, "tanks_change": 0, "refineries_change": 0, "satisfaction_change": -5, "narrative_short": "فروپاشی", "narrative_long": "بودجه کافی نیست.", "battle_occurred": False, "order_intent": order_intent, "region": region}
            else:
                new_sat = max(0, min(100, country.get("satisfaction", 50) + s_change))
                data["satisfaction_change"] = new_sat - country.get("satisfaction", 50)
                async with pool.acquire() as conn:
                    await conn.execute("UPDATE countries SET gdp = GREATEST(0, gdp + $1), mil_budget = GREATEST(0, mil_budget + $2), jets = GREATEST(0, jets + $3), tanks = GREATEST(0, tanks + $4), refineries = GREATEST(0, refineries + $5), satisfaction = $6 WHERE user_id = $7", g_change, m_change, j_change, t_change, r_change, new_sat, order["user_id"])
                await apply_battle_changes(context, order["user_id"], country['name'], data)
    enemy = None
    if action_type in ["deploy", "attack"] and region and region != "None":
        async with pool.acquire() as conn:
            enemy_row = await conn.fetchrow("SELECT user_id, country_name FROM deployments WHERE region = $1 AND country_name != $2 AND quantity > 0 LIMIT 1", region, country['name'])
            if enemy_row:
                enemy = dict(enemy_row)
    async with pool.acquire() as conn:
        await conn.execute("UPDATE orders SET order_intent = $1, region = $2, ai_analysis_raw = $3, enemy_user_id = $4 WHERE id = $5", order_intent, region, json.dumps(data, ensure_ascii=False), enemy['user_id'] if enemy else None, order_id)
    if enemy and action_type in ["deploy", "attack"]:
        if order_intent == "attack":
            enc_id = await create_encounter_and_battle(context, order_id, order["user_id"], country['name'], deployed_asset, enemy, region)
        elif order_intent in ["patrol", "deploy"]:
            enc_id = await create_encounter_ask_intent(context, order_id, order["user_id"], country['name'], deployed_asset, enemy, region)
    return data

async def analyze_and_apply_order(order_id: int, context):
    try:
        return await asyncio.wait_for(_analyze_inner(order_id, context), timeout=120.0)
    except asyncio.TimeoutError:
        data = {"success": False, "reason": "تایم اوت", "narrative_short": "تاخیر", "narrative_long": "پردازش طول کشید.", "gdp_change": 0, "mil_budget_change": 0, "jets_change": 0, "tanks_change": 0, "refineries_change": 0, "satisfaction_change": 0, "battle_occurred": False, "order_intent": "unknown", "region": "None", "target_country": "None"}
        async with pool.acquire() as conn:
            await conn.execute("UPDATE orders SET status='ai_analyzed', ai_analysis_raw=$1 WHERE id=$2", json.dumps(data, ensure_ascii=False), order_id)
        return data
    except Exception as e:
        logger.error(f"AI Error: {e}")
        data = {"success": False, "reason": f"خطا: {str(e)[:50]}", "narrative_short": "خطا", "narrative_long": "خطای داخلی.", "gdp_change": 0, "mil_budget_change": 0, "jets_change": 0, "tanks_change": 0, "refineries_change": 0, "satisfaction_change": 0, "battle_occurred": False, "order_intent": "unknown", "region": "None", "target_country": "None"}
        async with pool.acquire() as conn:
            await conn.execute("UPDATE orders SET status='ai_analyzed', ai_analysis_raw=$1 WHERE id=$2", json.dumps(data, ensure_ascii=False), order_id)
        return data

async def handle_radar_launch(context, enc_id, uid):
    async with pool.acquire() as conn:
        enc = await conn.fetchrow("SELECT * FROM encounters WHERE id = $1", enc_id)
        if not enc or enc['status'] != 'radar_contact' or uid != enc['detector_id']:
            return
        await conn.execute("UPDATE encounters SET status='missile_incoming', detector_intent='attack' WHERE id=$1", enc_id)
    try:
        await context.bot.send_message(uid, f"🚀 **موشک شلیک شد!**\n\nموشک به سمت {enc['detected_asset']} در حرکت است. دشمن تا ۳۰ کیلومتری خبر ندارد...")
    except:
        pass
    await asyncio.sleep(3)
    kb_missile = InlineKeyboardMarkup([
        [InlineKeyboardButton("🏃 عقب‌نشینی فوری (فرار)", callback_data=f"missile_retreat_{enc_id}")],
        [InlineKeyboardButton("⚔️ ورود به درگیری", callback_data=f"missile_engage_{enc_id}")]
    ])
    try:
        await context.bot.send_message(enc['detected_id'], f"🚨 **هشدار! موشک در ۳۰ کیلومتری!**\n\nسیستم هشدار رادار شما موشکی را شناسایی کرد!\nشلیک‌کننده: **{enc['detector_country']}**\n\n⏱ شما فقط چند ثانیه فرصت دارید!\n**تصمیم؟**", reply_markup=kb_missile, parse_mode="Markdown")
    except:
        pass

async def handle_radar_warn(context, enc_id, uid):
    async with pool.acquire() as conn:
        enc = await conn.fetchrow("SELECT * FROM encounters WHERE id = $1", enc_id)
        if not enc or enc['status'] != 'radar_contact' or uid != enc['detector_id']:
            return
        await conn.execute("UPDATE encounters SET status='warned', detector_intent='patrol' WHERE id=$1", enc_id)
    for u in [enc['detector_id'], enc['detected_id']]:
        try:
            await context.bot.send_message(u, f"📻 **هشدار رادیویی در {enc['region']}**\n\n{enc['detector_country']} پیام هشدار فرستاد و {enc['detected_country']} را تا مرز اسکورت کرد.\nهیچ درگیری رخ نداد. 🕊️")
        except:
            pass

async def handle_radar_retreat(context, enc_id, uid):
    async with pool.acquire() as conn:
        enc = await conn.fetchrow("SELECT * FROM encounters WHERE id = $1", enc_id)
        if not enc or enc['status'] != 'radar_contact' or uid != enc['detector_id']:
            return
        await conn.execute("UPDATE encounters SET status='avoided', detector_intent='retreat' WHERE id=$1", enc_id)
    try:
        await context.bot.send_message(uid, f"🏃 عقب‌نشینی از {enc['region']} انجام شد.")
    except:
        pass
    try:
        await context.bot.send_message(enc['detected_id'], f"📡 رادار شما {enc['detector_country']} را دید اما آنها عقب‌نشینی کردند.")
    except:
        pass

async def handle_missile_response(context, enc_id, uid, choice):
    async with pool.acquire() as conn:
        enc = await conn.fetchrow("SELECT * FROM encounters WHERE id = $1", enc_id)
        if not enc or enc['status'] != 'missile_incoming' or uid != enc['detected_id']:
            return
        await conn.execute("UPDATE encounters SET status='battle', detected_intent=$1 WHERE id=$2", choice, enc_id)
    await simulate_encounter_battle(context, enc_id, dict(enc))

async def set_commands(app):
    await app.bot.set_my_commands([
        BotCommand("start", "ثبت‌نام"),
        BotCommand("country", "اطلاعات کشور"),
        BotCommand("military", "آرشیو نظامی"),
        BotCommand("economy", "انبار منابع"),
        BotCommand("factory", "کارخانه‌ها"),
        BotCommand("mines", "معادن"),
        BotCommand("order", "دستور جدید"),
        BotCommand("research", "تحقیق و توسعه"),
        BotCommand("admin", "پنل ادمین"),
        BotCommand("unban", "رفع مسدودی (ادمین)")
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if check_spam(uid):
        async with pool.acquire() as conn:
            await conn.execute("UPDATE countries SET status = 'spam_banned' WHERE user_id = $1", uid)
        return await update.message.reply_text("🚫 شما به دلیل اسپم مسدود شدید.")
    async with pool.acquire() as conn:
        c = await conn.fetchrow("SELECT * FROM countries WHERE user_id = $1", uid)
    if c:
        if c["status"] == "active":
            await context.bot.send_message(uid, f"✅ کشور {c['name']} فعال است.")
        elif c["status"] in ["banned", "spam_banned"]:
            await context.bot.send_message(uid, "🚫 شما مسدود هستید.")
        elif c["status"] == "pending":
            await context.bot.send_message(uid, "⏳ در انتظار تایید ادمین.")
        return
    temp[uid] = {"step": "SELECT_COUNTRY"}
    await context.bot.send_message(uid, f"🏛️ **Welcome to rustabad RP (1979)**\n\nلطفاً نام کشور خود را انتخاب کنید:\n\n{'، '.join(ALLOWED_COUNTRIES)}", parse_mode="Markdown")

async def country_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with pool.acquire() as conn:
        c = await conn.fetchrow("SELECT * FROM countries WHERE user_id = $1", update.effective_user.id)
    if not c or c["status"] != "active":
        return await update.message.reply_text("⚠️ شما مجاز نیستید. /start")
    data = COUNTRY_DB.get(c['name'])
    text = (
        f"🏛️ *کشور: {c['name']}* (۱۹۷۹)\n"
        f"🏙️ *شهرها:* {data['cities'] if data else 'نامشخص'}\n\n"
        f"📈 GDP: {fmt_money(c['gdp'])}\n"
        f"🛡 بودجه: {fmt_money(c['mil_budget'])}\n"
        f"✈️ جنگنده‌ها: {c['jets']:,}\n"
        f"🚜 تانک‌ها: {c.get('tanks', 0):,}\n"
        f"✈️ خلبان‌ها: {c.get('pilots', 0):,}\n"
        f"🤝 اتحاد: {c.get('alliance', 'none')}\n"
        f"🏭 پالایش: {c['refineries']:,}\n"
        f"🎖 ارتش: {c['army']:,}\n"
        f"❤️ رضایت: {c.get('satisfaction', 50)}%"
    )
    await context.bot.send_message(update.effective_user.id, text, parse_mode="Markdown")

async def military_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with pool.acquire() as conn:
        c = await conn.fetchrow("SELECT * FROM countries WHERE user_id = $1", update.effective_user.id)
        if not c:
            return
        deployments = await conn.fetch("SELECT * FROM deployments WHERE country_name = $1 AND quantity > 0", c['name'])
    if c["status"] != "active":
        return await update.message.reply_text("⚠️ شما مجاز نیستید.")
    mil_data = MILITARY_DB.get(c['name'])
    if not mil_data:
        return
    personnel_str = PERSONNEL_DB.get(c['name'], f"کل: {c['army']:,} نفر")
    deploy_str = "هیچ نیرویی مستقر نیست." if not deployments else "\n".join([f"• 📍 {d['region']}: {d['quantity']} {d['model']}" for d in deployments])
    def fmt_b(text):
        return "\n   🔸 ".join(text.split(" | ")) if text else "نامشخص"
    text = (
        f"⚔️ *آرشیو نظامی {c['name']}*\n\n"
        f"👥 **پرسنل:**\n{personnel_str}\n\n"
        f"🛡 **بودجه:** {fmt_money(c['mil_budget'])}\n"
        f"✈️ **خلبانان:** {c.get('pilots', 0):,} نفر\n\n"
        f"🚜 **زمینی:**\n   🔸 {fmt_b(mil_data.get('نیروی زمینی', ''))}\n\n"
        f"✈️ **هوایی:**\n   🔸 {fmt_b(mil_data.get('نیروی هوایی', ''))}\n\n"
        f"💥 **توپخانه:**\n   🔸 {fmt_b(mil_data.get('توپخانه', ''))}\n\n"
        f"⚓ **دریایی:**\n   🔸 {fmt_b(mil_data.get('نیروی دریایی', ''))}\n\n"
        f"🛡 **پدافند:**\n   🔸 {fmt_b(mil_data.get('پدافند هوایی', ''))}\n\n"
        f"📍 **استقرارها:**\n{deploy_str}"
    )
    await context.bot.send_message(update.effective_user.id, text, parse_mode="Markdown")

async def economy_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with pool.acquire() as conn:
        c = await conn.fetchrow("SELECT * FROM countries WHERE user_id = $1", update.effective_user.id)
    if not c or c["status"] != "active":
        return
    res_text = "".join([f"{v}: {c.get(f'res_{k}', 0):,}\n" for k, v in RESOURCES.items() if c.get(f'res_{k}', 0) > 0]) or "خالی."
    await context.bot.send_message(update.effective_user.id, f"💰 *اقتصاد {c['name']}*\n🏦 GDP: {fmt_money(c['gdp'])}\n\n📦 *انبار:*\n{res_text}", parse_mode="Markdown")

async def mines_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with pool.acquire() as conn:
        c = await conn.fetchrow("SELECT * FROM countries WHERE user_id = $1", update.effective_user.id)
    if not c or c["status"] != "active":
        return
    data = COUNTRY_DB.get(c['name'])
    if not data:
        return
    text = f"⛏ *معادن {c['name']}*\n\n" + "".join([f"🔹 {m['name']}\n📦 {m['amount']:,} واحد {RESOURCES.get(m['output_res'], m['output_res'])}\n\n" for m in data['mines'].values()])
    await context.bot.send_message(update.effective_user.id, text, parse_mode="Markdown")

async def factory_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with pool.acquire() as conn:
        c = await conn.fetchrow("SELECT * FROM countries WHERE user_id = $1", update.effective_user.id)
        if not c:
            return
        infras = await conn.fetch("SELECT sector_type, count(*) as count FROM infrastructure WHERE user_id = $1 GROUP BY sector_type", update.effective_user.id)
    if c["status"] != "active":
        return
    counts = {r['sector_type']: r['count'] for r in infras}
    data = COUNTRY_DB.get(c['name'])
    if not data:
        return
    real_f = FACTORY_DB.get(c['name'], {})
    fac_str = "\n".join([f"🏭 {m}: {l}" for m, l in real_f.items()]) if real_f else "نامشخص."
    rows = [[InlineKeyboardButton(f"🏭 {f['name']} | {fmt_money(f['cost'])}", callback_data=f"fact_build_{k}")] for k, f in data['factories'].items() if counts.get(k, 0) < 5]
    await context.bot.send_message(update.effective_user.id, f"🏭 *کارخانه‌های {c['name']}*\n\n**خطوط تولید ۱۹۷۹:**\n{fac_str}\n\nساخت کارخانه جدید:", parse_mode="Markdown", reply_markup=kb(rows))

async def order_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    async with pool.acquire() as conn:
        c = await conn.fetchrow("SELECT * FROM countries WHERE user_id = $1", uid)
    if not c or c["status"] != "active":
        return await update.message.reply_text("⚠️ مجاز نیستید.")
    temp[uid] = {"step": "ORDER_CATEGORY"}
    await update.message.reply_text("دسته‌بندی دستور:", reply_markup=kb([[InlineKeyboardButton("💰 اقتصادی", callback_data="cat_economic"), InlineKeyboardButton("🏛️ سیاسی", callback_data="cat_political")], [InlineKeyboardButton("🤝 دیپلماسی", callback_data="cat_diplomacy"), InlineKeyboardButton("⚔️ نظامی", callback_data="cat_military")]]))

async def research_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    async with pool.acquire() as conn:
        c = await conn.fetchrow("SELECT * FROM countries WHERE user_id = $1", uid)
    if not c or c["status"] != "active":
        return
    if c.get("researching_tech") != 'None' and c.get("research_turns_left", 0) > 0:
        return await update.message.reply_text(f"🔬 در حال تحقیق: {c['researching_tech']}\n⏳ نوبت باقی‌مانده: {c['research_turns_left']}")
    techs = TECH_TREE.get(c['name'])
    if not techs:
        return await update.message.reply_text("⚠️ درخت تکنولوژی ندارید.")
    rows = [[InlineKeyboardButton(f"🔬 {t} | {fmt_money(i['cost'])} | {i['turns']} نوبت", callback_data=f"res_start_{t}")] for t, i in techs.items()]
    await update.message.reply_text("🔬 **مرکز تحقیق و توسعه**\nتکنولوژی مورد نظر:", reply_markup=kb(rows))

async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    await update.message.reply_text(
        "👑 **پنل مدیریت کل**\nبخش مورد نظر:",
        reply_markup=kb([
            [InlineKeyboardButton("🌍 کشورهای فعال", callback_data="adm_list_active_0"), InlineKeyboardButton("🚫 مسدودها", callback_data="adm_list_banned_0")],
            [InlineKeyboardButton("⏳ در انتظار", callback_data="adm_list_pending_0")],
            [InlineKeyboardButton("⏳ پردازش نوبت", callback_data="adm_next_turn")],
            [InlineKeyboardButton("💰 تنظیم GDP", callback_data="adm_set_gdp")]
        ]),
        parse_mode="Markdown"
    )

async def unban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        return await update.message.reply_text("⚠️ استفاده: `/unban آیدی`")
    try:
        target = int(context.args[0])
        async with pool.acquire() as conn:
            await conn.execute("UPDATE countries SET status = 'active' WHERE user_id = $1", target)
        await update.message.reply_text(f"✅ کاربر {target} آزاد شد.")
    except:
        await update.message.reply_text("❌ آیدی باید عدد باشد.")

async def show_admin_list(chat_id, msg_id, context, page, list_type):
    async with pool.acquire() as conn:
        if list_type == "banned":
            countries = await conn.fetch("SELECT * FROM countries WHERE status IN ('banned', 'spam_banned') ORDER BY created_at DESC")
            title = "🚫 **لیست مسدودها**"
        elif list_type == "pending":
            countries = await conn.fetch("SELECT * FROM countries WHERE status = 'pending' ORDER BY created_at DESC")
            title = "⏳ **در انتظار تایید**"
        else:
            countries = await conn.fetch("SELECT * FROM countries WHERE status = 'active' ORDER BY created_at DESC")
            title = "🌍 **کشورهای فعال**"
    per_page = 5
    start = page * per_page
    end = start + per_page
    page_items = countries[start:end]
    text = f"{title} (صفحه {page+1})\n\n"
    buttons = []
    if not page_items:
        text += "خالی است."
    for c in page_items:
        status_icon = "✅" if c['status'] == 'active' else "🚫" if c['status'] in ['banned', 'spam_banned'] else "⏳"
        buttons.append([InlineKeyboardButton(f"{status_icon} {c['name']} | {c['username'] or 'بدون آیدی'}", callback_data=f"adm_view_{c['user_id']}")])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"adm_list_{list_type}_{page-1}"))
    if end < len(countries):
        nav.append(InlineKeyboardButton("➡️", callback_data=f"adm_list_{list_type}_{page+1}"))
    nav.append(InlineKeyboardButton("🔙 بازگشت", callback_data="adm_panel"))
    buttons.append(nav)
    try:
        await context.bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=text, parse_mode="Markdown", reply_markup=kb(buttons))
    except:
        pass

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if check_spam(uid):
        async with pool.acquire() as conn:
            await conn.execute("UPDATE countries SET status = 'spam_banned' WHERE user_id = $1", uid)
        return await update.message.reply_text("🚫 اسپم! مسدود شدید.")
    async with pool.acquire() as conn:
        c = await conn.fetchrow("SELECT status FROM countries WHERE user_id = $1", uid)
    if c and c['status'] == 'banned':
        return await update.message.reply_text("🚫 مسدود هستید.")
    text = update.message.text.strip()
    t = temp.get(uid, {})
    if t.get("step") == "SELECT_COUNTRY":
        if text not in ALLOWED_COUNTRIES:
            return await context.bot.send_message(uid, "❌ کشور نامعتبر.")
        async with pool.acquire() as conn:
            if await conn.fetchval("SELECT 1 FROM countries WHERE name = $1 AND status != 'rejected'", text):
                return await context.bot.send_message(uid, "❌ قبلاً انتخاب شده.")
            data = COUNTRY_DB[text]
            await conn.execute("INSERT INTO countries (user_id, username, name, status, gdp, mil_budget, jets, tanks, refineries, army, pilots) VALUES ($1, $2, $3, 'pending', $4, $5, $6, $7, $8, $9, $10)", uid, update.effective_user.username or "بدون", text, data['gdp_init'], data['mil_budget_init'], data['jets_init'], data['tanks_init'], data['refineries_init'], data['army_init'], PILOT_DB.get(text, 1000))
        temp.pop(uid, None)
        await context.bot.send_message(uid, "⏳ در انتظار تایید.")
        await context.bot.send_message(ADMIN_ID, f"📥 **درخواست جدید**\n🌍 {text}\n🆔 `{uid}`", parse_mode="Markdown", reply_markup=kb([[InlineKeyboardButton("✅ تایید", callback_data=f"adm_ok_{uid}"), InlineKeyboardButton("❌ رد", callback_data=f"adm_rej_{uid}")]]))
    elif t.get("step") == "AWAITING_ORDER_TEXT":
        temp[uid] = {"step": "SELECT_VISIBILITY", "category": t.get("category"), "order_text": text}
        await update.message.reply_text("انتشار عمومی یا محرمانه؟", reply_markup=kb([[InlineKeyboardButton("🌍 عمومی", callback_data="vis_public")], [InlineKeyboardButton("🤫 محرمانه", callback_data="vis_secret")]]))
    elif t.get("step") == "ADMIN_SET_GDP_ID" and uid == ADMIN_ID:
        try:
            temp[uid] = {"step": "ADMIN_SET_GDP_AMOUNT", "target_id": int(text)}
            await update.message.reply_text("مقدار GDP:")
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
    if data == "adm_panel" and uid == ADMIN_ID:
        await cb.edit_message_text(
            "👑 **پنل مدیریت کل**",
            reply_markup=kb([
                [InlineKeyboardButton("🌍 کشورهای فعال", callback_data="adm_list_active_0"), InlineKeyboardButton("🚫 مسدودها", callback_data="adm_list_banned_0")],
                [InlineKeyboardButton("⏳ در انتظار", callback_data="adm_list_pending_0")],
                [InlineKeyboardButton("⏳ پردازش نوبت", callback_data="adm_next_turn")],
                [InlineKeyboardButton("💰 تنظیم GDP", callback_data="adm_set_gdp")]
            ]),
            parse_mode="Markdown"
        )
    elif data.startswith("adm_list_") and uid == ADMIN_ID:
        parts = data.split("_")
        await show_admin_list(uid, cb.message.message_id, context, int(parts[3]), parts[2])
    elif data.startswith("adm_view_") and uid == ADMIN_ID:
        target = int(data.split("_")[2])
        async with pool.acquire() as conn:
            c = await conn.fetchrow("SELECT * FROM countries WHERE user_id = $1", target)
        if not c:
            return await cb.answer("یافت نشد.", show_alert=True)
        data_info = COUNTRY_DB.get(c['name'], {})
        gov_name = GOVERNMENTS.get(c.get('gov_main', ''), {}).get('name', c.get('gov_main', 'نامشخص'))
        gov_sub = GOVERNMENTS.get(c.get('gov_main', ''), {}).get('subs', {}).get(c.get('gov_sub', ''), '')
        cities = data_info.get('cities', 'نامشخص')
        status_fa = {"active": "✅ فعال", "pending": "⏳ در انتظار", "banned": "🚫 بن", "spam_banned": "🤖 اسپم"}.get(c['status'], c['status'])
        text = f"👤 **پروفایل**\n\n🌍 **کشور:** {c['name']}\n👤 **رهبر:** {c.get('leader', 'نامشخص')}\n⚙️ **حکومت:** {gov_name} - {gov_sub}\n🏙️ **شهرها:** {cities}\n🆔 **آیدی پلیر:** `{c['user_id']}`\n📌 **وضعیت:** {status_fa}\n📈 **GDP:** {fmt_money(c['gdp'])}"
        buttons = []
        if c['status'] in ['banned', 'spam_banned']:
            buttons.append([InlineKeyboardButton("✅ آنبن", callback_data=f"adm_unban_{target}")])
        else:
            buttons.append([InlineKeyboardButton("🚫 بن", callback_data=f"adm_ban_{target}")])
        buttons.append([InlineKeyboardButton("🔄 ریست آمار", callback_data=f"adm_reset_{target}"), InlineKeyboardButton("🗑 حذف کامل", callback_data=f"adm_del_{target}")])
        buttons.append([InlineKeyboardButton("🔙 بازگشت", callback_data="adm_list_active_0")])
        await cb.edit_message_text(text, parse_mode="Markdown", reply_markup=kb(buttons))
    elif data.startswith("adm_ban_") and uid == ADMIN_ID:
        target = int(data.split("_")[2])
        async with pool.acquire() as conn:
            await conn.execute("UPDATE countries SET status = 'banned' WHERE user_id = $1", target)
        await cb.answer("مسدود شد.", show_alert=True)
        await show_admin_list(uid, cb.message.message_id, context, 0, "banned")
    elif data.startswith("adm_unban_") and uid == ADMIN_ID:
        target = int(data.split("_")[2])
        async with pool.acquire() as conn:
            await conn.execute("UPDATE countries SET status = 'active' WHERE user_id = $1", target)
        await cb.answer("آزاد شد.", show_alert=True)
        await show_admin_list(uid, cb.message.message_id, context, 0, "active")
    elif data.startswith("adm_reset_") and uid == ADMIN_ID:
        target = int(data.split("_")[2])
        async with pool.acquire() as conn:
            c = await conn.fetchrow("SELECT name FROM countries WHERE user_id = $1", target)
            if c:
                init_data = COUNTRY_DB.get(c['name'])
                if init_data:
                    await conn.execute("UPDATE countries SET gdp = $1, mil_budget = $2, army = $3, tanks = $4, jets = $5, refineries = $6, pilots = $7, satisfaction = 50, status = 'active' WHERE user_id = $8", init_data['gdp_init'], init_data['mil_budget_init'], init_data['army_init'], init_data['tanks_init'], init_data['jets_init'], init_data['refineries_init'], PILOT_DB.get(c['name'], 1000), target)
                    await conn.execute("DELETE FROM deployments WHERE user_id = $1", target)
        await cb.answer("ریست شد.", show_alert=True)
        await cb.edit_message_text("✅ ریست شد.")
    elif data.startswith("adm_del_") and uid == ADMIN_ID:
        target = int(data.split("_")[2])
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM countries WHERE user_id = $1", target)
        await cb.answer("حذف شد.", show_alert=True)
        await cb.edit_message_text("🗑 حذف شد.")
    elif data.startswith("adm_ok_"):
        target = int(data.split("_")[2])
        async with pool.acquire() as conn:
            await conn.execute("UPDATE countries SET status = 'active' WHERE user_id = $1", target)
        await cb.edit_message_text("✅ تایید شد.")
        await context.bot.send_message(target, "🎉 تایید شد! /country")
    elif data.startswith("adm_rej_"):
        target = int(data.split("_")[2])
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM countries WHERE user_id = $1", target)
        await cb.edit_message_text("❌ رد شد.")
    elif data == "adm_next_turn":
        await cb.edit_message_text("⏳ در حال پردازش...")
        await process_turn(context)
    elif data == "adm_set_gdp":
        await cb.edit_message_text("🆔 آیدی:")
        temp[uid] = {"step": "ADMIN_SET_GDP_ID"}
    elif data.startswith("cat_"):
        category = data.replace("cat_", "")
        temp[uid] = {"step": "AWAITING_ORDER_TEXT", "category": category}
        cat_fa = {"economic": "اقتصادی", "political": "سیاسی", "diplomacy": "دیپلماسی", "military": "نظامی"}.get(category, "")
        await cb.edit_message_text(f"دسته: {cat_fa}\n\nمتن دستور را بنویسید:")
    elif data == "vis_public" or data == "vis_secret":
        is_public = (data == "vis_public")
        ot = t.get("order_text")
        category = t.get("category")
        temp.pop(uid, None)
        if not ot or not category:
            return await cb.edit_message_text("⚠️ منقضی شده.")
        if check_ai_limit(uid):
            return await cb.answer("⚠️ حداکثر ۴ دستور در دقیقه!", show_alert=True)
        async with pool.acquire() as conn:
            oid = await conn.fetchval("INSERT INTO orders (user_id, order_text, category, is_public) VALUES ($1, $2, $3, $4) RETURNING id", uid, ot, category, is_public)
            c = await conn.fetchrow("SELECT * FROM countries WHERE user_id = $1", uid)
        cat_fa = {"economic": "اقتصادی", "political": "سیاسی", "diplomacy": "دیپلماسی", "military": "نظامی"}.get(category, category)
        vis_fa = "عمومی" if is_public else "محرمانه"
        if category == "diplomacy":
            await cb.edit_message_text("⏳ تحلیل...")
            await send_analysis(cb, context, oid)
        else:
            await context.bot.send_message(ADMIN_ID, f"📜 **دستور جدید**\n🌍 {c['name']}\n🗂 {cat_fa} | {vis_fa}\n📝 {ot}", parse_mode="Markdown", reply_markup=kb([[InlineKeyboardButton("✅ تایید", callback_data=f"ord_appr_{oid}")], [InlineKeyboardButton("❌ رد", callback_data=f"ord_rej_{oid}")]]))
            await cb.edit_message_text("⏳ ارسال به ادمین.")
    elif data.startswith("res_start_"):
        tech_name = data.replace("res_start_", "")
        async with pool.acquire() as conn:
            c = await conn.fetchrow("SELECT * FROM countries WHERE user_id = $1", uid)
        if c.get("researching_tech") != 'None' and c.get("research_turns_left", 0) > 0:
            return await cb.answer("در حال تحقیق هستید!", show_alert=True)
        tech_info = TECH_TREE.get(c['name'], {}).get(tech_name)
        if not tech_info:
            return await cb.answer("نامعتبر.", show_alert=True)
        if c['gdp'] < tech_info['cost']:
            return await cb.answer("❌ GDP کافی نیست!", show_alert=True)
        async with pool.acquire() as conn:
            await conn.execute("UPDATE countries SET gdp = gdp - $1, researching_tech = $2, research_turns_left = $3 WHERE user_id = $4", tech_info['cost'], tech_name, tech_info['turns'], uid)
        await cb.edit_message_text(f"✅ تحقیق روی **{tech_name}** آغاز شد.\n⏳ {tech_info['turns']} نوبت.")
    elif data.startswith("diplo_accept_"):
        oid = int(data.split("_")[2])
        async with pool.acquire() as conn:
            order = await conn.fetchrow("SELECT * FROM orders WHERE id = $1", oid)
            if not order or order['status'] != 'diplo_pending':
                return await cb.edit_message_text("⚠️ منقضی شده.")
            await conn.execute("UPDATE orders SET status = 'pending_admin', player_approved = TRUE WHERE id = $1", oid)
            sender = await conn.fetchrow("SELECT name FROM countries WHERE user_id = $1", order['user_id'])
            receiver = await conn.fetchrow("SELECT name FROM countries WHERE user_id = $1", uid)
        await cb.edit_message_text("✅ قبول شد.")
        await context.bot.send_message(ADMIN_ID, f"🤝 **توافق دیپلماتیک**\n👤 {sender['name']} -> {receiver['name']}\n📝 {order['order_text']}", parse_mode="Markdown", reply_markup=kb([[InlineKeyboardButton("✅ تایید نهایی", callback_data=f"final_appr_{oid}")], [InlineKeyboardButton("❌ رد", callback_data=f"ord_rej_{oid}")]]))
    elif data.startswith("diplo_reject_"):
        oid = int(data.split("_")[2])
        async with pool.acquire() as conn:
            order = await conn.fetchrow("SELECT * FROM orders WHERE id = $1", oid)
            if order:
                await conn.execute("UPDATE orders SET status = 'rejected' WHERE id = $1", oid)
                receiver = await conn.fetchrow("SELECT name FROM countries WHERE user_id = $1", uid)
                try:
                    await context.bot.send_message(order['user_id'], f"❌ {receiver['name']} درخواست شما را رد کرد.")
                except:
                    pass
        await cb.edit_message_text("❌ رد شد.")
    elif data.startswith("final_appr_"):
        oid = int(data.split("_")[2])
        async with pool.acquire() as conn:
            order = await conn.fetchrow("SELECT * FROM orders WHERE id = $1", oid)
            if not order:
                return
            sender_country = await conn.fetchrow("SELECT name FROM countries WHERE user_id = $1", order['user_id'])
        try:
            ai_data = json.loads(order["ai_analysis_raw"] or "{}")
        except:
            ai_data = {}
        text_to_send = ai_data.get('narrative_long', 'توافق انجام شد.')
        final_text = f"📢 **بیانیه رسمی {sender_country['name']}**\n\n{text_to_send}"
        if order['status'] == 'pending_admin':
            try:
                g = int(ai_data.get("gdp_change") or 0)
                m = int(ai_data.get("mil_budget_change") or 0)
                j = int(ai_data.get("jets_change") or 0)
                t_change = int(ai_data.get("tanks_change") or 0)
                async with pool.acquire() as conn:
                    await conn.execute("UPDATE countries SET gdp = GREATEST(0, gdp + $1), mil_budget = GREATEST(0, mil_budget + $2), jets = GREATEST(0, jets + $3), tanks = GREATEST(0, tanks + $4) WHERE user_id = $5 OR name = $6", g, m, j, t_change, order['user_id'], order.get('target_country'))
                    await conn.execute("UPDATE orders SET status = 'published' WHERE id = $1", oid)
            except:
                pass
        if order['is_public']:
            if GROUP_ID and TOPIC_ID:
                try:
                    await context.bot.send_message(chat_id=int(GROUP_ID), text=final_text, message_thread_id=int(TOPIC_ID), parse_mode="Markdown")
                except:
                    pass
        await cb.edit_message_text("✅ تایید نهایی شد.")
    elif data.startswith("radar_launch_"):
        await cb.edit_message_text("🚀 شلیک...")
        await handle_radar_launch(context, int(data.split("_")[2]), uid)
    elif data.startswith("radar_warn_"):
        await cb.edit_message_text("📻 هشدار...")
        await handle_radar_warn(context, int(data.split("_")[2]), uid)
    elif data.startswith("radar_retreat_"):
        await cb.edit_message_text("🏃 عقب‌نشینی...")
        await handle_radar_retreat(context, int(data.split("_")[2]), uid)
    elif data.startswith("missile_retreat_"):
        await cb.edit_message_text("🏃 فرار...")
        await handle_missile_response(context, int(data.split("_")[2]), uid, "retreat")
    elif data.startswith("missile_engage_"):
        await cb.edit_message_text("⚔️ درگیری...")
        await handle_missile_response(context, int(data.split("_")[2]), uid, "attack")
    elif data.startswith("intent_patrol_"):
        await cb.edit_message_text("🕊️ گشت‌زنی.")
        await handle_intent_response(context, int(data.split("_")[2]), uid, "patrol")
    elif data.startswith("intent_attack_"):
        await cb.edit_message_text("⚔️ حمله.")
        await handle_intent_response(context, int(data.split("_")[2]), uid, "attack")
    elif data.startswith("intent_retreat_"):
        await cb.edit_message_text("🏃 عقب‌نشینی.")
        await handle_intent_response(context, int(data.split("_")[2]), uid, "retreat")
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
            country_data = await conn.fetchrow("SELECT name FROM countries WHERE user_id = $1", order['user_id'])
        try:
            ai_data = json.loads(order["ai_analysis_raw"] or "{}")
        except:
            ai_data = {}
        text_to_send = ai_data.get('narrative_short', '') if is_short else ai_data.get('narrative_long', '')
        country_name = country_data['name'] if country_data else "نامشخص"
        final_text = f"📢 **بیانیه رسمی {country_name}**\n\n{text_to_send}"
        is_attack = ai_data.get('action_type') == 'attack' or ai_data.get('order_intent') == 'attack'
        is_secret = (not order['is_public']) and (not is_attack)
        if is_secret:
            try:
                await context.bot.send_message(order['user_id'], f"🤫 **نتیجه محرمانه:**\n\n{text_to_send}")
            except:
                pass
            try:
                await context.bot.send_message(ADMIN_ID, f"🤫 **محرمانه از {country_name}:**\n\n{text_to_send}")
            except:
                pass
            async with pool.acquire() as conn:
                await conn.execute("UPDATE orders SET status = 'published' WHERE id = $1", oid)
            await cb.edit_message_text("✅ محرمانه ارسال شد.")
        else:
            if not order['is_public'] and is_attack:
                final_text = f"🚨 **افشای حمله نظامی!**\n\n{final_text}"
            sent = False
            if GROUP_ID and TOPIC_ID:
                try:
                    await context.bot.send_message(chat_id=int(GROUP_ID), text=final_text, message_thread_id=int(TOPIC_ID), parse_mode="Markdown")
                    sent = True
                except:
                    pass
            if not sent and CHANNEL_ID:
                try:
                    await context.bot.send_message(int(CHANNEL_ID.strip()), final_text)
                    sent = True
                except:
                    pass
            if sent:
                async with pool.acquire() as conn:
                    await conn.execute("UPDATE orders SET status = 'published' WHERE id = $1", oid)
                await cb.edit_message_text("✅ منتشر شد.")
            else:
                await cb.edit_message_text("❌ خطا در ارسال.")
    elif data == "cancel_pub":
        await cb.edit_message_text("❌ لغو شد.")
    elif data.startswith("fact_build_"):
        sector = data.replace("fact_build_", "")
        async with pool.acquire() as conn:
            c = await conn.fetchrow("SELECT * FROM countries WHERE user_id = $1", uid)
        req = COUNTRY_DB.get(c['name'], {}).get('factories', {}).get(sector)
        if not req or c['gdp'] < req['cost']:
            return await cb.answer("❌ GDP کافی نیست!", show_alert=True)
        async with pool.acquire() as conn:
            await conn.execute("UPDATE countries SET gdp = gdp - $1 WHERE user_id = $2", req['cost'], uid)
            await conn.execute("INSERT INTO infrastructure (user_id, sector_type, name, income) VALUES ($1, $2, $3, $4)", uid, sector, req['name'], req['income'])
        await cb.answer("✅ ساخته شد!", show_alert=True)

async def send_analysis(update_or_cb, context, order_id):
    ai_data = await analyze_and_apply_order(order_id, context)
    st = "✅ موفق" if ai_data.get("success") else "❌ ناموفق"
    ch = f"\n📈 GDP: {ai_data.get('gdp_change',0):+,} $ | ✈️ جنگنده: {ai_data.get('jets_change',0):+,} | 🚜 تانک: {ai_data.get('tanks_change',0):+,} | ❤️ رضایت: {ai_data.get('satisfaction_change',0):+,}\n" if ai_data.get("success") else ""
    async with pool.acquire() as conn:
        order = await conn.fetchrow("SELECT * FROM orders WHERE id = $1", order_id)
    is_attack = ai_data.get('action_type') == 'attack' or ai_data.get('order_intent') == 'attack'
    is_secret = (not order['is_public']) and (not is_attack)
    btn1 = "🤫 محرمانه (خلاصه)" if is_secret else "📢 خلاصه"
    btn2 = "🤫 محرمانه (کامل)" if is_secret else "📜 کامل"
    txt = f"🧠 تحلیل (70B)\n\n📌 وضعیت: {st}\n📝 دلیل: {ai_data.get('reason', '')}\n{ch}\n📰 **خلاصه:**\n{ai_data.get('narrative_short', '')}\n\n📖 **کامل:**\n{ai_data.get('narrative_long', '')}"
    btn = kb([[InlineKeyboardButton(btn1, callback_data=f"pub_short_{order_id}"), InlineKeyboardButton(btn2, callback_data=f"pub_long_{order_id}")], [InlineKeyboardButton("❌ لغو", callback_data="cancel_pub")]])
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
            updates = {f'res_{m["output_res"]}': c.get(f'res_{m["output_res"]}', 0) + m['amount'] for m in c_data['mines'].values()}
            if updates:
                set_clause = ", ".join([f"{k} = {v}" for k, v in updates.items()])
                await conn.execute(f"UPDATE countries SET {set_clause} WHERE user_id = $1", c['user_id'])
            if c.get("researching_tech") != 'None' and c.get("research_turns_left", 0) > 0:
                new_turns = c['research_turns_left'] - 1
                if new_turns <= 0:
                    await conn.execute("UPDATE countries SET researching_tech = 'None', research_turns_left = 0, jets = jets + 20 WHERE user_id = $1", c['user_id'])
                    try:
                        await context.bot.send_message(c['user_id'], f"🎉 **تحقیق تکمیل شد!**\nتکنولوژی **{c['researching_tech']}** توسعه یافت و ۲۰ فروند جنگنده اضافه شد.")
                    except:
                        pass
                else:
                    await conn.execute("UPDATE countries SET research_turns_left = $1 WHERE user_id = $2", new_turns, c['user_id'])
        infras = await conn.fetch("SELECT * FROM infrastructure")
        for i in infras:
            c = await conn.fetchrow("SELECT * FROM countries WHERE user_id = $1", i['user_id'])
            fact = COUNTRY_DB.get(c['name'], {}).get('factories', {}).get(i['sector_type'])
            if not fact:
                continue
            if c.get(f'res_{fact["consumes"]}', 0) >= 1000:
                await conn.execute(f"UPDATE countries SET res_{fact['consumes']} = res_{fact['consumes']} - 1000, res_{fact['produces']} = res_{fact['produces']} + 500, gdp = gdp + $1 WHERE user_id = $2", fact['income'], c['user_id'])
    await context.bot.send_message(ADMIN_ID, "✅ نوبت پردازش شد.")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(f"Update {update} caused error {context.error}", exc_info=context.error)
    try:
        await context.bot.send_message(ADMIN_ID, f"⚠️ خطا:\n`{type(context.error).__name__}: {str(context.error)[:200]}`", parse_mode="Markdown")
    except:
        pass

async def post_init(app):
    try:
        await init_db()
        await set_commands(app)
        await app.bot.delete_webhook(drop_pending_updates=True)
        logger.info("✅ Bot started successfully")
    except Exception as e:
        logger.error(f"❌ FATAL in post_init: {type(e).__name__}: {e}", exc_info=True)
        raise

def main():
    if not TOKEN:
        logger.error("❌ BOT_TOKEN is empty!")
        return
    if not DATABASE_URL:
        logger.error("❌ DATABASE_URL is empty!")
        return
    app = Application.builder().token(TOKEN).post_init(post_init).build()
    app.add_error_handler(error_handler)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("country", country_cmd))
    app.add_handler(CommandHandler("military", military_cmd))
    app.add_handler(CommandHandler("economy", economy_cmd))
    app.add_handler(CommandHandler("mines", mines_cmd))
    app.add_handler(CommandHandler("factory", factory_cmd))
    app.add_handler(CommandHandler("order", order_cmd))
    app.add_handler(CommandHandler("research", research_cmd))
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(CommandHandler("unban", unban_cmd))
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