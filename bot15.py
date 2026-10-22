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
    "tank_armor": "🛡 آلیاژ زره", "jet_engine": "🚀 سوپرآلیاژ جت", "electronics": "📟 الکترونیک", "ammo": "🔫 مهمات",
    "gold": "🏵 طلا", "lead": "🔘 سرب", "zinc": "⚪ روی", "phosphate": "🧪 فسفات", "sulfur": "🟡 گوگرد"
}

MILITARY_DB = {
    "ایران": {"tanks": "چیفتن ۸۹۴، M60 ۴۶۰، M47 ۴۰۰، اسکورپیون ۲۵۰", "aircraft": "F-14 ۷۷، F-4 ۱۹۰، F-5 ۱۶۶", "air_defense": "هاوک، توپ‌های ۱۸۰۰ عراده‌ای", "navy": "۳ ناوشکن، ۴ ناوچه موشک‌انداز، ۱۴ هاورکرافت", "small_arms": "G3"},
    "آمریکا": {"tanks": "M60A3 ۲۵۶۰، M48A5 ۲۰۶۷، M551 ۵۹", "aircraft": "F-15, F-16, F-4, A-10, B-52 ۳۴۶", "air_defense": "Chaparral, Vulcan, Redeye", "navy": "۱۳ ناو هواپیمابر، ۲۸ رزمناو، ۹۷ ناوشکن، ۴۱ SSBN", "small_arms": "M16A1, M1911A1"},
    "شوروی": {"tanks": "T-64/T-72/T-80 بیش از ۲۰,۰۰۰، T-62/T-55/54 (مجموع ۵۰,۰۰۰)", "aircraft": "MiG-23/27, Su-17/24, Tu-95, Tu-22M", "air_defense": "SA-2, SA-3, SA-5, SA-10", "navy": "۱۸۰ زیردریایی هسته‌ای، ۶۴ SSBN، ۲۴۸ شناور سطحی بزرگ", "small_arms": "AK-74, AKM"},
    "چین": {"tanks": "59式، 69式، T-34 (۹۰۰۰-۱۰۰۰۰)", "aircraft": "歼-5 ۱۴۰۰، 歼-6 ۱۰۰۰، 歼-7 ۷۵، 强-5 ۳۰۰", "air_defense": "SA-2, توپ‌های ۱۰۰mm", "navy": "۵۴ زیردریایی، ۱۶ ناوشکن/ناوچه، ۷۶۳ قایق گشتی", "small_arms": "56式 (AK-47 clone)"},
    "عراق": {"tanks": "T-54/55/62 (۱۷۰۰)، T-72 (۱۰۰)", "aircraft": "MiG-21 ۲۰۶، 歼-7 ۴۰، Mirage F1 ۱۲، Tu-22 ۳۲", "air_defense": "SA-2, SA-3, SA-6", "navy": "۱۲ قایق موشک‌انداز OSA، ۱۲ اژدرافکن P-6", "small_arms": "AK-47, Tabuk"},
    "اسرائیل": {"tanks": "Centurion ۱۰۰۰، M60 ۸۱۰، M48 ۶۵۰، Merkava ۴۰", "aircraft": "F-15 ۲۴، F-4 ۹۰، A-4 ۲۷۰، Kfir ۸۰", "air_defense": "Chaparral, Vulcan, Redeye", "navy": "۲۲ قایق موشک‌انداز (Reshef/Saar)، ۳ زیردریایی Type 206", "small_arms": "Galil, Uzi, M16A1"},
    "مصر": {"tanks": "T-54/55 ۸۵۰، T-62 ۷۵۰، M60A3 ۶۰", "aircraft": "MiG-21 ۲۵۰، F-4E ۱۶، Tu-16 ۲۵، Mirage 5 ۶۰", "air_defense": "SA-2 ۳۶۰، SA-3 ۲۰۰، SA-6 ۷۵", "navy": "۵ ناوشکن، ۱۲ زیردریایی، ۱۷ قایق موشک‌انداز", "small_arms": "AK-47"},
    "سوریه": {"tanks": "T-55 ۱۵۰۰، T-62 ۸۰۰، T-72 ۶۵", "aircraft": "MiG-21 ۲۰۰، MiG-23 ۵۰، MiG-25 ۱۲، Su-20/22 ۳۰", "air_defense": "SA-2, SA-3, SA-6", "navy": "۱۴ قایق موشک‌انداز OSA/Komar", "small_arms": "AK-47"},
    "بریتانیا": {"tanks": "Chieftain ۶۴۰", "aircraft": "Vulcan, Buccaneer, Jaguar ۵۲، Phantom ۴۰", "air_defense": "Rapier, Bloodhound", "navy": "۱۳۹ ناوشکن/ناوچه، ۳۰ زیردریایی، ۲ ناو هواپیمابر سبک", "small_arms": "L1A1 SLR, Sterling"},
    "فرانسه": {"tanks": "AMX-30 ۱۳۶۰", "aircraft": "Mirage F1 ۹۰، Jaguar ۱۷۴، Mirage IV ۳۴", "air_defense": "Roland, Hawk", "navy": "۲ ناو هواپیمابر، ۴ SSBN، ۲۲ زیردریایی", "small_arms": "FAMAS, MAS 49/56"},
    "آلمان غربی": {"tanks": "Leopard 1 ۲۴۰۰، Leopard 2 (جدید)، M48 ۶۵۰", "aircraft": "F-4 ۱۷۵، RF-4E ۸۸، F-104 ۱۴۴، Tornado (جدید)", "air_defense": "Roland, Gepard", "navy": "۲۴ زیردریایی، ۱۸ ناوشکن/ناوچه، ۴۰ قایق موشک‌انداز", "small_arms": "G3, MP5"},
    "آلمان شرقی": {"tanks": "T-54/55 ۲۵۰۰، T-72 ۵۴۹، T-34 ۶۰۰", "aircraft": "MiG-21 ۳۰۰، Su-7 ۸۰، MiG-23 ۳", "air_defense": "SA-4, SA-6, SA-7", "navy": "۱۵ قایق موشک‌انداز OSA، ۴۸ اژدرافکن، ۵۱ مین‌روب", "small_arms": "AK-47/74"},
    "ژاپن": {"tanks": "Type 74 ۷۴۰، Type 61", "aircraft": "F-4EJ ۱۵۰، F-1 ۷۷، F-104J", "air_defense": "Hawk, توپ‌های ۳۵mm", "navy": "۶۰ ناوشکن/ناوچه، ۱۶ زیردریایی", "small_arms": "Howa Type 64"},
    "هند": {"tanks": "T-54/55 ۹۵۰، T-72 ۷۰، Vijayanta ۱۱۰۰", "aircraft": "MiG-21 ۶۲۵، Su-7، Jaguar ۱۵۰، Gnat", "air_defense": "SA-2, توپ‌های ۴۰mm", "navy": "۲ ناو هواپیمابر، ۶ زیردریایی، ۲۳ ناوشکن/ناوچه", "small_arms": "Ishapore 2A1 (L1A1)"},
    "پاکستان": {"tanks": "Type 59، M48 (۱۰۰۰)", "aircraft": "MiG-19، Mirage III، F-6 (۲۴۷)", "air_defense": "SA-2, توپ‌های ۳۷mm", "navy": "۳۰ زیردریایی/ناوچه، قایق‌های گشتی", "small_arms": "G3, AK-47"},
    "ترکیه": {"tanks": "M48 ۳۰۰۰، M47", "aircraft": "F-4 ۳۰۰، F-100، F-104", "air_defense": "Rapier, توپ‌های ۴۰mm", "navy": "۱۳ ناوشکن/ناوچه، ۱۵ زیردریایی", "small_arms": "G3, M1 Garand"},
    "برزیل": {"tanks": "M41 ۲۵۰، M3A1 ۲۲۰، X1A2 ۲۵", "aircraft": "Mirage III، F-5E ۷۹، AT-26", "air_defense": "Roland", "navy": "۱ ناو هواپیمابر، ۱۰ زیردریایی، ۲ ناوشکن", "small_arms": "FN FAL (M964)"},
    "آرژانتین": {"tanks": "M4 Sherman، AMX-13، TAM (۳۵۰)", "aircraft": "Dagger ۳۵، Pucara ۳۰، A-4، Canberra ۸", "air_defense": "Roland", "navy": "۱ ناو هواپیمابر، ۴ زیردریایی، ۸ ناوشکن", "small_arms": "FN FAL, FMK-3"},
    "کره جنوبی": {"tanks": "M47، M48 (۳۵۰)", "aircraft": "F-4 ۷۰، F-5 ۲۰۰، F-86 (۵۲۰)", "air_defense": "Hawk, Vulcan", "navy": "۶۰ ناوشکن/ناوچه، ۱۶ زیردریایی", "small_arms": "M16A1"},
    "کره شمالی": {"tanks": "T-34 ۳۰۰، T-54/55، T-62 (۲۳۰۰)", "aircraft": "MiG-21 ۱۲۰، MiG-17 ۱۱۰، MiG-19 ۱۳۰ (۵۶۵)", "air_defense": "SA-2, توپ‌های ۱۰۰mm", "navy": "۲۰ زیردریایی، ۵۲ قایق موشک‌انداز", "small_arms": "AK-47, Type 58"},
    "ویتنام": {"tanks": "T-54/55 ۱۶۰۰، Type 59 ۱۶۰، PT-76 ۴۵۰ (۲۰۰۰)", "aircraft": "MiG-21 ۷۰، MiG-19 ۷۰، MiG-17 ۱۲۰، F-5 ۴۱ (۳۰۰)", "air_defense": "SA-2 ۳۶۰، SA-3", "navy": "۸ قایق موشک‌انداز OSA، ۵ مین‌روب", "small_arms": "AK-47, M16"},
    "کوبا": {"tanks": "T-54/55 ۶۳۰، T-62 ۵۰، T-34 ۳۵۰", "aircraft": "MiG-23 ۲۰، MiG-21 ۷۸، MiG-19 ۴۰، MiG-17 ۳۰ (۱۶۸)", "air_defense": "SA-2, SA-3, ZSU-23-4", "navy": "۲ زیردریایی Foxtrot، ۱۳ قایق موشک‌انداز OSA-II", "small_arms": "AK-47, FN FAL"},
    "عربستان": {"tanks": "M47، M41، AML-60/90 (۵۵۰)", "aircraft": "F-5E ۵۰", "air_defense": "Hawk, توپ‌های ۳۵mm", "navy": "قایق‌های گشتی ساحلی", "small_arms": "FN FAL, G3"}
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
                user_id BIGINT PRIMARY KEY, 
                username TEXT, 
                name TEXT, 
                status TEXT DEFAULT 'pending', 
                gdp BIGINT DEFAULT 500000000, 
                mil_budget BIGINT DEFAULT 35000000, 
                jets INT DEFAULT 0, 
                tanks INT DEFAULT 0, 
                refineries INT DEFAULT 0, 
                army INT DEFAULT 100000, 
                satisfaction INT DEFAULT 50, 
                tax_rate INT DEFAULT 10, 
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS deployments (
                id SERIAL PRIMARY KEY, 
                user_id BIGINT, 
                country_name TEXT, 
                region TEXT, 
                asset_type TEXT, 
                model TEXT, 
                quantity INT, 
                status TEXT DEFAULT 'active', 
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS infrastructure (
                id SERIAL PRIMARY KEY, 
                user_id BIGINT, 
                sector_type TEXT, 
                name TEXT, 
                income BIGINT DEFAULT 0, 
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id SERIAL PRIMARY KEY, 
                user_id BIGINT, 
                order_text TEXT, 
                category TEXT, 
                status TEXT DEFAULT 'pending', 
                ai_analysis_raw TEXT, 
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        for res in RESOURCES.keys():
            await conn.execute(f"ALTER TABLE countries ADD COLUMN IF NOT EXISTS res_{res} BIGINT DEFAULT 0")
            
    logger.info("Database initialized with Deployments table.")

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
    if isinstance(raw, dict): 
        return raw
    if not raw or not isinstance(raw, str): 
        return {}
    start, end = raw.find('{'), raw.rfind('}')
    if start == -1 or end == -1: 
        return {}
    s = raw[start:end + 1].replace("```json", "").replace("```", "").strip()
    try: return json.loads(s)
    except: pass
    try: return ast.literal_eval(s)
    except: pass
    try: return ast.literal_eval(s.replace("true", "True").replace("false", "False").replace("null", "None"))
    except: pass
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

def _build_prompt(country: dict, order_text: str, category: str, enemy_deployments: str) -> str:
    if category == "political": 
        narrative_rule = "The narrative MUST be a highly dramatic, grandiloquent political speech."
    elif category == "military": 
        narrative_rule = "The narrative MUST be an epic war report."
    else: 
        narrative_rule = "The narrative MUST be a dramatic economic news report."

    return f"""You are the strict Game Master of a grand strategy game set in 1979.
Analyze the order based on the exact 1979 historical stats, calculate impacts, and simulate regional battles.

COUNTRY STATS:
- Name: {country['name']}
- GDP: ${country['gdp']:,}
- Military Budget: ${country['mil_budget']:,}
- Army: {country['army']}, Tanks: {country['tanks']}, Jets: {country['jets']}

FORCE DETAILS:
{MILITARY_DB.get(country['name'], {})}

CURRENT ENEMY DEPLOYMENTS GLOBALLY:
{enemy_deployments}

PLAYER ORDER: "{order_text}"
CATEGORY: {category}

RULES (CRITICAL):
1. If the order is to DEPLOY forces to a region (e.g., "deploy 10 F-15 to Alaska"):
   - Extract the region name (e.g., "Alaska").
   - Set "action_type": "deploy".
   - Cost to deploy is $500,000 per unit. Deduct this from "mil_budget_change".
   - Check the ENEMY DEPLOYMENTS list. If the enemy has forces in the SAME region, a battle occurs!
   - Calculate "my_losses" and "enemy_losses" logically based on models and quantities.
   - Deduct "my_losses" from the deployed quantity before finalizing.
2. If the order is an ATTACK on an existing region:
   - Set "action_type": "attack".
   - Simulate battle with enemy forces in that region. Calculate losses.
3. If the order is ECONOMIC or POLITICAL, use standard rules (GDP/Mil_Budget changes).
4. ALL money values are in EXACT US DOLLARS.

EXACT JSON FORMAT:
{{
  "success": true/false,
  "reason": "Strict Persian reason",
  "action_type": "deploy" or "attack" or "economic" or "political",
  "region": "Alaska" or "None",
  "deployed_asset": "F-15" or "None",
  "deployed_quantity": 10,
  "deployment_cost": 5000000,
  "battle_occurred": true or false,
  "enemy_country": "USA" or "None",
  "my_losses": 2,
  "enemy_losses": 5,
  "gdp_change": 0,
  "mil_budget_change": -5000000,
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
    
    if data.get("battle_occurred") and region != "None":
        enemy = data.get("enemy_country")
        my_losses = int(data.get("my_losses", 0))
        enemy_losses = int(data.get("enemy_losses", 0))
        
        if my_losses > 0:
            async with pool.acquire() as conn:
                await conn.execute("UPDATE deployments SET quantity = quantity - $1 WHERE country_name = $2 AND region = $3 AND quantity >= $1", my_losses, country_name, region)
                await conn.execute("DELETE FROM deployments WHERE quantity <= 0")
                
        if enemy_losses > 0 and enemy != "None":
            async with pool.acquire() as conn:
                await conn.execute("UPDATE deployments SET quantity = quantity - $1 WHERE country_name = $2 AND region = $3 AND quantity >= $1", enemy_losses, enemy, region)
                await conn.execute("DELETE FROM deployments WHERE quantity <= 0")
                enemy_user = await conn.fetchrow("SELECT user_id FROM countries WHERE name = $1", enemy)
            
            if enemy_user:
                try:
                    await context.bot.send_message(enemy_user['user_id'], f"⚠️ **هشدار نظامی!**\nنیروهای شما در منطقه {region} مورد حمله قرار گرفتند و {enemy_losses} فروند/عراده تلفات دادند.")
                except: 
                    pass

async def analyze_and_apply_order(order_id: int, context):
    try:
        return await asyncio.wait_for(_analyze_inner(order_id, context), timeout=120.0)
    except asyncio.TimeoutError:
        data = {"success": False, "reason": "پردازش طول کشید", "narrative_short": "به تعویق افتاد.", "narrative_long": "به تعویق افتاد."}
        async with pool.acquire() as conn:
            await conn.execute("UPDATE orders SET status='ai_analyzed', ai_analysis_raw=$1 WHERE id=$2", json.dumps(data, ensure_ascii=False), order_id)
        return data

async def _analyze_inner(order_id: int, context):
    async with pool.acquire() as conn:
        order = await conn.fetchrow("SELECT * FROM orders WHERE id = $1", order_id)
        if not order: 
            return {"success": False, "reason": "سفارش یافت نشد", "narrative_short": "", "narrative_long": ""}
        country = await conn.fetchrow("SELECT * FROM countries WHERE user_id = $1", order["user_id"])
    
    enemy_deployments_str = await get_enemy_deployments_str(country['name'])
    prompt = _build_prompt(dict(country), order["order_text"], order["category"], enemy_deployments_str)
    ai_response = await ask_ai(prompt, system_prompt="You are a strict JSON-only API. Use ONLY Persian characters.")
    data = _safe_parse_json(ai_response)

    if "success" not in data or "narrative_long" not in data:
        data = {"success": False, "reason": "پاسخ نامعتبر بود", "narrative_short": "خطا", "narrative_long": "نیاز به بررسی دستی.", "gdp_change": 0, "mil_budget_change": 0, "jets_change": 0, "tanks_change": 0, "refineries_change": 0, "satisfaction_change": 0, "battle_occurred": False}

    for k in ["narrative_short", "narrative_long", "reason"]:
        if k in data: 
            data[k] = _clean_persian_text(str(data[k]))

    if data.get("success"):
        try:
            g_change = int(data.get("gdp_change") or 0)
            m_change = int(data.get("mil_budget_change") or 0)
            j_change = int(data.get("jets_change") or 0)
            t_change = int(data.get("tanks_change") or 0)
            r_change = int(data.get("refineries_change") or 0)
            s_change = int(data.get("satisfaction_change") or 0)
        except:
            data = {"success": False, "reason": "خطای عددی", "narrative_short": "", "narrative_long": "", "gdp_change": 0, "mil_budget_change": 0, "jets_change": 0, "tanks_change": 0, "refineries_change": 0, "satisfaction_change": 0, "battle_occurred": False}
        else:
            if country["gdp"] + g_change < 0 or country["mil_budget"] + m_change < 0:
                data = {"success": False, "reason": "ورشکستگی! بودجه کافی نیست.", "gdp_change": 0, "mil_budget_change": 0, "jets_change": 0, "tanks_change": 0, "refineries_change": 0, "satisfaction_change": -5, "narrative_short": "اقتصاد فروپاشید.", "narrative_long": "با خالی شدن خزانه ملی، طرح پیشنهادی با شکست مواجه شد.", "battle_occurred": False}
            else:
                new_sat = max(0, min(100, country.get("satisfaction", 50) + s_change))
                data["satisfaction_change"] = new_sat - country.get("satisfaction", 50)
                async with pool.acquire() as conn:
                    await conn.execute(
                        "UPDATE countries SET gdp = GREATEST(0, gdp + $1), mil_budget = GREATEST(0, mil_budget + $2), jets = GREATEST(0, jets + $3), tanks = GREATEST(0, tanks + $4), refineries = GREATEST(0, refineries + $5), satisfaction = $6 WHERE user_id = $7", 
                        g_change, m_change, j_change, t_change, r_change, new_sat, order["user_id"]
                    )
                await apply_battle_changes(context, order["user_id"], country['name'], data)

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
        BotCommand("order", "دستور جدید"), 
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
        f"🚜 **تانک‌ها:** {mil_data['tanks']}\n\n"
        f"✈️ **هواپیماها:** {mil_data['aircraft']}\n\n"
        f"🛡 **پدافند هوایی:** {mil_data['air_defense']}\n\n"
        f"⚓ **نیروی دریایی:** {mil_data['navy']}\n\n"
        f"🔫 **سلاح‌های سبک:** {mil_data['small_arms']}\n\n"
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
    if not context.args: 
        return await update.message.reply_text("⚠️ مثال: `/order استقرار 10 جنگنده F-15 در آلاسکا`")
        
    temp[uid] = {"order_text": " ".join(context.args), "step": "ORDER_CATEGORY"}
    await update.message.reply_text("دسته‌بندی؟", reply_markup=kb([[InlineKeyboardButton("💰 اقتصادی", callback_data="cat_economic")], [InlineKeyboardButton("🏛️ سیاسی", callback_data="cat_political")], [InlineKeyboardButton("⚔️ نظامی", callback_data="cat_military")]]))

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
    ai_data = await analyze_and_apply_order(order_id, context)
    st = "✅ موفق" if ai_data.get("success") else "❌ ناموفق"
    ch = f"\n📈 GDP: {ai_data.get('gdp_change',0):+,} $ | ✈️ جنگنده: {ai_data.get('jets_change',0):+,} | 🚜 تانک: {ai_data.get('tanks_change',0):+,} | 🏭 پالایشگاه: {ai_data.get('refineries_change',0):+,} | ❤️ رضایت: {ai_data.get('satisfaction_change',0):+,}\n" if ai_data.get("success") else ""
    
    battle_str = ""
    if ai_data.get("battle_occurred"):
        battle_str = f"\n⚔️ **درگیری در {ai_data.get('region')}!**\nتلفات ما: {ai_data.get('my_losses')} | تلفات دشمن ({ai_data.get('enemy_country')}): {ai_data.get('enemy_losses')}\n"
    
    txt = f"🧠 تحلیل (70B)\n\n📌 وضعیت: {st}\n📝 دلیل: {ai_data.get('reason', '')}\n{ch}{battle_str}\n📰 **خلاصه:**\n{ai_data.get('narrative_short', '')}\n\n📖 **کامل:**\n{ai_data.get('narrative_long', '')}"
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

async def post_init(app):
    await init_db()
    await set_commands(app)
    await app.bot.delete_webhook(drop_pending_updates=True)

def main():
    app = Application.builder().token(TOKEN).post_init(post_init).build()
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
        app.run_webhook(listen="0.0.0.0", port=port, url_path=TOKEN, webhook_url=f"https://{rh}/{TOKEN}")
    else: 
        app.run_polling()

if __name__ == "__main__":
    main()
