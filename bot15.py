import os
import json
import ast
import asyncio
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
CHANNEL_ID = os.environ.get("CHANNEL_ID", "")
CLOUDFLARE_API_TOKEN = os.environ.get("CLOUDFLARE_API_TOKEN", "")
CLOUDFLARE_ACCOUNT_ID = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")

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

INDUSTRIES = {
    "Massive": {"name": "صنایع عظیم", "cost": 39000, "income": 17000, "build_workers": 12000, "max_limit": 10, "tech": 600, "workers": 2100, "power": 5000},
    "Large": {"name": "صنایع بزرگ", "cost": 25000, "income": 7000, "build_workers": 8000, "max_limit": 20, "tech": 250, "workers": 1500, "power": 2000},
    "Medium": {"name": "صنایع متوسط", "cost": 13000, "income": 3000, "build_workers": 4000, "max_limit": 30, "tech": 70, "workers": 600, "power": 1000},
    "Small": {"name": "صنایع کوچک", "cost": 7000, "income": 1000, "build_workers": 1500, "max_limit": 60, "tech": 20, "workers": 200, "power": 500},
}

RESOURCE_FACILITIES = {
    "mine_iron": {"name": "⛏ معدن آهن", "cost": 10000, "income": 2000, "build_workers": 2000, "max_limit": 20, "tech": 50, "workers": 500, "power": 1000},
    "mine_copper": {"name": "🟤 معدن مس", "cost": 15000, "income": 3500, "build_workers": 3000, "max_limit": 15, "tech": 80, "workers": 800, "power": 1500},
    "mine_oil": {"name": "🛢 چاه نفت", "cost": 25000, "income": 8000, "build_workers": 5000, "max_limit": 10, "tech": 150, "workers": 1200, "power": 2500},
    "mine_gold": {"name": "🏵 معدن طلا", "cost": 40000, "income": 15000, "build_workers": 8000, "max_limit": 5, "tech": 300, "workers": 2000, "power": 4000},
    "ref_steel": {"name": "🏗 پالایشگاه فولاد", "cost": 20000, "income": 5000, "build_workers": 4000, "max_limit": 15, "tech": 120, "workers": 1000, "power": 2000},
    "ref_oil": {"name": "🛢 پالایشگاه نفت", "cost": 35000, "income": 10000, "build_workers": 6000, "max_limit": 10, "tech": 250, "workers": 1500, "power": 3500},
    "ref_copper": {"name": "🔌 پالایشگاه مس", "cost": 25000, "income": 6000, "build_workers": 5000, "max_limit": 10, "tech": 180, "workers": 1200, "power": 2500},
}

pool = None

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
                gov_main TEXT,
                gov_sub TEXT,
                status TEXT DEFAULT 'pending',
                treasury BIGINT DEFAULT 100000,
                gdp BIGINT DEFAULT 500000,
                army INT DEFAULT 10000,
                technicians BIGINT DEFAULT 1000,
                workers BIGINT DEFAULT 10000,
                power BIGINT DEFAULT 5000,
                tax_rate INT DEFAULT 10,
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
                admin_note TEXT,
                ai_analysis_raw TEXT,
                final_text TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                published_at TIMESTAMP DEFAULT NULL
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS cities (
                id SERIAL PRIMARY KEY, 
                user_id BIGINT, 
                name TEXT, 
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
        
        # برای دیتابیس‌های قدیمی
        await conn.execute("ALTER TABLE countries ADD COLUMN IF NOT EXISTS technicians BIGINT DEFAULT 1000")
        await conn.execute("ALTER TABLE countries ADD COLUMN IF NOT EXISTS workers BIGINT DEFAULT 10000")
        await conn.execute("ALTER TABLE countries ADD COLUMN IF NOT EXISTS power BIGINT DEFAULT 5000")
        await conn.execute("ALTER TABLE countries ADD COLUMN IF NOT EXISTS tax_rate INT DEFAULT 10")
        
    logger.info("Database initialized.")

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

async def ask_ai(prompt: str, system_prompt: str = "You are a game master API. Output raw JSON only. Do NOT wrap in markdown.") -> str:
    url = f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/ai/run/@cf/meta/llama-3.3-70b-instruct-fp8-fast"
    headers = {
        "Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}", 
        "Content-Type": "application/json"
    }
    payload = {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 512
    }
    
    for attempt in range(3):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, json=payload, timeout=120.0)
                logger.info(f"Cloudflare Status (Attempt {attempt+1}): {response.status_code}")
                
                if response.status_code != 200:
                    if attempt < 2:
                        await asyncio.sleep(2)
                        continue
                    return '{"success": false, "reason": "خطای کلودفلر", "narrative": "پاسخی دریافت نشد."}'
                
                res_data = response.json()
                
                if res_data.get("success"):
                    return res_data["result"]["response"]
                else:
                    if attempt < 2:
                        await asyncio.sleep(2)
                        continue
                    return '{"success": false, "reason": "خطای مدل", "narrative": "مدل نتوانست پاسخ دهد."}'
                    
        except Exception as e:
            logger.error(f"AI Request Exception (Attempt {attempt+1}): {str(e)}")
            if attempt < 2:
                await asyncio.sleep(2)
                continue
            return '{"success": false, "reason": "تایم اوت", "narrative": "ارتباط برقرار نشد."}'

async def analyze_and_apply_order(order_id: int, context):
    order = await get_order(order_id)
    country = await get_country(order["user_id"])
    
    enemies_data = []
    async with pool.acquire() as conn:
        enemies = await conn.fetch("SELECT name, army, treasury FROM countries WHERE user_id != $1 AND status = 'active'", country['user_id'])
        for e in enemies:
            enemies_data.append(f"Country: {e['name']} | Army: {e['army']} | Treasury: {e['treasury']}")
            
    enemies_text = "\n".join(enemies_data) if enemies_data else "No other countries exist yet."

    prompt = f"""
    Country: {country['name']}
    Treasury: {country['treasury']} units (1 unit = $1000)
    Army: {country['army']}
    Technicians: {country.get('technicians', 0)}
    Workers: {country.get('workers', 0)}
    Power: {country.get('power', 0)}
    
    Player Action: "{order['order_text']}"
    Category: {order['category']}
    
    List of other countries:
    {enemies_text}
    
    CRITICAL RULES:
    1. If the action is a military attack, check the enemies list. Compare armies. The winner takes 20% of the loser's treasury and kills 20% of their army. Set "target_country", "target_treasury_change", "target_army_change".
    2. If action requires more money than Treasury, "success": false.
    3. Calculate treasury_change in UNITS (10M dollars = -10000).
    
    Return strict JSON with keys:
    "success": boolean, "reason": string (Persian), 
    "treasury_change": integer, "army_change": integer, "gdp_change": integer, 
    "narrative": string (Persian),
    "target_country": string (or null),
    "target_treasury_change": integer, "target_army_change": integer
    """
    
    ai_response = await ask_ai(prompt)
    
    try:
        start_idx = ai_response.find('{')
        end_idx = ai_response.rfind('}')
        if start_idx != -1 and end_idx != -1:
            json_str = ai_response[start_idx:end_idx+1]
            try:
                data = json.loads(json_str)
            except json.JSONDecodeError:
                data = ast.literal_eval(json_str)
        else:
            data = {}
    except Exception as e:
        logger.error(f"Parse Error: {e} | AI Raw Output: {ai_response}")
        data = {"success": False, "reason": "خطای پردازش", "narrative": "دستور اجرا نشد."}

    if "success" not in data:
        data = {"success": False, "reason": "پاسخ نامعتبر", "narrative": "دستور نیاز به بررسی دستی دارد."}

    async with pool.acquire() as conn:
        if data.get("success"):
            new_treasury = max(0, country['treasury'] + data.get("treasury_change", 0))
            new_army = max(0, country['army'] + data.get("army_change", 0))
            new_gdp = max(1000, country['gdp'] + data.get("gdp_change", 0))
            
            await conn.execute("UPDATE countries SET treasury=$1, army=$2, gdp=$3 WHERE user_id=$4", 
                               new_treasury, new_army, new_gdp, order["user_id"])
            
            target_name = data.get("target_country")
            if target_name:
                target_country = await conn.fetchrow("SELECT * FROM countries WHERE name = $1", target_name)
                if target_country:
                    new_t_target_treasury = max(0, target_country['treasury'] + data.get("target_treasury_change", 0))
                    new_t_target_army = max(0, target_country['army'] + data.get("target_army_change", 0))
                    
                    await conn.execute("UPDATE countries SET treasury=$1, army=$2 WHERE user_id=$3", 
                                       new_t_target_treasury, new_t_target_army, target_country['user_id'])
                    
                    try:
                        await context.bot.send_message(
                            target_country['user_id'], 
                            f"🚨 **هشدار حمله!**\n\nکشور {country['name']} به شما حمله کرد.\n📜 رویداد: {data.get('narrative')}",
                            parse_mode="Markdown"
                        )
                    except:
                        pass
            
        await conn.execute("UPDATE orders SET status='ai_analyzed', ai_analysis_raw=$1 WHERE id=$2", 
                           json.dumps(data, ensure_ascii=False), order_id)
    
    return data

temp = {}

async def set_commands(app):
    cmds = [
        BotCommand("start", "ثبت‌نام و شروع بازی"),
        BotCommand("country", "مشاهده اطلاعات کشور"),
        BotCommand("order", "ثبت دستور جدید (نظامی/سیاسی)"),
        BotCommand("cities", "مدیریت شهرها"),
        BotCommand("economy", "مدیریت اقتصادی و مالیات"),
        BotCommand("regions", "مدیریت مناطق"),
        BotCommand("infra", "مدیریت صنایع"),
        BotCommand("mines", "مدیریت معادن و پالایشگاه‌ها"),
        BotCommand("admin", "پنل مدیریت و آمار"),
        BotCommand("turn", "پردازش درآمد نوبت (ادمین)"),
        BotCommand("cancel", "لغو عملیات")
    ]
    await app.bot.set_my_commands(cmds)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    c = await get_country(uid)
    
    if c:
        if c["status"] == "active":
            await update.message.reply_text(f"✅ کشور {c['name']} فعال است. برای ثبت دستور از /order استفاده کنید.")
        elif c["status"] == "pending":
            await update.message.reply_text("⏳ ثبت‌نام شما در انتظار تایید ادمین است.")
        return

    temp[uid] = {"step": "NAME"}
    await update.message.reply_text("🏛️ Welcome to rustabad RP\n\nلطفاً **نام کشور** خود را وارد کنید:", parse_mode="Markdown")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    temp.pop(update.effective_user.id, None)
    await update.message.reply_text("❌ عملیات لغو شد.")

async def country_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    c = await get_country(uid)
    if not c or c["status"] != "active":
        await update.message.reply_text("⚠️ ابتدا باید ثبت‌نام کنید و تایید بگیرید. /start")
        return
        
    text = (
        f"🏛️ *کشور: {c['name']}*\n"
        f"👤 رهبر: {c['leader']}\n"
        f"⚙️ حکومت: {GOVERNMENTS.get(c['gov_main'], {}).get('name', '')} - {GOVERNMENTS.get(c['gov_main'], {}).get('subs', {}).get(c['gov_sub'], '')}\n\n"
        f"💰 خزانه: {fmt_money(c['treasury'])}\n"
        f"🎖 ارتش: {c['army']:,} نفر\n"
        f"🧠 تکنسین: {c.get('technicians', 0):,} | 👷 کارگر: {c.get('workers', 0):,}\n"
        f"⚡️ برق: {c.get('power', 0):,}\n"
        f"📈 GDP: {fmt_money(c['gdp'])}\n"
        f"📊 نرخ مالیات: {c.get('tax_rate', 10)}٪"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid != ADMIN_ID:
        return
        
    async with pool.acquire() as conn:
        total_countries = await conn.fetchval("SELECT COUNT(*) FROM countries WHERE status = 'active'")
        pending_countries = await conn.fetchval("SELECT COUNT(*) FROM countries WHERE status = 'pending'")
        total_orders = await conn.fetchval("SELECT COUNT(*) FROM orders")
        pending_orders = await conn.fetchval("SELECT COUNT(*) FROM orders WHERE status = 'pending'")

    text = (
        f"👑 *پنل مدیریت Rustabad RP*\n\n"
        f"🌍 کشورهای فعال: {total_countries}\n"
        f"⏳ در انتظار ثبت‌نام: {pending_countries}\n\n"
        f"📜 کل دستورات: {total_orders}\n"
        f"⌛ دستورات در انتظار: {pending_orders}\n\n"
        f"💡 _برای پردازش درآمد، از /turn استفاده کنید._"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

async def turn_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
        
    async with pool.acquire() as conn:
        incomes = await conn.fetch("SELECT user_id, SUM(income) as total_income FROM infrastructure GROUP BY user_id")
        
        text = "⏳ *پردازش نوبت جدید...*\n\n"
        
        for row in incomes:
            if row['total_income'] > 0:
                await conn.execute("UPDATE countries SET treasury = treasury + $1 WHERE user_id = $2", row['total_income'], row['user_id'])
                country = await get_country(row['user_id'])
                text += f"✅ به {country['name']} مبلغ {fmt_money(row['total_income'])} واریز شد.\n"
                
    await update.message.reply_text(text, parse_mode="Markdown")

async def cities_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    c = await get_country(uid)
    if not c or c["status"] != "active":
        return
        
    async with pool.acquire() as conn:
        cities = await conn.fetch("SELECT * FROM cities WHERE user_id = $1", uid)
        
    text = f"🏙️ *مدیریت شهرها*\n\nتعداد شهرهای شما: {len(cities)}\n\n"
    if cities:
        for city in cities:
            text += f"🔹 {city['name']}\n"
    
    rows = []
    if len(cities) < 5:
        rows.append([InlineKeyboardButton("➕ تاسیس شهر جدید (هزینه: ۵ میلیون دلار)", callback_data="city_new")])
    
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=kb(rows))

async def economy_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    c = await get_country(uid)
    if not c or c["status"] != "active":
        return
        
    text = (
        f"💰 *وزارت اقتصاد {c['name']}*\n\n"
        f"📈 GDP: {fmt_money(c['gdp'])}\n"
        f"🏦 خزانه: {fmt_money(c['treasury'])}\n"
        f"📊 نرخ مالیات فعلی: {c.get('tax_rate', 10)}٪\n\n"
        f"درآمد مالیاتی هر نوبت: {fmt_money((c['gdp'] * c.get('tax_rate', 10)) // 100)}\n\n"
        f"⚠️ _مالیات بالا درآمد را زیاد می‌کند اما رضایت مردم را کاهش می‌دهد._"
    )
    rows = [
        [InlineKeyboardButton("📉 کاهش مالیات (۵-)", callback_data="tax_down")],
        [InlineKeyboardButton("📈 افزایش مالیات (۵+)", callback_data="tax_up")]
    ]
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=kb(rows))

async def regions_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    c = await get_country(uid)
    if not c or c["status"] != "active":
        return
        
    text = (
        f"🗺️ *مدیریت مناطق {c['name']}*\n\n"
        f"هزینه تاسیس هر منطقه: ۱۰ میلیون دلار\n\n"
        f"🔹 *نظامی*: افزایش GDP\n"
        f"🔹 *صنعتی*: افزایش GDP\n"
        f"🔹 *کشاورزی*: افزایش GDP"
    )
    rows = [
        [InlineKeyboardButton("🪖 منطقه نظامی", callback_data="region_military")],
        [InlineKeyboardButton("🏭 منطقه صنعتی", callback_data="region_industrial")],
        [InlineKeyboardButton("🌾 منطقه کشاورزی", callback_data="region_agricultural")]
    ]
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=kb(rows))

async def infra_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    c = await get_country(uid)
    if not c or c["status"] != "active":
        return
        
    async with pool.acquire() as conn:
        infras = await conn.fetch("SELECT sector_type, count(*) as count FROM infrastructure WHERE user_id = $1 GROUP BY sector_type", uid)
    
    counts = {r['sector_type']: r['count'] for r in infras}
    
    text = f"🏭 *مدیریت صنایع {c['name']}*\n\n"
    text += f"🧠 تکنسین آزاد: {c.get('technicians', 0):,}\n"
    text += f"👷 کارگر آزاد: {c.get('workers', 0):,}\n"
    text += f"⚡️ برق آزاد: {c.get('power', 0):,}\n\n"
    
    rows = []
    for key, data in INDUSTRIES.items():
        current_count = counts.get(key, 0)
        if current_count < data['max_limit']:
            rows.append([InlineKeyboardButton(f"➕ {data['name']} (هزینه: {fmt_money(data['cost'])})", callback_data=f"infra_build_{key}")])
        else:
            rows.append([InlineKeyboardButton(f"🚫 {data['name']} (سقف پر شده)", callback_data="infra_maxed")])
            
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=kb(rows))

async def mines_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    c = await get_country(uid)
    if not c or c["status"] != "active":
        return
        
    async with pool.acquire() as conn:
        facilities = await conn.fetch("SELECT sector_type, count(*) as count FROM infrastructure WHERE user_id = $1 AND (sector_type LIKE 'mine_%' OR sector_type LIKE 'ref_%') GROUP BY sector_type", uid)
    
    counts = {r['sector_type']: r['count'] for r in facilities}
    
    text = f"⛏ *مدیریت معادن و پالایشگاه‌ها {c['name']}*\n\n"
    text += f"🧠 تکنسین آزاد: {c.get('technicians', 0):,}\n"
    text += f"👷 کارگر آزاد: {c.get('workers', 0):,}\n"
    text += f"⚡️ برق آزاد: {c.get('power', 0):,}\n\n"
    
    rows = []
    for key, data in RESOURCE_FACILITIES.items():
        current_count = counts.get(key, 0)
        if current_count < data['max_limit']:
            rows.append([InlineKeyboardButton(f"➕ {data['name']} (هزینه: {fmt_money(data['cost'])})", callback_data=f"facility_build_{key}")])
        else:
            rows.append([InlineKeyboardButton(f"🚫 {data['name']} (سقف پر شده)", callback_data="facility_maxed")])
            
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=kb(rows))

async def order_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    c = await get_country(uid)
    
    if not c or c["status"] != "active":
        await update.message.reply_text("⚠️ شما مجاز به ثبت دستور نیستید.")
        return
        
    if not context.args:
        await update.message.reply_text("⚠️ دستور خود را بعد از کامند بنویسید.\nمثال: `/order حمله به کشور روم`")
        return
        
    order_text = " ".join(context.args)
    temp[uid] = {"order_text": order_text, "step": "ORDER_CATEGORY"}
    
    rows = [
        [InlineKeyboardButton("💰 اقتصادی", callback_data="cat_economic")],
        [InlineKeyboardButton("🏛️ سیاسی", callback_data="cat_political")],
        [InlineKeyboardButton("⚔️ نظامی", callback_data="cat_military")]
    ]
    await update.message.reply_text("دستور شما در کدام دسته‌بندی قرار می‌گیرد؟", reply_markup=kb(rows))

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text.strip()
    t = temp.get(uid, {})

    if t.get("step") == "NAME":
        t["name"] = text
        t["step"] = "LEADER"
        temp[uid] = t
        await update.message.reply_text("👤 نام رهبر کشور را وارد کنید:")
        
    elif t.get("step") == "LEADER":
        t["leader"] = text
        t["step"] = "GOV_MAIN"
        temp[uid] = t
        
        rows = [[InlineKeyboardButton(v["name"], callback_data=f"gov_{k}")] for k, v in GOVERNMENTS.items()]
        await update.message.reply_text("⚙️ نوع نظام حکومتی خود را انتخاب کنید:", reply_markup=kb(rows))

    elif t.get("step") == "ADMIN_EDIT_ORDER" and uid == ADMIN_ID:
        order_id = t["order_id"]
        async with pool.acquire() as conn:
            await conn.execute("UPDATE orders SET order_text = $1 WHERE id = $2", text, order_id)
        temp.pop(uid, None)
        await update.message.reply_text("✅ دستور ویرایش شد. در حال تحلیل با هوش مصنوعی...")
        await analyze_and_send_to_admin(update, context, order_id)
        
    elif t.get("step") == "CITY_NAME_NEW":
        if len(text) < 3:
            await update.message.reply_text("❌ نام شهر باید حداقل ۳ حرف باشد.")
            return
        async with pool.acquire() as conn:
            await conn.execute("UPDATE countries SET treasury = treasury - 5000 WHERE user_id = $1", uid)
            await conn.execute("INSERT INTO cities (user_id, name) VALUES ($1, $2)", uid, text)
        temp.pop(uid, None)
        await update.message.reply_text(f"✅ شهر «{text}» تاسیس شد و ۵ میلیون دلار کسر شد.")

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cb = update.callback_query
    data = cb.data
    uid = cb.from_user.id
    c = await get_country(uid)
    t = temp.get(uid, {})
    await cb.answer()

    if data.startswith("gov_"):
        main_gov = data.replace("gov_", "")
        t["gov_main"] = main_gov
        t["step"] = "GOV_SUB"
        temp[uid] = t
        
        subs = GOVERNMENTS[main_gov]["subs"]
        rows = [[InlineKeyboardButton(v, callback_data=f"subgov_{k}")] for k, v in subs.items()]
        await cb.edit_message_text("زیرشاخه حکومت را انتخاب کنید:", reply_markup=kb(rows))
        
    elif data.startswith("subgov_"):
        sub_gov = data.replace("subgov_", "")
        t["gov_sub"] = sub_gov
        temp.pop(uid, None)
        
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO countries (user_id, username, name, leader, gov_main, gov_sub, status) VALUES ($1, $2, $3, $4, $5, $6, 'pending')",
                uid, cb.from_user.username, t["name"], t["leader"], t["gov_main"], sub_gov
            )
            
        await cb.edit_message_text("⏳ درخواست ثبت کشور شما ارسال شد. منتظر تایید ادمین باشید.")
        
        gov_name = GOVERNMENTS[t['gov_main']]['name'] + " - " + GOVERNMENTS[t['gov_main']]['subs'][sub_gov]
        admin_text = f"📥 **درخواست ثبت کشور جدید**\n\n🏛️ {t['name']}\n👤 رهبر: {t['leader']}\n⚙️ حکومت: {gov_name}\n🆔 `{uid}`"
        admin_btn = kb([[InlineKeyboardButton("✅ تایید", callback_data=f"adm_ok_{uid}"), InlineKeyboardButton("❌ رد", callback_data=f"adm_rej_{uid}")]])
        await context.bot.send_message(ADMIN_ID, admin_text, parse_mode="Markdown", reply_markup=admin_btn)

    elif data.startswith("adm_ok_"):
        target_uid = int(data.split("_")[2])
        async with pool.acquire() as conn:
            await conn.execute("UPDATE countries SET status = 'active' WHERE user_id = $1", target_uid)
        await cb.edit_message_text("✅ کشور تایید شد.")
        await context.bot.send_message(target_uid, "🎉 کشور شما تایید شد! از این پس می‌توانید با /order دستور ثبت کنید.")

    elif data.startswith("adm_rej_"):
        target_uid = int(data.split("_")[2])
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM countries WHERE user_id = $1", target_uid)
        await cb.edit_message_text("❌ درخواست رد شد.")
        await context.bot.send_message(target_uid, "❌ درخواست ثبت کشور شما رد شد.")

    elif data == "city_new":
        if c['treasury'] < 5000:
            await cb.answer("❌ خزانه کافی نیست! نیاز: ۵ میلیون دلار", show_alert=True)
            return
        temp[uid] = {"step": "CITY_NAME_NEW"}
        await cb.edit_message_text("🏙️ لطفاً نام شهر جدید خود را وارد کنید:")

    elif data == "tax_up":
        new_rate = min(50, c.get('tax_rate', 10) + 5)
        async with pool.acquire() as conn:
            await conn.execute("UPDATE countries SET tax_rate = $1 WHERE user_id = $2", new_rate, uid)
        await cb.answer(f"✅ نرخ مالیات به {new_rate}٪ افزایش یافت.", show_alert=True)
        await economy_cmd(update, context)

    elif data == "tax_down":
        new_rate = max(0, c.get('tax_rate', 10) - 5)
        async with pool.acquire() as conn:
            await conn.execute("UPDATE countries SET tax_rate = $1 WHERE user_id = $2", new_rate, uid)
        await cb.answer(f"✅ نرخ مالیات به {new_rate}٪ کاهش یافت.", show_alert=True)
        await economy_cmd(update, context)

    elif data.startswith("region_"):
        if c['treasury'] < 10000:
            await cb.answer("❌ خزانه کافی نیست! نیاز: ۱۰ میلیون دلار", show_alert=True)
            return
        async with pool.acquire() as conn:
            await conn.execute("UPDATE countries SET treasury = treasury - 10000, gdp = gdp + 50000 WHERE user_id = $1", uid)
        await cb.answer("✅ منطقه تاسیس شد و به GDP اضافه شد.", show_alert=True)

    elif data.startswith("infra_build_"):
        sector = data.replace("infra_build_", "")
        req = INDUSTRIES[sector]
        
        if c['treasury'] < req['cost']:
            await cb.answer("❌ خزانه کافی نیست!", show_alert=True)
            return
            
        if c.get('workers', 0) < req['build_workers']:
            await cb.answer(f"❌ کارگر ساخت‌وساز کافی نیست!\nنیاز: {req['build_workers']:,} کارگر", show_alert=True)
            return
            
        if c.get('technicians', 0) < req['tech'] or c.get('workers', 0) < (req['build_workers'] + req['workers']) or c.get('power', 0) < req['power']:
            await cb.answer(f"❌ منابع عملیاتی کافی نیست!\nنیاز به {req['tech']} تکنسین، {req['workers']} کارگر و {req['power']} برق دارید.", show_alert=True)
            return

        async with pool.acquire() as conn:
            await conn.execute("""UPDATE countries SET 
                treasury = treasury - $1, 
                technicians = technicians - $2, 
                workers = workers - $3, 
                power = power - $4,
                gdp = gdp + $5
                WHERE user_id = $6""", 
                req['cost'], req['tech'], req['workers'], req['power'], req['income'] * 10, uid)
                
            await conn.execute("INSERT INTO infrastructure (user_id, sector_type, name, income) VALUES ($1, $2, $3, $4)", uid, sector, req['name'], req['income'])
            
        await cb.answer("✅ صنعت ساخته شد!", show_alert=True)
        await infra_cmd(update, context)

    elif data == "infra_maxed":
        await cb.answer("❌ شما به سقف مجاز این صنعت رسیده‌اید!", show_alert=True)

    elif data.startswith("facility_build_"):
        sector = data.replace("facility_build_", "")
        req = RESOURCE_FACILITIES[sector]
        
        if c['treasury'] < req['cost']:
            await cb.answer("❌ خزانه کافی نیست!", show_alert=True)
            return
            
        if c.get('workers', 0) < req['build_workers']:
            await cb.answer(f"❌ کارگر ساخت‌وساز کافی نیست!\nنیاز: {req['build_workers']:,} کارگر", show_alert=True)
            return
            
        if c.get('technicians', 0) < req['tech'] or c.get('workers', 0) < (req['build_workers'] + req['workers']) or c.get('power', 0) < req['power']:
            await cb.answer(f"❌ منابع عملیاتی کافی نیست!\nنیاز به {req['tech']} تکنسین، {req['workers']} کارگر و {req['power']} برق دارید.", show_alert=True)
            return

        async with pool.acquire() as conn:
            await conn.execute("""UPDATE countries SET 
                treasury = treasury - $1, 
                technicians = technicians - $2, 
                workers = workers - $3, 
                power = power - $4,
                gdp = gdp + $5
                WHERE user_id = $6""", 
                req['cost'], req['tech'], req['workers'], req['power'], req['income'] * 10, uid)
                
            await conn.execute("INSERT INTO infrastructure (user_id, sector_type, name, income) VALUES ($1, $2, $3, $4)", uid, sector, req['name'], req['income'])
            
        await cb.answer("✅ تاسیسات ساخته شد!", show_alert=True)
        await mines_cmd(update, context)

    elif data == "facility_maxed":
        await cb.answer("❌ شما به سقف مجاز این تاسیسات رسیده‌اید!", show_alert=True)

    elif data.startswith("cat_"):
        category = data.replace("cat_", "")
        order_text = t.get("order_text")
        temp.pop(uid, None)
        
        async with pool.acquire() as conn:
            order_id = await conn.fetchval(
                "INSERT INTO orders (user_id, order_text, category) VALUES ($1, $2, $3) RETURNING id",
                uid, order_text, category
            )
            
        cat_fa = {"economic": "اقتصادی", "political": "سیاسی", "military": "نظامی"}.get(category, category)
        
        admin_text = (
            f"📜 **دستور جدید از {c['name']}**\n\n"
            f"🗂 دسته: {cat_fa}\n"
            f"📝 متن دستور: {order_text}\n\n"
            f"آیا با تحلیل این دستور موافقید؟"
        )
        admin_btn = kb([
            [InlineKeyboardButton("✅ تایید و تحلیل", callback_data=f"ord_appr_{order_id}")],
            [InlineKeyboardButton("✏️ ویرایش دستور", callback_data=f"ord_edit_{order_id}")],
            [InlineKeyboardButton("❌ رد دستور", callback_data=f"ord_rej_{order_id}")]
        ])
        await context.bot.send_message(ADMIN_ID, admin_text, parse_mode="Markdown", reply_markup=admin_btn)
        await cb.edit_message_text("⏳ دستور شما به ادمین ارسال شد.")

    elif data.startswith("ord_appr_"):
        order_id = int(data.split("_")[2])
        await cb.edit_message_text("⏳ در حال تحلیل...")
        await analyze_and_send_to_admin(cb, context, order_id)

    elif data.startswith("ord_edit_"):
        order_id = int(data.split("_")[2])
        temp[uid] = {"step": "ADMIN_EDIT_ORDER", "order_id": order_id}
        await cb.edit_message_text("✏️ لطفاً متن اصلاح‌شده دستور را ارسال کنید:")

    elif data.startswith("ord_rej_"):
        order_id = int(data.split("_")[2])
        async with pool.acquire() as conn:
            await conn.execute("UPDATE orders SET status = 'rejected' WHERE id = $1", order_id)
        await cb.edit_message_text("❌ دستور رد شد.")

    elif data.startswith("pub_"):
        order_id = int(data.split("_")[2])
        order = await get_order(order_id)
        ai_data = json.loads(order["ai_analysis_raw"])
        narrative = ai_data.get("narrative", "اتفاقی افتاد.")
        
        final_text = f"📢 **بیانیه رسمی**\n\n{narrative}"
        
        if CHANNEL_ID:
            try:
                await context.bot.send_message(CHANNEL_ID, final_text, parse_mode="Markdown")
                await cb.edit_message_text("✅ در کانال منتشر شد.")
            except Exception as e:
                await cb.edit_message_text(f"❌ خطا در ارسال به کانال: {e}")
        else:
            await cb.edit_message_text("⚠️ آیدی کانال تنظیم نشده است.")
            
        async with pool.acquire() as conn:
            await conn.execute("UPDATE orders SET status = 'published' WHERE id = $1", order_id)

async def analyze_and_send_to_admin(update_or_cb, context, order_id):
    ai_data = await analyze_and_apply_order(order_id, context)
    
    if ai_data.get("success"):
        status_icon = "✅ موفقیت‌آمیز"
    else:
        status_icon = "❌ ناموفق"
        
    text = (
        f"🧠 **نتیجه تحلیل هوش مصنوعی**\n\n"
        f"📌 وضعیت: {status_icon}\n"
        f"📝 تحلیل: {ai_data.get('reason', 'دلیلی ذکر نشد')}\n\n"
        f"📖 **انتشار برای کانال:**\n"
        f"{ai_data.get('narrative', '')}\n\n"
        f" تایید می‌شود؟"
    )
    
    btn = kb([
        [InlineKeyboardButton("📢 انتشار در کانال", callback_data=f"pub_{order_id}")],
        [InlineKeyboardButton("❌ لغو", callback_data="cancel_pub")]
    ])
    
    if hasattr(update_or_cb, "message"):
        await update_or_cb.message.reply_text(text, parse_mode="Markdown", reply_markup=btn)
    else:
        await update_or_cb.edit_message_text(text, parse_mode="Markdown", reply_markup=btn)

async def post_init(app):
    await init_db()
    await set_commands(app)
    await app.bot.delete_webhook(drop_pending_updates=True)

def main():
    app = Application.builder().token(TOKEN).post_init(post_init).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CommandHandler("country", country_cmd))
    app.add_handler(CommandHandler("order", order_cmd))
    app.add_handler(CommandHandler("cities", cities_cmd))
    app.add_handler(CommandHandler("economy", economy_cmd))
    app.add_handler(CommandHandler("regions", regions_cmd))
    app.add_handler(CommandHandler("infra", infra_cmd))
    app.add_handler(CommandHandler("mines", mines_cmd))
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(CommandHandler("turn", turn_cmd))
    
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
