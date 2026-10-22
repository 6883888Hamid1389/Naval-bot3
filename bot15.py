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

AIRCRAFT_SPECS = {
    "F-14": "سرعت 2.34 ماخ | رادار AWG-9 (300km) | AIM-54 Phoenix (200km) | AIM-7 Sparrow (80km) | AIM-9 Sidewinder (18km) | مانور عالی | بال متغیر",
    "F-15": "سرعت 2.5 ماخ | رادار APG-63 (150km) | AIM-7 Sparrow (80km) | AIM-9 Sidewinder (18km) | مانور فوق‌العاده",
    "F-16": "سرعت 2 ماخ | رادار APG-66 (60km) | AIM-9 Sidewinder (18km) | مانور فوق‌العاده (داگ‌فایت)",
    "F-4": "سرعت 2.23 ماخ | رادار APQ-120 (80km) | AIM-7 Sparrow (80km) | AIM-9 Sidewinder (18km) | مانور متوسط | توپ 20mm",
    "MiG-21": "سرعت 2.1 ماخ | رادار RP-21 (19km) | R-3S (8km) | R-60 (8km) | مانور خوب | برد کم",
    "MiG-23": "سرعت 2.35 ماخ | رادار RP-23 (70km) | R-23 (35km) | R-60 (8km) | مانور خوب | بال متغیر",
    "MiG-25": "سرعت 2.83 ماخ | رادار RP-25 (100km) | R-40 (80km) | بدون توپ | مانور ضعیف | ارتفاع بالا",
    "Mirage F1": "سرعت 2.2 ماخ | رادار Cyrano IV (60km) | R.530 (30km) | R.550 Magic (10km) | مانور خوب | توپ 30mm",
    "Su-17": "سرعت 1.6 ماخ | R-60 (8km) | مخصوص حمله زمینی",
    "MiG-27": "سرعت 1.7 ماخ | R-60 (8km) | مخصوص حمله زمینی",
    "Jaguar": "سرعت 1.6 ماخ | AIM-9 | مخصوص حمله زمینی"
}

MILITARY_DB = {
    "ایران": {"نیروی هوایی": "F-14A Tomcat: 77 | F-4 Phantom II: 190 | F-5 Tiger II: 166", "نیروی زمینی": "Chieftain: 894 | M60 Patton: 460 | M47 Patton: 400 | Scorpion: 250", "توپخانه و خمپاره‌انداز": "M101 105mm: 330 | M114 155mm: 100 | M107 175mm: 100 | M110 203mm: 100 | BM-21 Grad: 64 | خمپاره 81/120/240mm", "نیروی دریایی": "ناوشکن Battle: 1 | ناوشکن Sumner: 2 | ناوچه Alvand: 4 | قایق موشک‌انداز Kaman: 10", "پدافند هوایی": "MIM-23 Hawk | توپ ضدهوایی ۱۸۰۰ عراده", "سلاح سبک": "H&K G3"},
    "آمریکا": {"نیروی هوایی": "F-15A/B Eagle: 310 | F-4 Phantom II: 968 | A-10 Thunderbolt II: 144 | F-111 Aardvark: 350 | B-52 Stratofortress: 346 | F-16A/B Fighting Falcon: 156", "نیروی زمینی": "M60A3 Patton: 2560 | M48A5 Patton: 2067 | M551 Sheridan: 59", "توپخانه و خمپاره‌انداز": "M101A1 105mm: 1500 | M102 105mm: 500 | M109A1 155mm: 2000 | M114A2 155mm: 500 | M107 175mm: 750 | M110 203mm: 750 | خمپاره 60/81/107mm", "نیروی دریایی": "ناو هواپیمابر: 13 | رزمناو: 28 | ناوشکن: 97 | زیردریایی SSN: 80 | SSBN: 41", "پدافند هوایی": "MIM-72 Chaparral | M163 Vulcan | FIM-43 Redeye", "سلاح سبک": "M16A1 | M1911A1"},
    "شوروی": {"نیروی هوایی": "MiG-23/27 Flogger: 800 | MiG-25 Foxbat: 25 | Su-17/20/22 Fitter: 500 | Su-24 Fencer: 100 | Tu-95 Bear: 113 | Tu-22M Backfire: 150", "نیروی زمینی": "T-64/T-72/T-80: +20000 | T-62/T-55/T-54: 50000", "توپخانه و خمپاره‌انداز": "D-30 122mm: 4379 | 2S1 Gvozdika: 2751 | 2S3 Akatsiya: 2325 | 2S5 Giatsint-S: 507 | 2S7 Pion: 347 | 2S4 Tyulpan: 430 | BM-21 Grad: 4520 | BM-27 Uragan: 720", "نیروی دریایی": "ناو هواپیمابر Kiev: 2 | Kirov: 1 | Kara: 7 | زیردریایی هسته‌ای: 180 | SSBN: 64", "پدافند هوایی": "SA-2 | SA-3 | SA-5 | SA-10", "سلاح سبک": "AK-74 | AKM"},
    "چین": {"نیروی هوایی": "J-5: 1400 | J-6: 1000 | J-7: 75 | Q-5 Fantan: 300 | H-5: 300 | H-6: 100", "نیروی زمینی": "Type 59: +9000 | Type 69: چند صد | T-34: چند صد", "توپخانه و خمپاره‌انداز": "Type 54 122mm: 10000 | Type 59 130mm: 4000 | Type 66 152mm: 1000 | Type 63 107mm: 4000 | خمپاره 82/120/160mm", "نیروی دریایی": "زیردریایی: 54 | ناوشکن/ناوچه: 16 | قایق گشتی: 763", "پدافند هوایی": "SA-2 | توپ ۱۰۰mm", "سلاح سبک": "Type 56"},
    "عراق": {"نیروی هوایی": "MiG-21: 115 | MiG-23: 80 | Su-20/22: 70 | Tu-22: 12 | Tu-16: 14 | Mirage F1EQ: 12", "نیروی زمینی": "T-54/55/62: 1700 | T-72: 100", "توپخانه و خمپاره‌انداز": "D-30 122mm: 100 | M-30 122mm: 400 | M-46 130mm: 100 | GHN-45 155mm: 200 | G-5 155mm: 100 | GCT 155mm: 76 | 2S1 122mm: 100 | BM-21: چند صد | خمپاره 82/120/160mm", "نیروی دریایی": "OSA-I: 4 | OSA-II: 8 | P-6: 12", "پدافند هوایی": "SA-2 | SA-3 | SA-6", "سلاح سبک": "AK-47 | Tabuk"},
    "اسرائیل": {"نیروی هوایی": "F-15A/B: 24 | F-4E: 90 | A-4 Skyhawk: 270 | Kfir-C2: 80", "نیروی زمینی": "Centurion: 1000 | M60 Patton: 810 | M48 Patton: 650 | Merkava Mk.1: 40", "توپخانه و خمپاره‌انداز": "M109 155mm: 120 | M107 175mm: 60 | M110 203mm: 48 | M101 105mm: 500 | M114 155mm: 450 | خمپاره 81/120/160mm", "نیروی دریایی": "Reshef: 10 | Saar: 12 | Type 206: 3", "پدافند هوایی": "MIM-72 Chaparral | M163 Vulcan | FIM-43 Redeye", "سلاح سبک": "Galil | Uzi | M16A1"},
    "مصر": {"نیروی هوایی": "MiG-21: 208 | MiG-17: 50 | Su-7: 120 | Tu-16: 25 | Mirage 5: 60 | F-4E: 16", "نیروی زمینی": "T-54/55: 850 | T-62: 750 | M60A3: 60", "توپخانه و خمپاره‌انداز": "D-30 122mm: 300 | M-46 130mm: 200 | 2S1 122mm: 100 | 2S3 152mm: 50 | BM-21: 200 | SU-100: 200 | خمپاره 82/120/160mm", "نیروی دریایی": "Skory: 4 | Z: 1 | Romeo: 6 | Whiskey: 6 | OSA-I: 8 | Komar: 5", "پدافند هوایی": "SA-2: 360 | SA-3: 200 | SA-6: 75", "سلاح سبک": "AK-47"},
    "سوریه": {"نیروی هوایی": "MiG-21: 172 | MiG-23: 140 | MiG-25: 25 | Su-20/22: 30", "نیروی زمینی": "T-54/55: 1500 | T-62: 800 | T-72: 65", "توپخانه و خمپاره‌انداز": "2S1 122mm: 100 | 2S3 152mm: 50 | D-30 122mm: 300 | M-46 130mm: 200 | BM-21: 200 | خمپاره 82/120/160/240mm", "نیروی دریایی": "OSA-I/II: 12 | Komar: 2", "پدافند هوایی": "SA-2 | SA-3 | SA-6", "سلاح سبک": "AK-47"},
    "بریتانیا": {"نیروی هوایی": "Phantom FGR.2: 40 | Jaguar GR.1: 52 | Harrier GR.3: 26 | Buccaneer S.2: 24 | Vulcan B.2: 50", "نیروی زمینی": "Chieftain: 640", "توپخانه و خمپاره‌انداز": "Abbot 105mm: 100 | M109 155mm: 50 | M107 175mm: 20 | خمپاره 81mm", "نیروی دریایی": "Hermes: 1 | Type 42: 7 | Type 22: 2 | Leander: 26 | Resolution (SSBN): 4", "پدافند هوایی": "Rapier | Bloodhound", "سلاح سبک": "L1A1 SLR | Sterling"},
    "فرانسه": {"نیروی هوایی": "Mirage F1C: 90 | Mirage IIIE: 30 | Jaguar: 174 | Mirage IV: 34", "نیروی زمینی": "AMX-30: 1360", "توپخانه و خمپاره‌انداز": "AMX-30 AuF1 155mm: 110 | TR 155mm: 20 | خمپاره 120mm: 400", "نیروی دریایی": "Clemenceau: 2 | Colbert: 1 | موشک‌انداز: 6 | Redoutable (SSBN): 4 | زیردریایی تهاجمی: 22", "پدافند هوایی": "Roland | MIM-23 Hawk", "سلاح سبک": "FAMAS | MAS 49/56"},
    "آلمان غربی": {"نیروی هوایی": "F-4F Phantom II: 175 | RF-4E: 88 | F-104G: 144 | Tornado IDS: 10", "نیروی زمینی": "Leopard 1: 2400 | Leopard 2: 100 | M48: 650", "توپخانه و خمپاره‌انداز": "M109G 155mm: 586 | FH-70 155mm: 215 | LARS 110mm: 209 | خمپاره 120mm", "نیروی دریایی": "Type 206: 18 | Lütjens: 3 | Bremen: 6 | قایق موشک‌انداز: 40", "پدافند هوایی": "Roland | Gepard", "سلاح سبک": "H&K G3 | MP5"},
    "آلمان شرقی": {"نیروی هوایی": "MiG-21: 252 | MiG-23: 81 | Su-7: 80 | MiG-17: 30", "نیروی زمینی": "T-54/55: 2500 | T-72: 549 | T-34: 600", "توپخانه و خمپاره‌انداز": "2S1 122mm: 200 | 2S3 152mm: 100 | D-30 122mm: 300 | BM-21: 108 | خمپاره 120mm: 250", "نیروی دریایی": "Koni: 3 | OSA-I: 15 | Shershen: 18 | Libelle: 30 | Kondor: 51", "پدافند هوایی": "SA-4 | SA-6 | SA-7", "سلاح سبک": "AK-47 | AK-74"},
    "ژاپن": {"نیروی هوایی": "F-4EJ: 140 | RF-4E: 14 | F-1: 77 | F-104J", "نیروی زمینی": "Type 74: 740", "توپخانه و خمپاره‌انداز": "Type 75 155mm: 200 | Type 74 105mm: 100 | خمپاره 81/120mm", "نیروی دریایی": "ناوشکن: 60 | زیردریایی: 16", "پدافند هوایی": "MIM-23 Hawk | توپ ۳۵mm", "سلاح سبک": "Howa Type 64"},
    "هند": {"نیروی هوایی": "MiG-21: 300 | Su-7: 120 | Jaguar: 88 | MiG-23BN: 53 | MiG-17: 148", "نیروی زمینی": "T-54/55: 950 | T-72: 70 | Vijayanta: 1100", "توپخانه و خمپاره‌انداز": "D-30 122mm: 500 | M-46 130mm: 300 | FH-77B 155mm: 100 | BM-21: 200 | خمپاره 81/120mm", "نیروی دریایی": "Vikrant: 1 | Foxtrot: 8 | ناوشکن/ناوچه: 23", "پدافند هوایی": "SA-2 | توپ ۴۰mm", "سلاح سبک": "Ishapore 2A1"},
    "پاکستان": {"نیروی هوایی": "Mirage III: 65 | Mirage 5: 52 | J-6: 175 | F-7P: 74", "نیروی زمینی": "Type 59: 1000 | M48", "توپخانه و خمپاره‌انداز": "D-30 122mm: 200 | M-46 130mm: 100 | M101 105mm: 300 | خمپاره 81/120mm", "نیروی دریایی": "ناوشکن: 1 | ناوچه: 8 | زیردریایی: 9", "پدافند هوایی": "SA-2 | توپ ۳۷mm", "سلاح سبک": "G3 | AK-47"},
    "ترکیه": {"نیروی هوایی": "F-4E: 80 | RF-4E: 8 | F-104G: 72 | F-104D: 45 | F-5: 24", "نیروی زمینی": "M48: 3000 | M47", "توپخانه و خمپاره‌انداز": "M101 105mm: 500 | M114 155mm: 300 | M115 203mm: 100 | خمپاره 81/120mm", "نیروی دریایی": "ناوشکن: 13 | زیردریایی: 15", "پدافند هوایی": "Rapier | توپ ۴۰mm", "سلاح سبک": "G3 | M1 Garand"},
    "برزیل": {"نیروی هوایی": "Mirage IIIEBR: 15 | Mirage IIIDBR: 2 | F-5E: 36 | F-5B: 6 | AT-26: 50", "نیروی زمینی": "M41: 250 | M3A1: 220 | X1A2: 25", "توپخانه و خمپاره‌انداز": "M101 105mm: 300 | M114 155mm: 100 | خمپاره 81/120mm", "نیروی دریایی": "Minas Gerais: 1 | Oberon: 3 | GUPPY: 7 | ناوشکن: 2", "پدافند هوایی": "Roland", "سلاح سبک": "FN FAL"},
    "آرژانتین": {"نیروی هوایی": "Mirage IIIEA: 16 | Dagger: 35 | A-4: 16 | Canberra: 8 | Pucara: 30", "نیروی زمینی": "TAM: 350 | AMX-13 | M4 Sherman", "توپخانه و خمپاره‌انداز": "CITER 155mm: 87 | OTO Melara 105mm: 80 | خمپاره 81/120mm", "نیروی دریایی": "Veinticinco de Mayo: 1 | Belgrano: 1 | ناوشکن: 8 | Type 209: 2", "پدافند هوایی": "Roland", "سلاح سبک": "FN FAL | FMK-3"},
    "کره جنوبی": {"نیروی هوایی": "F-4D/E: 128 | F-5A/B: 44 | F-5E/F: 160", "نیروی زمینی": "M47: 350 | M48", "توپخانه و خمپاره‌انداز": "M109 155mm: 200 | M101 105mm: 500 | خمپاره 81/120mm", "نیروی دریایی": "ناوشکن: 60 | زیردریایی: 16", "پدافند هوایی": "MIM-23 Hawk | M163 Vulcan", "سلاح سبک": "M16A1"},
    "کره شمالی": {"نیروی هوایی": "MiG-21: 120 | MiG-19: 130 | MiG-17: 107 | Su-7: 20", "نیروی زمینی": "T-54/55: 2000 | T-62: 300 | T-34: 300", "توپخانه و خمپاره‌انداز": "D-30 122mm: 1000 | M-46 130mm: 500 | BM-21: 500 | خمپاره 82/120/160mm", "نیروی دریایی": "زیردریایی: 20 | OSA: 52", "پدافند هوایی": "SA-2 | توپ ۱۰۰mm", "سلاح سبک": "AK-47 | Type 58"},
    "ویتنام": {"نیروی هوایی": "MiG-21: 120 | MiG-19: 70 | MiG-17: 70 | F-5: 20 | A-37: 19", "نیروی زمینی": "T-54/55: 1600 | Type 59: 160 | PT-76: 450 | M48", "توپخانه و خمپاره‌انداز": "D-30 122mm: 500 | M-46 130mm: 300 | BM-21: 200 | خمپاره 82/120mm", "نیروی دریایی": "OSA: 8 | مین‌روب: 5", "پدافند هوایی": "SA-2: 360 | SA-3", "سلاح سبک": "AK-47 | M16"},
    "کوبا": {"نیروی هوایی": "MiG-23BN: 25 | MiG-21: 78 | MiG-19: 40 | MiG-17: 30", "نیروی زمینی": "T-54/55: 630 | T-62: 50 | T-34: 350", "توپخانه و خمپاره‌انداز": "D-30 122mm: 200 | M-46 130mm: 100 | BM-21: 100 | خمپاره 82/120mm", "نیروی دریایی": "Foxtrot: 2 | OSA-II: 13", "پدافند هوایی": "SA-2 | SA-3 | ZSU-23-4", "سلاح سبک": "AK-47 | FN FAL"},
    "عربستان": {"نیروی هوایی": "F-5E: 70 | F-5F: 20 | F-5B: 20", "نیروی زمینی": "M47 | M41 | AML-60/90", "توپخانه و خمپاره‌انداز": "M101 105mm: 200 | M109 155mm: 100 | خمپاره 81/120mm", "نیروی دریایی": "قایق‌های گشتی ساحلی", "پدافند هوایی": "MIM-23 Hawk | توپ ۳۵mm", "سلاح سبک": "FN FAL | G3"}
}

COUNTRY_DB = {
    "ایران": {"gdp_init": 90400000000, "mil_budget_init": 4000000000, "army_init": 520000, "tanks_init": 1735, "jets_init": 450, "refineries_init": 1175000, "cities": "تهران، اصفهان، مشهد، تبریز، شیراز، اهواز، کرمانشاه، قم، آبادان، رشت، خراسان، فارس، آذربایجان شرقی، آذربایجان غربی، خوزستان، گیلان، مازندران، کرمان، یزد، مرکزی، همدان، لرستان، سیستان و بلوچستان، هرمزگان، بوشهر، زنجان، قزوین، سمنان، ایلام، اردبیل، کردستان", "mines": {"oil_well": {"name": "نفت خوزستان", "output_res": "oil", "amount": 3000000}, "copper_mine": {"name": "مس سرچشمه", "output_res": "copper", "amount": 40000}, "iron_mine": {"name": "آهن بافق", "output_res": "iron", "amount": 60000}}, "factories": {"abadan_refinery": {"name": "پالایشگاه آبادان", "income": 250000, "cost": 500000, "consumes": "oil", "produces": "chemicals"}, "isfahan_steel": {"name": "ذوب آهن اصفهان", "income": 150000, "cost": 350000, "consumes": "iron", "produces": "steel"}}},
    "آمریکا": {"gdp_init": 2627333000000, "mil_budget_init": 548272000000, "army_init": 2013233, "tanks_init": 7835, "jets_init": 3000, "refineries_init": 17050000, "cities": "نیویورک، کالیفرنیا، تگزاس، فلوریدا، آلاسکا، ایلینوی، پنسیلوانیا، اوهایو، میشیگان", "mines": {"oil_well": {"name": "نفت تگزاس", "output_res": "oil", "amount": 9000000}, "iron_mine": {"name": "آهن میشیگان", "output_res": "iron", "amount": 80000}, "coal_mine": {"name": "زغال آپالاش", "output_res": "coal", "amount": 300000}}, "factories": {"texas_refinery": {"name": "پالایشگاه تگزاس", "income": 600000, "cost": 1200000, "consumes": "oil", "produces": "chemicals"}, "us_steel": {"name": "فولاد آمریکا", "income": 400000, "cost": 800000, "consumes": "iron", "produces": "steel"}}},
    "شوروی": {"gdp_init": 1300000000000, "mil_budget_init": 165000000000, "army_init": 3658000, "tanks_init": 50000, "jets_init": 8479, "refineries_init": 10000000, "cities": "مسکو، لنینگراد، کی‌یف، مینسک، تفلیس، باکو، تاشکند، آلماتی، سیبری شرقی", "mines": {"oil_well": {"name": "نفت سیبری", "output_res": "oil", "amount": 11900000}, "iron_mine": {"name": "آهن کورسک", "output_res": "iron", "amount": 250000}, "uranium_mine": {"name": "اورانیوم قزاقستان", "output_res": "uranium", "amount": 50000}}, "factories": {"siberia_refinery": {"name": "پالایشگاه سیبری", "income": 600000, "cost": 1200000, "consumes": "oil", "produces": "chemicals"}, "ural_tank": {"name": "زره اورال", "income": 400000, "cost": 700000, "consumes": "steel", "produces": "tank_armor"}}},
    "چین": {"gdp_init": 263698000000, "mil_budget_init": 40000000000, "army_init": 5120000, "tanks_init": 10000, "jets_init": 5000, "refineries_init": 2000000, "cities": "پکن، شانگهای، تیانجین، چونگ‌کینگ", "mines": {"coal_mine": {"name": "زغال شانشی", "output_res": "coal", "amount": 250000}, "iron_mine": {"name": "آهن آنشان", "output_res": "iron", "amount": 90000}}, "factories": {"cn_steel": {"name": "فولاد آنشان", "income": 180000, "cost": 400000, "consumes": "iron", "produces": "steel"}}},
    "عراق": {"gdp_init": 118000000000, "mil_budget_init": 11350000000, "army_init": 222000, "tanks_init": 1900, "jets_init": 339, "refineries_init": 450000, "cities": "بغداد، بصره، موصل، کرکوک، اربیل", "mines": {"oil_well": {"name": "نفت کرکوک", "output_res": "oil", "amount": 3500000}}, "factories": {"baiji_refinery": {"name": "پالایشگاه بیجی", "income": 200000, "cost": 400000, "consumes": "oil", "produces": "chemicals"}}},
    "اسرائیل": {"gdp_init": 23000000000, "mil_budget_init": 13269000000, "army_init": 172000, "tanks_init": 3050, "jets_init": 576, "refineries_init": 218000, "cities": "اورشلیم، تل‌آویو، حیفا، بئرشبع، نتانیا", "mines": {"copper_mine": {"name": "مس تیمنا", "output_res": "copper", "amount": 10000}}, "factories": {"haifa_refinery": {"name": "پالایشگاه حیفا", "income": 150000, "cost": 300000, "consumes": "oil", "produces": "chemicals"}}},
    "مصر": {"gdp_init": 19000000000, "mil_budget_init": 1165000000, "army_init": 445000, "tanks_init": 1600, "jets_init": 568, "refineries_init": 180000, "cities": "قاهره، اسکندریه، جیزه، پورت سعید، سوئز", "mines": {"oil_well": {"name": "نفت سوئز", "output_res": "oil", "amount": 527000}}, "factories": {"suez_refinery": {"name": "پالایشگاه سوئز", "income": 120000, "cost": 250000, "consumes": "oil", "produces": "chemicals"}}},
    "سوریه": {"gdp_init": 12300000000, "mil_budget_init": 2400000000, "army_init": 230000, "tanks_init": 2600, "jets_init": 262, "refineries_init": 116000, "cities": "دمشق، حلب، حمص، حماة، لاذقیه", "mines": {"oil_well": {"name": "نفت سوریه", "output_res": "oil", "amount": 180000}}, "factories": {"homs_refinery": {"name": "پالایشگاه حمص", "income": 100000, "cost": 200000, "consumes": "oil", "produces": "chemicals"}}},
    "بریتانیا": {"gdp_init": 181000000000, "mil_budget_init": 18000000000, "army_init": 215000, "tanks_init": 640, "jets_init": 1796, "refineries_init": 1000000, "cities": "لندن، بیرمنگام، گلاسکو، لیورپول، ادینبرو", "mines": {"coal_mine": {"name": "زغال یورکشایر", "output_res": "coal", "amount": 122000000}}, "factories": {"vickers_tank": {"name": "ویکرز", "income": 200000, "cost": 450000, "consumes": "steel", "produces": "tank_armor"}}},
    "فرانسه": {"gdp_init": 537000000000, "mil_budget_init": 18000000000, "army_init": 484722, "tanks_init": 1360, "jets_init": 477, "refineries_init": 1500000, "cities": "پاریس، مارسی، لیون، تولوز، لیل", "mines": {"iron_mine": {"name": "آهن لورن", "output_res": "iron", "amount": 30000}}, "factories": {"dassault_jet": {"name": "داسو", "income": 350000, "cost": 700000, "consumes": "titanium", "produces": "jet_engine"}}},
    "آلمان غربی": {"gdp_init": 881000000000, "mil_budget_init": 64008000000, "army_init": 495000, "tanks_init": 5000, "jets_init": 577, "refineries_init": 1500000, "cities": "دوسلدورف، کلن، مونیخ، اشتوتگارت، هانوفر", "mines": {"coal_mine": {"name": "زغال رور", "output_res": "coal", "amount": 200000000}}, "factories": {"ruhr_refinery": {"name": "پالایشگاه رور", "income": 350000, "cost": 700000, "consumes": "oil", "produces": "chemicals"}}},
    "آلمان شرقی": {"gdp_init": 170000000000, "mil_budget_init": 4500000000, "army_init": 173100, "tanks_init": 3140, "jets_init": 335, "refineries_init": 0, "cities": "برلین شرقی، روستوک، شورین، ماگدبورگ، لایپزیگ", "mines": {"coal_mine": {"name": "لیگنیت", "output_res": "coal", "amount": 250000000}}, "factories": {"eg_chem": {"name": "شیمیایی", "income": 150000, "cost": 300000, "consumes": "coal", "produces": "chemicals"}}},
    "ژاپن": {"gdp_init": 1055012000000, "mil_budget_init": 21225000000, "army_init": 250000, "tanks_init": 740, "jets_init": 227, "refineries_init": 5000000, "cities": "توکیو، اوساکا، کاناگاوا، آیچی، هوکایدو", "mines": {"coal_mine": {"name": "زغال هوکایدو", "output_res": "coal", "amount": 20000}}, "factories": {"jp_electronics": {"name": "الکترونیک", "income": 400000, "cost": 700000, "consumes": "copper", "produces": "electronics"}}},
    "هند": {"gdp_init": 152062000000, "mil_budget_init": 11190000000, "army_init": 1000000, "tanks_init": 2790, "jets_init": 625, "refineries_init": 500000, "cities": "دهلی نو، بمبئی، کلکته، چنای، بنگلور", "mines": {"iron_mine": {"name": "آهن", "output_res": "iron", "amount": 60000}}, "factories": {"in_steel": {"name": "فولاد", "income": 150000, "cost": 350000, "consumes": "iron", "produces": "steel"}}},
    "پاکستان": {"gdp_init": 25798000000, "mil_budget_init": 1979000000, "army_init": 400000, "tanks_init": 1000, "jets_init": 247, "refineries_init": 100000, "cities": "اسلام‌آباد، کراچی، لاهور، پیشاور", "mines": {"iron_mine": {"name": "آهن", "output_res": "iron", "amount": 20000}}, "factories": {"pk_ammo": {"name": "مهمات", "income": 100000, "cost": 250000, "consumes": "iron", "produces": "ammo"}}},
    "ترکیه": {"gdp_init": 126394000000, "mil_budget_init": 4733000000, "army_init": 500000, "tanks_init": 3000, "jets_init": 300, "refineries_init": 400000, "cities": "آنکارا، استانبول، ازمیر، بورسا", "mines": {"chromium_mine": {"name": "کروم", "output_res": "chromium", "amount": 40000}}, "factories": {"tr_steel": {"name": "فولاد", "income": 120000, "cost": 250000, "consumes": "coal", "produces": "steel"}}},
    "برزیل": {"gdp_init": 186976000000, "mil_budget_init": 6811000000, "army_init": 257000, "tanks_init": 350, "jets_init": 205, "refineries_init": 1000000, "cities": "برازیلیا، سائوپائولو، ریودوژانیرو", "mines": {"iron_mine": {"name": "آهن", "output_res": "iron", "amount": 80000}}, "factories": {"br_steel": {"name": "فولاد", "income": 150000, "cost": 300000, "consumes": "iron", "produces": "steel"}}},
    "آرژانتین": {"gdp_init": 73916000000, "mil_budget_init": 14098000000, "army_init": 133500, "tanks_init": 350, "jets_init": 132, "refineries_init": 600000, "cities": "بوئنوس آیرس، کوردوبا، سانتافه", "mines": {"copper_mine": {"name": "مس", "output_res": "copper", "amount": 20000}}, "factories": {"ar_steel": {"name": "فولاد", "income": 100000, "cost": 250000, "consumes": "copper", "produces": "steel"}}},
    "کره جنوبی": {"gdp_init": 66947000000, "mil_budget_init": 8819000000, "army_init": 600000, "tanks_init": 350, "jets_init": 520, "refineries_init": 600000, "cities": "سئول، بوسان، اینچئون، دئگو", "mines": {"tungsten_mine": {"name": "تنگستن", "output_res": "tungsten", "amount": 15000}}, "factories": {"kr_steel": {"name": "فولاد", "income": 150000, "cost": 300000, "consumes": "tungsten", "produces": "steel"}}},
    "کره شمالی": {"gdp_init": 9490000000, "mil_budget_init": 2000000000, "army_init": 600000, "tanks_init": 2300, "jets_init": 565, "refineries_init": 50000, "cities": "پیونگ‌یانگ، هامهونگ", "mines": {"coal_mine": {"name": "زغال سنگ", "output_res": "coal", "amount": 50000}}, "factories": {"nk_ammo": {"name": "مهمات", "income": 100000, "cost": 200000, "consumes": "coal", "produces": "ammo"}}},
    "ویتنام": {"gdp_init": 7140000000, "mil_budget_init": 1000000000, "army_init": 615000, "tanks_init": 2000, "jets_init": 300, "refineries_init": 0, "cities": "هانوی، هوشی‌مین، هایفونگ", "mines": {"coal_mine": {"name": "زغال سنگ", "output_res": "coal", "amount": 30000}}, "factories": {"vn_ammo": {"name": "مهمات", "income": 80000, "cost": 200000, "consumes": "coal", "produces": "ammo"}}},
    "کوبا": {"gdp_init": 19584000000, "mil_budget_init": 1500000000, "army_init": 150000, "tanks_init": 800, "jets_init": 168, "refineries_init": 100000, "cities": "هاوانا، سانتیاگو د کوبا", "mines": {"cobalt_mine": {"name": "کوبالت", "output_res": "cobalt", "amount": 15000}}, "factories": {"cu_refinery": {"name": "پالایشگاه", "income": 80000, "cost": 200000, "consumes": "oil", "produces": "chemicals"}}},
    "عربستان": {"gdp_init": 94600000000, "mil_budget_init": 10500000000, "army_init": 51700, "tanks_init": 550, "jets_init": 90, "refineries_init": 834900, "cities": "ریاض، جده، مکه، مدینه، دمام", "mines": {"oil_well": {"name": "غوار", "output_res": "oil", "amount": 10000000}}, "factories": {"ras_tanura": {"name": "راس تنوره", "income": 300000, "cost": 600000, "consumes": "oil", "produces": "chemicals"}}}
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
                user_id BIGINT PRIMARY KEY, username TEXT, name TEXT, status TEXT DEFAULT 'pending', 
                gdp BIGINT DEFAULT 500000000, mil_budget BIGINT DEFAULT 35000000, 
                jets INT DEFAULT 0, tanks INT DEFAULT 0, refineries INT DEFAULT 0, army INT DEFAULT 100000, 
                satisfaction INT DEFAULT 50, tax_rate INT DEFAULT 10, created_at TIMESTAMP DEFAULT NOW()
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
        ]
        for table, col, col_type in columns_to_add:
            try:
                await conn.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {col_type}")
            except:
                pass
    logger.info("Database initialized (Full v3).")

async def get_enemy_deployments_str(player_country):
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM deployments WHERE country_name != $1 AND quantity > 0", player_country)
    if not rows:
        return "هیچ نیروی دشمنی در هیچ منطقه‌ای مستقر نیست."
    return "\n".join([f"- {r['country_name']}: {r['quantity']} {r['model']} در {r['region']}" for r in rows])

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
    if isinstance(raw, dict): return raw
    if not raw or not isinstance(raw, str): return {}
    start, end = raw.find('{'), raw.rfind('}')
    if start == -1 or end == -1: return {}
    s = raw[start:end + 1].replace("```json", "").replace("```", "").strip()
    try: return json.loads(s)
    except: pass
    try: return ast.literal_eval(s)
    except: pass
    try: return ast.literal_eval(s.replace("true", "True").replace("false", "False").replace("null", "None"))
    except: pass
    return {}

def _clean_persian_text(text: str) -> str:
    if not isinstance(text, str): return ""
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

def _build_prompt(country: dict, order_text: str, category: str, enemy_deployments: str) -> str:
    if category == "political": 
        narrative_rule = "The narrative MUST be a highly dramatic political speech."
    elif category == "diplomacy":
        narrative_rule = "The narrative MUST be a formal diplomatic agreement or treaty declaration."
    elif category == "military": 
        narrative_rule = "The narrative MUST be an epic war report."
    else: 
        narrative_rule = "The narrative MUST be a dramatic economic news report."

    return f"""You are the strict Game Master of a grand strategy game set in 1979.

COUNTRY: {country['name']} | GDP: ${country['gdp']:,} | Mil Budget: ${country['mil_budget']:,}
Army: {country['army']} | Tanks: {country['tanks']} | Jets: {country['jets']}

ENEMY DEPLOYMENTS GLOBALLY:
{enemy_deployments}

PLAYER ORDER: "{order_text}"
CATEGORY: {category}

CRITICAL:
- Extract the "target_country" from the text if this is a diplomatic order (e.g., alliance, trade, truce). Must be EXACTLY one of the allowed countries: {', '.join(ALLOWED_COUNTRIES)}. If not diplomatic, set to "None".
- Determine "order_intent": "attack", "patrol", "deploy", "economic", "political", "diplomacy".
- Determine "action_type": "deploy", "attack", "economic", "political", "diplomacy".
- If CATEGORY is "diplomacy", calculate the economic/military benefits of this agreement.

NARRATIVE STYLE: {narrative_rule}
Use ONLY Persian alphabet.

EXACT JSON FORMAT:
{{
  "success": true/false,
  "reason": "Persian reason",
  "order_intent": "attack/patrol/deploy/economic/political/diplomacy",
  "action_type": "deploy/attack/economic/political/diplomacy",
  "target_country": "USA or None",
  "region": "Alaska or None",
  "deployed_asset": "F-15 or None",
  "deployed_quantity": 10,
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
    
    action = data.get("action_type")
    region = data.get("region")
    
    if action == "deploy" and region != "None":
        asset = data.get("deployed_asset")
        qty = int(data.get("deployed_quantity", 0))
        if asset != "None" and qty > 0:
            async with pool.acquire() as conn:
                await conn.execute(
                    "INSERT INTO deployments (user_id, country_name, region, asset_type, model, quantity) VALUES ($1, $2, $3, $4, $5, $6)",
                    user_id, country_name, region, "aircraft/tank", asset, qty
                )

async def create_encounter_ask_intent(context, order_id, user_id, country_name, asset, enemy, region):
    async with pool.acquire() as conn:
        enc_id = await conn.fetchval(
            """INSERT INTO encounters 
            (order_id, detector_id, detector_country, detector_asset, detected_id, detected_country, detected_asset, region, status) 
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'awaiting_intent') RETURNING id""",
            order_id, user_id, country_name, asset, enemy['user_id'], enemy['country_name'], "نیروی نامشخص", region
        )
        
        enemy_asset_row = await conn.fetchrow(
            "SELECT model FROM deployments WHERE country_name = $1 AND region = $2 AND quantity > 0 ORDER BY quantity DESC LIMIT 1",
            enemy['country_name'], region
        )
        if enemy_asset_row:
            await conn.execute("UPDATE encounters SET detected_asset = $1 WHERE id = $2", enemy_asset_row['model'], enc_id)
    
    intent_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🕊️ فقط گشت‌زنی", callback_data=f"intent_patrol_{enc_id}")],
        [InlineKeyboardButton("⚔️ قصد حمله داریم", callback_data=f"intent_attack_{enc_id}")],
        [InlineKeyboardButton("🏃 عقب‌نشینی", callback_data=f"intent_retreat_{enc_id}")]
    ])
    
    for target_id, target_country, our_asset in [
        (user_id, country_name, asset),
        (enemy['user_id'], enemy['country_name'], enemy_asset_row['model'] if enemy_asset_row else 'نیروی نامشخص')
    ]:
        try:
            await context.bot.send_message(
                target_id,
                f"🚨 **درگیری هوایی در {region}**\n\n"
                f"کشور شما (`{our_asset}`) در این منطقه با نیروهای دشمن روبرو شده.\n"
                f"**نیت شما چیست؟**",
                reply_markup=intent_kb
            )
        except:
            pass
    
    return enc_id

async def create_encounter_and_battle(context, order_id, user_id, country_name, asset, enemy, region):
    async with pool.acquire() as conn:
        enc_id = await conn.fetchval(
            """INSERT INTO encounters 
            (order_id, detector_id, detector_country, detector_asset, detected_id, detected_country, detected_asset, region, detector_intent, detected_intent, status) 
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'attack', 'attack', 'battle') RETURNING id""",
            order_id, user_id, country_name, asset, enemy['user_id'], enemy['country_name'], "نیروی نامشخص", region
        )
        enemy_asset_row = await conn.fetchrow(
            "SELECT model FROM deployments WHERE country_name = $1 AND region = $2 AND quantity > 0 ORDER BY quantity DESC LIMIT 1",
            enemy['country_name'], region
        )
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
        
        if det_intent == 'retreat' or ed_intent == 'retreat':
            if det_intent == 'retreat' and ed_intent == 'retreat':
                await conn.execute("UPDATE encounters SET status = 'avoided' WHERE id = $1", enc_id)
                for uid in [enc['detector_id'], enc['detected_id']]:
                    try:
                        await context.bot.send_message(uid, "🕊️ هر دو طرف عقب‌نشینی کردند. نبردی رخ نداد.")
                    except: 
                        pass
            elif det_intent == 'retreat':
                if ed_intent == 'attack':
                    await conn.execute("UPDATE encounters SET status = 'battle' WHERE id = $1", enc_id)
                    await simulate_encounter_battle(context, enc_id, dict(enc))
                else:
                    await conn.execute("UPDATE encounters SET status = 'avoided' WHERE id = $1", enc_id)
            else:
                if det_intent == 'attack':
                    await conn.execute("UPDATE encounters SET status = 'battle' WHERE id = $1", enc_id)
                    await simulate_encounter_battle(context, enc_id, dict(enc))
                else:
                    await conn.execute("UPDATE encounters SET status = 'avoided' WHERE id = $1", enc_id)
        elif det_intent == 'attack' and ed_intent == 'attack':
            await conn.execute("UPDATE encounters SET status = 'battle' WHERE id = $1", enc_id)
            await simulate_encounter_battle(context, enc_id, dict(enc))
        else:
            await conn.execute("UPDATE encounters SET status = 'patrol_only' WHERE id = $1", enc_id)
            for uid in [enc['detector_id'], enc['detected_id']]:
                try:
                    await context.bot.send_message(uid, "🕊️ هر دو طرف فقط در حال گشت‌زنی بودند. نبردی رخ نداد.")
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
    
    prompt = f"""Simulate a 1979 air battle.

DETECTOR: {enc['detector_country']} | Asset: {enc['detector_asset']} | Spec: {det_spec} | Intent: {det_intent}
DETECTED: {enc['detected_country']} | Asset: {enc['detected_asset']} | Spec: {ed_spec} | Intent: {ed_intent}

If both attacked: full air battle with losses on both sides.
If one retreating while other attacks: retreating side has heavy losses (surprise attack).
Use realistic 1979 combat rules (BVR radar/missile range first, then dogfight maneuverability).

Output JSON only:
{{
  "detector_losses": integer,
  "detected_losses": integer,
  "narrative": "Persian cinematic battle report (2 sentences max)"
}}"""
    
    ai_response = await ask_ai(prompt, system_prompt="You are a battle simulation API. Output JSON with Persian narrative.")
    data = _safe_parse_json(ai_response)
    
    det_losses = max(0, int(data.get('detector_losses', 0)))
    ed_losses = max(0, int(data.get('detected_losses', 0)))
    narrative = _clean_persian_text(data.get('narrative', 'نبردی شدید رخ داد.'))
    
    async with pool.acquire() as conn:
        await conn.execute("UPDATE countries SET jets = GREATEST(0, jets - $1) WHERE user_id = $2", det_losses, enc['detector_id'])
        await conn.execute("UPDATE countries SET jets = GREATEST(0, jets - $1) WHERE user_id = $2", ed_losses, enc['detected_id'])
        await conn.execute("UPDATE deployments SET quantity = GREATEST(0, quantity - $1) WHERE country_name = $2 AND region = $3", det_losses, enc['detector_country'], enc['region'])
        await conn.execute("UPDATE deployments SET quantity = GREATEST(0, quantity - $1) WHERE country_name = $2 AND region = $3", ed_losses, enc['detected_country'], enc['region'])
        await conn.execute("DELETE FROM deployments WHERE quantity <= 0")
        await conn.execute("UPDATE encounters SET battle_narrative = $1 WHERE id = $2", narrative, enc_id)
        await conn.execute("UPDATE orders SET final_narrative = $1 WHERE id = $2", narrative, enc['order_id'])
    
    battle_msg = (
        f"⚔️ **نتیجه نبرد در {enc['region']}**\n\n"
        f"🏴 **{enc['detector_country']}**: {det_losses} فروند تلفات\n"
        f"🏳️ **{enc['detected_country']}**: {ed_losses} فروند تلفات\n\n"
        f"📖 {narrative}"
    )
    
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
    
    enemy_deployments_str = await get_enemy_deployments_str(country['name'])
    prompt = _build_prompt(dict(country), order["order_text"], order["category"], enemy_deployments_str)
    
    # 👇 سیستم پرامپت اصلاح شد تا کلیدهای JSON رو به فارسی ترجمه نکنه
    sys_prompt = "You are a strict JSON API. Output RAW JSON only. DO NOT wrap in markdown. DO NOT translate the JSON keys. Keep keys in English exactly as requested. Use Persian ONLY for the values of reason, narrative_short, and narrative_long."
    ai_response = await ask_ai(prompt, system_prompt=sys_prompt)
    
    # 👇 این خط رو اضافه کردم که دقیقا ببینیم AI چی فرستاده (توی لاگ رندر)
    logger.info(f"AI RAW for order {order_id}:\n{ai_response}")
    
    data = _safe_parse_json(ai_response)

    if "success" not in data or "narrative_long" not in data:
        data = {"success": False, "reason": "پاسخ نامعتبر بود", "narrative_short": "خطا", "narrative_long": "نیاز به بررسی دستی.", "gdp_change": 0, "mil_budget_change": 0, "jets_change": 0, "tanks_change": 0, "refineries_change": 0, "satisfaction_change": 0, "battle_occurred": False, "order_intent": "unknown", "region": "None", "target_country": "None"}

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
            target_data = await conn.fetchrow("SELECT user_id, name FROM countries WHERE name = $1 AND status = 'active'", target_country)
        
        if not target_data:
            data["success"] = False
            data["reason"] = f"کشور {target_country} در بازی وجود ندارد یا فعال نیست."
        else:
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE orders SET status = 'diplo_pending', target_country = $1, ai_analysis_raw = $2 WHERE id = $3",
                    target_country, json.dumps(data, ensure_ascii=False), order_id
                )
            
            kb_diplo = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ قبول توافق", callback_data=f"diplo_accept_{order_id}")],
                [InlineKeyboardButton("❌ رد توافق", callback_data=f"diplo_reject_{order_id}")]
            ])
            
            try:
                await context.bot.send_message(
                    target_data['user_id'],
                    f"🤝 **درخواست دیپلماتیک از {country['name']}**\n\n"
                    f"📜 متن پیشنهاد: {order['order_text']}\n\n"
                    f"آیا این توافق را می‌پذیرید؟",
                    reply_markup=kb_diplo
                )
            except Exception as e:
                logger.error(f"Failed to send diplo request: {e}")
                data["success"] = False
                data["reason"] = "ارسال درخواست به کشور هدف با خطا مواجه شد."
            
            return data

    if data.get("success"):
        try:
            g_change = int(data.get("gdp_change") or 0)
            m_change = int(data.get("mil_budget_change") or 0)
            j_change = int(data.get("jets_change") or 0)
            t_change = int(data.get("tanks_change") or 0)
            r_change = int(data.get("refineries_change") or 0)
            s_change = int(data.get("satisfaction_change") or 0)
        except:
            data = {"success": False, "reason": "خطای عددی", "narrative_short": "", "narrative_long": "", "gdp_change": 0, "mil_budget_change": 0, "jets_change": 0, "tanks_change": 0, "refineries_change": 0, "satisfaction_change": 0, "battle_occurred": False, "order_intent": order_intent, "region": region}
        else:
            if country["gdp"] + g_change < 0 or country["mil_budget"] + m_change < 0:
                data = {"success": False, "reason": "ورشکستگی! بودجه کافی نیست.", "gdp_change": 0, "mil_budget_change": 0, "jets_change": 0, "tanks_change": 0, "refineries_change": 0, "satisfaction_change": -5, "narrative_short": "اقتصاد فروپاشید.", "narrative_long": "با خالی شدن خزانه ملی، طرح پیشنهادی با شکست مواجه شد.", "battle_occurred": False, "order_intent": order_intent, "region": region}
            else:
                new_sat = max(0, min(100, country.get("satisfaction", 50) + s_change))
                data["satisfaction_change"] = new_sat - country.get("satisfaction", 50)
                async with pool.acquire() as conn:
                    await conn.execute(
                        "UPDATE countries SET gdp = GREATEST(0, gdp + $1), mil_budget = GREATEST(0, mil_budget + $2), jets = GREATEST(0, jets + $3), tanks = GREATEST(0, tanks + $4), refineries = GREATEST(0, refineries + $5), satisfaction = $6 WHERE user_id = $7", 
                        g_change, m_change, j_change, t_change, r_change, new_sat, order["user_id"]
                    )
                await apply_battle_changes(context, order["user_id"], country['name'], data)
    
    enemy = None
    if action_type in ["deploy", "attack"] and region and region != "None":
        async with pool.acquire() as conn:
            enemy_row = await conn.fetchrow(
                "SELECT user_id, country_name FROM deployments WHERE region = $1 AND country_name != $2 AND quantity > 0 LIMIT 1",
                region, country['name']
            )
            if enemy_row:
                enemy = dict(enemy_row)
    
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE orders SET order_intent = $1, region = $2, ai_analysis_raw = $3, enemy_user_id = $4 WHERE id = $5",
            order_intent, region, json.dumps(data, ensure_ascii=False), 
            enemy['user_id'] if enemy else None, order_id
        )
    
    if enemy and action_type in ["deploy", "attack"]:
        if order_intent == "attack":
            enc_id = await create_encounter_and_battle(context, order_id, order["user_id"], country['name'], deployed_asset, enemy, region)
            data["encounter_id"] = enc_id
            data["battle_triggered"] = "immediate"
        elif order_intent in ["patrol", "deploy"]:
            enc_id = await create_encounter_ask_intent(context, order_id, order["user_id"], country['name'], deployed_asset, enemy, region)
            data["encounter_id"] = enc_id
            data["battle_triggered"] = "awaiting_intent"
    
    return data
    
    if data.get("success"):
        try:
            g_change = int(data.get("gdp_change") or 0)
            m_change = int(data.get("mil_budget_change") or 0)
            j_change = int(data.get("jets_change") or 0)
            t_change = int(data.get("tanks_change") or 0)
            r_change = int(data.get("refineries_change") or 0)
            s_change = int(data.get("satisfaction_change") or 0)
        except:
            data = {"success": False, "reason": "خطای عددی", "narrative_short": "", "narrative_long": "", "gdp_change": 0, "mil_budget_change": 0, "jets_change": 0, "tanks_change": 0, "refineries_change": 0, "satisfaction_change": 0, "battle_occurred": False, "order_intent": order_intent, "region": region}
        else:
            if country["gdp"] + g_change < 0 or country["mil_budget"] + m_change < 0:
                data = {"success": False, "reason": "ورشکستگی! بودجه کافی نیست.", "gdp_change": 0, "mil_budget_change": 0, "jets_change": 0, "tanks_change": 0, "refineries_change": 0, "satisfaction_change": -5, "narrative_short": "اقتصاد فروپاشید.", "narrative_long": "با خالی شدن خزانه ملی، طرح پیشنهادی با شکست مواجه شد.", "battle_occurred": False, "order_intent": order_intent, "region": region}
            else:
                new_sat = max(0, min(100, country.get("satisfaction", 50) + s_change))
                data["satisfaction_change"] = new_sat - country.get("satisfaction", 50)
                async with pool.acquire() as conn:
                    await conn.execute(
                        "UPDATE countries SET gdp = GREATEST(0, gdp + $1), mil_budget = GREATEST(0, mil_budget + $2), jets = GREATEST(0, jets + $3), tanks = GREATEST(0, tanks + $4), refineries = GREATEST(0, refineries + $5), satisfaction = $6 WHERE user_id = $7", 
                        g_change, m_change, j_change, t_change, r_change, new_sat, order["user_id"]
                    )
                await apply_battle_changes(context, order["user_id"], country['name'], data)
    
    enemy = None
    if action_type in ["deploy", "attack"] and region and region != "None":
        async with pool.acquire() as conn:
            enemy_row = await conn.fetchrow(
                "SELECT user_id, country_name FROM deployments WHERE region = $1 AND country_name != $2 AND quantity > 0 LIMIT 1",
                region, country['name']
            )
            if enemy_row:
                enemy = dict(enemy_row)
    
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE orders SET order_intent = $1, region = $2, ai_analysis_raw = $3, enemy_user_id = $4 WHERE id = $5",
            order_intent, region, json.dumps(data, ensure_ascii=False), 
            enemy['user_id'] if enemy else None, order_id
        )
    
    if enemy and action_type in ["deploy", "attack"]:
        if order_intent == "attack":
            enc_id = await create_encounter_and_battle(context, order_id, order["user_id"], country['name'], deployed_asset, enemy, region)
            data["encounter_id"] = enc_id
            data["battle_triggered"] = "immediate"
        elif order_intent in ["patrol", "deploy"]:
            enc_id = await create_encounter_ask_intent(context, order_id, order["user_id"], country['name'], deployed_asset, enemy, region)
            data["encounter_id"] = enc_id
            data["battle_triggered"] = "awaiting_intent"
    
    return data

async def analyze_and_apply_order(order_id: int, context):
    try:
        return await asyncio.wait_for(_analyze_inner(order_id, context), timeout=120.0)
    except asyncio.TimeoutError:
        logger.error(f"AI Timeout for order {order_id}")
        data = {"success": False, "reason": "پردازش طول کشید", "narrative_short": "به تعویق افتاد.", "narrative_long": "پردازش هوش مصنوعی طول کشید و به تعویق افتاد.", "gdp_change": 0, "mil_budget_change": 0, "jets_change": 0, "tanks_change": 0, "refineries_change": 0, "satisfaction_change": 0, "battle_occurred": False, "order_intent": "unknown", "region": "None", "target_country": "None"}
        async with pool.acquire() as conn:
            await conn.execute("UPDATE orders SET status='ai_analyzed', ai_analysis_raw=$1 WHERE id=$2", json.dumps(data, ensure_ascii=False), order_id)
        return data
    except Exception as e:
        logger.error(f"AI Analysis error for order {order_id}: {type(e).__name__}: {e}")
        data = {"success": False, "reason": f"خطا: {str(e)[:100]}", "narrative_short": "خطا در تحلیل", "narrative_long": "هوش مصنوعی نتوانست تحلیل را انجام دهد.", "gdp_change": 0, "mil_budget_change": 0, "jets_change": 0, "tanks_change": 0, "refineries_change": 0, "satisfaction_change": 0, "battle_occurred": False, "order_intent": "unknown", "region": "None", "target_country": "None"}
        async with pool.acquire() as conn:
            await conn.execute("UPDATE orders SET status='ai_analyzed', ai_analysis_raw=$1 WHERE id=$2", json.dumps(data, ensure_ascii=False), order_id)
        return data

async def set_commands(app):
    await app.bot.set_my_commands([
        BotCommand("start", "ثبت‌نام"), 
        BotCommand("country", "اطلاعات کشور"), 
        BotCommand("military", "آرشیو نظامی"), 
        BotCommand("economy", "انبار منابع"), 
        BotCommand("factory", "مدیریت کارخانه‌ها"), 
        BotCommand("mines", "معادن"), 
        BotCommand("order", "ثبت دستور جدید"), 
        BotCommand("admin", "پنل ادمین"), 
        BotCommand("turn", "پردازش نوبت (ادمین)")
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    async with pool.acquire() as conn:
        c = await conn.fetchrow("SELECT * FROM countries WHERE user_id = $1", uid)
    if c:
        if c["status"] == "active": 
            await context.bot.send_message(uid, f"✅ کشور {c['name']} فعال است.")
        elif c["status"] == "pending": 
            await context.bot.send_message(uid, "⏳ در انتظار تایید ادمین.")
        return
        
    temp[uid] = {"step": "SELECT_COUNTRY"}
    await context.bot.send_message(uid, f"🏛️ **Welcome to rustabad RP (1979)**\n\nلطفاً نام کشور خود را انتخاب کنید:\n\n{'، '.join(ALLOWED_COUNTRIES)}", parse_mode="Markdown")

async def country_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with pool.acquire() as conn:
        c = await conn.fetchrow("SELECT * FROM countries WHERE user_id = $1", update.effective_user.id)
    if not c or c["status"] != "active": 
        return await update.message.reply_text("⚠️ شما مجاز نیستید یا در انتظار تایید هستید. /start")
        
    data = COUNTRY_DB.get(c['name'])
    text = (
        f"🏛️ *کشور: {c['name']}* (۱۹۷۹)\n"
        f"🏙️ *شهرها:* {data['cities'] if data else 'نامشخص'}\n\n"
        f"📈 GDP: {fmt_money(c['gdp'])}\n"
        f"🛡 بودجه نظامی: {fmt_money(c['mil_budget'])}\n"
        f"✈️ جنگنده‌ها: {c['jets']:,} فروند\n"
        f"🚜 تانک‌ها: {c.get('tanks', 0):,} عراده\n"
        f"🏭 ظرفیت پالایش: {c['refineries']:,} بشکه در روز\n"
        f"🎖 ارتش: {c['army']:,} نفر\n"
        f"❤️ رضایت: {c.get('satisfaction', 50)}%\n\n"
        f"برای مشاهده آرشیو نظامی از /military استفاده کنید."
    )
    await context.bot.send_message(update.effective_user.id, text, parse_mode="Markdown")

async def military_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with pool.acquire() as conn:
        c = await conn.fetchrow("SELECT * FROM countries WHERE user_id = $1", update.effective_user.id)
        deployments = await conn.fetch("SELECT * FROM deployments WHERE country_name = $1 AND quantity > 0", c['name'])
        
    if not c or c["status"] != "active": 
        return await update.message.reply_text("⚠️ شما مجاز نیستید یا در انتظار تایید هستید. /start")
    
    mil_data = MILITARY_DB.get(c['name'])
    if not mil_data: 
        return await update.message.reply_text("⚠️ آرشیو نظامی در دسترس نیست.")
    
    deploy_str = "هیچ نیرویی مستقر نیست."
    if deployments:
        deploy_str = "\n".join([f"📍 {d['region']}: {d['quantity']} {d['model']}" for d in deployments])
        
    text = (
        f"⚔️ *آرشیو نظامی {c['name']}* (۱۹۷۹)\n\n"
        f"🚜 **تانک‌ها:** {mil_data['نیروی زمینی']}\n\n"
        f"✈️ **هواپیماها:** {mil_data['نیروی هوایی']}\n\n"
        f"💥 **توپخانه:** {mil_data['توپخانه و خمپاره‌انداز']}\n\n"
        f"⚓ **نیروی دریایی:** {mil_data['نیروی دریایی']}\n\n"
        f"🛡 **پدافند هوایی:** {mil_data['پدافند هوایی']}\n\n"
        f"🔫 **سلاح‌های سبک:** {mil_data['سلاح سبک']}\n\n"
        f"📍 **نیروهای مستقر شده:**\n{deploy_str}\n\n"
        f"👥 **پرسنل:** {c['army']:,} نفر\n"
        f"🛡 **بودجه نظامی:** {fmt_money(c['mil_budget'])}"
    )
    await context.bot.send_message(update.effective_user.id, text, parse_mode="Markdown")

async def economy_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with pool.acquire() as conn: 
        c = await conn.fetchrow("SELECT * FROM countries WHERE user_id = $1", update.effective_user.id)
    if not c or c["status"] != "active": 
        return await update.message.reply_text("⚠️ شما مجاز نیستید. /start")
        
    res_text = "".join([f"{v}: {c.get(f'res_{k}', 0):,}\n" for k, v in RESOURCES.items() if c.get(f'res_{k}', 0) > 0]) or "انبار خالی است.\n"
    await context.bot.send_message(update.effective_user.id, f"💰 *اقتصاد {c['name']}*\n🏦 GDP: {fmt_money(c['gdp'])}\n\n📦 *انبار:*\n{res_text}", parse_mode="Markdown")

async def mines_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with pool.acquire() as conn: 
        c = await conn.fetchrow("SELECT * FROM countries WHERE user_id = $1", update.effective_user.id)
    if not c or c["status"] != "active": 
        return await update.message.reply_text("⚠️ شما مجاز نیستید. /start")
        
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
    if not c or c["status"] != "active": 
        return await update.message.reply_text("⚠️ شما مجاز نیستید. /start")
        
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
        return await update.message.reply_text("⚠️ شما مجاز نیستید. /start")
        
    temp[uid] = {"step": "ORDER_CATEGORY"}
    
    kb_cats = InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 اقتصادی", callback_data="cat_economic"), InlineKeyboardButton("🏛️ سیاسی", callback_data="cat_political")],
        [InlineKeyboardButton("🤝 دیپلماسی", callback_data="cat_diplomacy"), InlineKeyboardButton("⚔️ نظامی", callback_data="cat_military")]
    ])
    await update.message.reply_text("دسته‌بندی دستور خود را انتخاب کنید:", reply_markup=kb_cats)

async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: 
        return
    await update.message.reply_text("👑 **پنل ادمین**", reply_markup=kb([[InlineKeyboardButton("📋 لیست کشورها", callback_data="adm_list")], [InlineKeyboardButton("⏳ پردازش نوبت", callback_data="adm_next_turn")], [InlineKeyboardButton("💰 تنظیم GDP", callback_data="adm_set_gdp")]]), parse_mode="Markdown")

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
            await conn.execute("INSERT INTO countries (user_id, username, name, status, gdp, mil_budget, jets, tanks, refineries, army) VALUES ($1, $2, $3, 'pending', $4, $5, $6, $7, $8, $9)", uid, update.effective_user.username or "بدون", text, data['gdp_init'], data['mil_budget_init'], data['jets_init'], data['tanks_init'], data['refineries_init'], data['army_init'])
        temp.pop(uid, None)
        await context.bot.send_message(uid, "⏳ در انتظار تایید ادمین.")
        await context.bot.send_message(ADMIN_ID, f"📥 **درخواست جدید**\n🌍 {text}\n🆔 `{uid}`", parse_mode="Markdown", reply_markup=kb([[InlineKeyboardButton("✅ تایید", callback_data=f"adm_ok_{uid}"), InlineKeyboardButton("❌ رد", callback_data=f"adm_rej_{uid}")]]))
        
    elif t.get("step") == "AWAITING_ORDER_TEXT":
        category = t.get("category")
        temp[uid] = {"step": "SELECT_VISIBILITY", "category": category, "order_text": text}
        
        kb_vis = InlineKeyboardMarkup([
            [InlineKeyboardButton("🌍 عمومی (در گروه منتشر شود)", callback_data="vis_public")],
            [InlineKeyboardButton("🤫 محرمانه (فقط ادمین و طرفین)", callback_data="vis_secret")]
        ])
        await update.message.reply_text("آیا نتیجه این دستور باید در گروه منتشر شود؟", reply_markup=kb_vis)
        
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
        await context.bot.send_message(target, "🎉 کشور شما تایید شد! /country")
        
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
        category = data.replace("cat_", "")
        temp[uid] = {"step": "AWAITING_ORDER_TEXT", "category": category}
        
        cat_fa = {"economic": "اقتصادی", "political": "سیاسی", "diplomacy": "دیپلماسی", "military": "نظامی"}.get(category, category)
        await cb.edit_message_text(f"دسته‌بندی: {cat_fa}\n\nلطفاً متن دستور خود را بنویسید و ارسال کنید:")

    elif data == "vis_public" or data == "vis_secret":
        is_public = (data == "vis_public")
        ot = t.get("order_text")
        category = t.get("category")
        temp.pop(uid, None)
        
        if not ot or not category:
            return await cb.edit_message_text("⚠️ منقضی شده.")
        
        async with pool.acquire() as conn:
            oid = await conn.fetchval(
                "INSERT INTO orders (user_id, order_text, category, is_public) VALUES ($1, $2, $3, $4) RETURNING id", 
                uid, ot, category, is_public
            )
            c = await conn.fetchrow("SELECT * FROM countries WHERE user_id = $1", uid)
        
        cat_fa = {"economic": "اقتصادی", "political": "سیاسی", "diplomacy": "دیپلماسی", "military": "نظامی"}.get(category, category)
        vis_fa = "عمومی" if is_public else "محرمانه"
        
        if category == "diplomacy":
            await cb.edit_message_text("⏳ در حال بررسی توسط هوش مصنوعی و ارسال به کشور هدف...")
            await send_analysis(cb, context, oid)
        else:
            await context.bot.send_message(
                ADMIN_ID, 
                f"📜 **دستور جدید از {c['name']}**\n"
                f"🗂 دسته: {cat_fa} | وضعیت: {vis_fa}\n"
                f"📝 متن: {ot}", 
                parse_mode="Markdown", 
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ تایید و تحلیل", callback_data=f"ord_appr_{oid}")],
                    [InlineKeyboardButton("❌ رد", callback_data=f"ord_rej_{oid}")]
                ])
            )
            await cb.edit_message_text("⏳ ارسال به ادمین.")

    elif data.startswith("diplo_accept_"):
        oid = int(data.split("_")[2])
        async with pool.acquire() as conn:
            order = await conn.fetchrow("SELECT * FROM orders WHERE id = $1", oid)
            if not order or order['status'] != 'diplo_pending':
                return await cb.edit_message_text("⚠️ این درخواست منقضی شده یا قبلاً پاسخ داده شده.")
            
            await conn.execute("UPDATE orders SET status = 'pending_admin', player_approved = TRUE WHERE id = $1", oid)
            sender = await conn.fetchrow("SELECT name FROM countries WHERE user_id = $1", order['user_id'])
            receiver = await conn.fetchrow("SELECT name FROM countries WHERE user_id = $1", uid)
            
        await cb.edit_message_text("✅ شما این توافق را پذیرفتید. درخواست برای تایید نهایی به ادمین ارسال شد.")
        
        try:
            await context.bot.send_message(
                order['user_id'],
                f"🎉 **خبر خوش!**\nکشور {receiver['name']} پیشنهاد دیپلماتیک شما را پذیرفت. در انتظار تایید ادمین برای انتشار."
            )
        except: 
            pass
        
        vis_fa = "عمومی" if order['is_public'] else "محرمانه"
        await context.bot.send_message(
            ADMIN_ID, 
            f"🤝 **توافق دیپلماتیک تایید شده توسط طرفین**\n"
            f"👤 فرستنده: {sender['name']}\n"
            f"🎯 گیرنده: {receiver['name']}\n"
            f"📝 متن: {order['order_text']}\n"
            f"وضعیت: {vis_fa}\n"
            f"آیا تایید نهایی می‌کنید؟", 
            parse_mode="Markdown", 
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ تایید نهایی و انتشار", callback_data=f"final_appr_{oid}")],
                [InlineKeyboardButton("❌ رد", callback_data=f"ord_rej_{oid}")]
            ])
        )

    elif data.startswith("diplo_reject_"):
        oid = int(data.split("_")[2])
        async with pool.acquire() as conn:
            order = await conn.fetchrow("SELECT * FROM orders WHERE id = $1", oid)
            if not order or order['status'] != 'diplo_pending':
                return await cb.edit_message_text("⚠️ این درخواست منقضی شده.")
            
            await conn.execute("UPDATE orders SET status = 'rejected', player_approved = FALSE WHERE id = $1", oid)
            sender = await conn.fetchrow("SELECT name FROM countries WHERE user_id = $1", order['user_id'])
            receiver = await conn.fetchrow("SELECT name FROM countries WHERE user_id = $1", uid)
            
        await cb.edit_message_text("❌ شما این توافق را رد کردید.")
        
        try:
            await context.bot.send_message(
                order['user_id'],
                f"❌ **درخواست رد شد.**\nکشور {receiver['name']} پیشنهاد دیپلماتیک شما را نپذیرفت."
            )
        except: 
            pass

    elif data.startswith("final_appr_"):
        oid = int(data.split("_")[2])
        async with pool.acquire() as conn:
            order = await conn.fetchrow("SELECT * FROM orders WHERE id = $1", oid)
            if not order: 
                return
        
        try: 
            ai_data = json.loads(order["ai_analysis_raw"] or "{}")
        except: 
            ai_data = {}
            
        text_to_send = ai_data.get('narrative_long', 'توافق انجام شد.')
        final_text = f"📢 **بیانیه رسمی**\n\n{text_to_send}"
        
        if order['status'] == 'pending_admin':
            try:
                g_change = int(ai_data.get("gdp_change") or 0)
                m_change = int(ai_data.get("mil_budget_change") or 0)
                j_change = int(ai_data.get("jets_change") or 0)
                t_change = int(ai_data.get("tanks_change") or 0)
                
                async with pool.acquire() as conn:
                    await conn.execute(
                        "UPDATE countries SET gdp = GREATEST(0, gdp + $1), mil_budget = GREATEST(0, mil_budget + $2), jets = GREATEST(0, jets + $3), tanks = GREATEST(0, tanks + $4) WHERE user_id = $5 OR name = $6", 
                        g_change, m_change, j_change, t_change, order['user_id'], order.get('target_country')
                    )
                    await conn.execute("UPDATE orders SET status = 'published' WHERE id = $1", oid)
            except Exception as e:
                logger.error(f"Failed to apply diplo changes: {e}")
        
        if order['is_public']:
            if GROUP_ID and TOPIC_ID:
                try:
                    await context.bot.send_message(
                        chat_id=int(GROUP_ID), text=final_text, 
                        message_thread_id=int(TOPIC_ID), parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"Group publish error: {e}")
            elif CHANNEL_ID:
                try:
                    await context.bot.send_message(int(CHANNEL_ID.strip()), final_text)
                except: 
                    pass
            
        await cb.edit_message_text("✅ تایید نهایی انجام شد و نتیجه اعمال گردید.")

    elif data.startswith("enc_yes_"):
        enc_id = int(data.split("_")[2])
        await cb.edit_message_text("✅ نبرد آغاز شد.")
        await handle_intent_response(context, enc_id, uid, "attack")

    elif data.startswith("enc_no_"):
        enc_id = int(data.split("_")[2])
        await cb.edit_message_text("🕊️ عقب‌نشینی ثبت شد.")
        await handle_intent_response(context, enc_id, uid, "retreat")
        
    elif data.startswith("intent_patrol_"):
        enc_id = int(data.split("_")[2])
        await cb.edit_message_text("🕊️ نیت شما: فقط گشت‌زنی.")
        await handle_intent_response(context, enc_id, uid, "patrol")

    elif data.startswith("intent_attack_"):
        enc_id = int(data.split("_")[2])
        await cb.edit_message_text("⚔️ نیت شما: حمله.")
        await handle_intent_response(context, enc_id, uid, "attack")

    elif data.startswith("intent_retreat_"):
        enc_id = int(data.split("_")[2])
        await cb.edit_message_text("🏃 نیت شما: عقب‌نشینی.")
        await handle_intent_response(context, enc_id, uid, "retreat")

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
        final_text = f"📢 بیانیه رسمی\n\n{text_to_send}"
        
        sent = False
        if GROUP_ID and TOPIC_ID:
            try:
                await context.bot.send_message(
                    chat_id=int(GROUP_ID), text=final_text, 
                    message_thread_id=int(TOPIC_ID), parse_mode="Markdown"
                )
                sent = True
            except Exception as e:
                logger.error(f"Group publish error: {e}")
                
        if not sent and CHANNEL_ID:
            try:
                await context.bot.send_message(int(CHANNEL_ID.strip()), final_text)
                sent = True
            except Exception as e:
                logger.error(f"Channel publish error: {e}")
                
        if sent:
            async with pool.acquire() as conn: 
                await conn.execute("UPDATE orders SET status = 'published' WHERE id = $1", oid)
            await cb.edit_message_text("✅ با موفقیت منتشر شد.")
        else:
            await cb.edit_message_text("❌ خطا در ارسال.")
            
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
    ai_data = await analyze_and_apply_order(order_id, context)
    st = "✅ موفق" if ai_data.get("success") else "❌ ناموفق"
    ch = f"\n📈 GDP: {ai_data.get('gdp_change',0):+,} $ | ✈️ جنگنده: {ai_data.get('jets_change',0):+,} | 🚜 تانک: {ai_data.get('tanks_change',0):+,} | ❤️ رضایت: {ai_data.get('satisfaction_change',0):+,}\n" if ai_data.get("success") else ""
    
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
                
    await context.bot.send_message(ADMIN_ID, "✅ نوبت پردازش شد.")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(f"Update {update} caused error {context.error}", exc_info=context.error)

async def post_init(app):
    await init_db()
    await set_commands(app)
    await app.bot.delete_webhook(drop_pending_updates=True)

def main():
    app = Application.builder().token(TOKEN).post_init(post_init).build()
    app.add_error_handler(error_handler)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("country", country_cmd))
    app.add_handler(CommandHandler("military", military_cmd))
    app.add_handler(CommandHandler("economy", economy_cmd))
    app.add_handler(CommandHandler("mines", mines_cmd))
    app.add_handler(CommandHandler("factory", factory_cmd))
    app.add_handler(CommandHandler("order", order_cmd))
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    rh = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
    if rh:
        port = int(os.environ.get("PORT", 10000))
        app.run_webhook(
            listen="0.0.0.0", 
            port=port, 
            url_path=TOKEN, 
            webhook_url=f"https://{rh}/{TOKEN}"
        )
    else:
        app.run_polling()

if __name__ == "__main__":
    main()
