import os
import json
import asyncio
import logging
import asyncpg
import httpx
import random
import datetime
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
                prospect_oil_count INT DEFAULT 0,
                prospect_mine_count INT DEFAULT 0,
                last_prospect TIMESTAMP DEFAULT NULL,
                created_at TIMESTAMP DEFAULT NOW()
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
        
        await conn.execute("ALTER TABLE countries ADD COLUMN IF NOT EXISTS technicians BIGINT DEFAULT 1000")
        await conn.execute("ALTER TABLE countries ADD COLUMN IF NOT EXISTS workers BIGINT DEFAULT 10000")
        await conn.execute("ALTER TABLE countries ADD COLUMN IF NOT EXISTS power BIGINT DEFAULT 5000")
        await conn.execute("ALTER TABLE countries ADD COLUMN IF NOT EXISTS tax_rate INT DEFAULT 10")
        await conn.execute("ALTER TABLE countries ADD COLUMN IF NOT EXISTS prospect_oil_count INT DEFAULT 0")
        await conn.execute("ALTER TABLE countries ADD COLUMN IF NOT EXISTS prospect_mine_count INT DEFAULT 0")
        await conn.execute("ALTER TABLE countries ADD COLUMN IF NOT EXISTS last_prospect TIMESTAMP DEFAULT NULL")
        
    logger.info("Database initialized.")

async def get_country(uid):
    async with pool.acquire() as conn:
        r = await conn.fetchrow("SELECT * FROM countries WHERE user_id = $1", uid)
        return dict(r) if r else None

def kb(rows):
    return InlineKeyboardMarkup(rows)

def fmt_money(amount):
    return f"{amount:,.0f} دلار" if amount < 1000000 else f"{amount/1000000:.1f} میلیون دلار"

# ---------- AI SETUP (For War) ----------
async def ask_ai(prompt: str, system_prompt: str = "You are a game master API.") -> str:
    url = f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/ai/run/@cf/meta/llama-3.3-70b-instruct-fp8-fast"
    headers = {"Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}", "Content-Type": "application/json"}
    payload = {"messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}], "max_tokens": 512}
    
    for attempt in range(3):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, json=payload, timeout=120.0)
                if response.status_code == 200:
                    res_data = response.json()
                    if res_data.get("success"):
                        return res_data["result"]["response"]
                await asyncio.sleep(2)
        except Exception:
            await asyncio.sleep(2)
            
    return ""

# ---------- COMMANDS ----------

async def set_commands(app):
    cmds = [
        BotCommand("start", "ثبت‌نام و شروع بازی"),
        BotCommand("country", "مشاهده اطلاعات کشور"),
        BotCommand("cities", "مدیریت شهرها"),
        BotCommand("economy", "مدیریت اقتصادی و مالیات"),
        BotCommand("regions", "مدیریت مناطق"),
        BotCommand("infra", "مدیریت صنایع"),
        BotCommand("mines", "مدیریت معادن و پالایشگاه‌ها"),
        BotCommand("prospect", "سیستم استخراج"),
        BotCommand("war", "اعلام جنگ و حمله"),
        BotCommand("admin", "پنل مدیریت (ادمین)"),
        BotCommand("turn", "پردازش درآمد نوبت (ادمین)"),
        BotCommand("cancel", "لغو عملیات")
    ]
    await app.bot.set_my_commands(cmds)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    c = await get_country(uid)
    
    if c:
        if c["status"] == "active":
            await context.bot.send_message(uid, f"✅ کشور {c['name']} فعال است.")
        elif c["status"] == "banned":
            await context.bot.send_message(uid, "🚫 شما مسدود شده‌اید.")
        elif c["status"] == "pending":
            await context.bot.send_message(uid, "⏳ ثبت‌نام شما در انتظار تایید ادمین است.")
        return

    temp[uid] = {"step": "NAME"}
    await context.bot.send_message(uid, "🏛️ Welcome to rustabad RP\n\nلطفاً **نام کشور** خود را وارد کنید:", parse_mode="Markdown")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    temp.pop(update.effective_user.id, None)
    await context.bot.send_message(update.effective_user.id, "❌ عملیات لغو شد.")

async def country_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    c = await get_country(uid)
    if not c or c["status"] != "active":
        await context.bot.send_message(uid, "⚠️ ابتدا باید ثبت‌نام کنید.")
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
    await context.bot.send_message(uid, text, parse_mode="Markdown")

async def cities_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    c = await get_country(uid)
    if not c or c["status"] != "active": return
    
    async with pool.acquire() as conn:
        cities = await conn.fetch("SELECT * FROM cities WHERE user_id = $1", uid)
        
    text = f"🏙️ *مدیریت شهرها*\n\nتعداد شهرهای شما: {len(cities)}\n\n"
    if cities:
        for city in cities: text += f"🔹 {city['name']}\n"
    
    rows = []
    if len(cities) < 5:
        rows.append([InlineKeyboardButton("➕ تاسیس شهر (۵ میلیون دلار)", callback_data="city_new")])
    await context.bot.send_message(uid, text, parse_mode="Markdown", reply_markup=kb(rows))

async def economy_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    c = await get_country(uid)
    if not c or c["status"] != "active": return
        
    text = (
        f"💰 *وزارت اقتصاد {c['name']}*\n\n"
        f"📈 GDP: {fmt_money(c['gdp'])}\n"
        f"🏦 خزانه: {fmt_money(c['treasury'])}\n"
        f"📊 نرخ مالیات: {c.get('tax_rate', 10)}٪\n"
        f"درآمد مالیاتی هر نوبت: {fmt_money((c['gdp'] * c.get('tax_rate', 10)) // 100)}\n\n"
        f"⚠️ _مالیات بالا درآمد را زیاد می‌کند اما رضایت مردم را کاهش می‌دهد._"
    )
    rows = [[InlineKeyboardButton("📉 کاهش (۵-)", callback_data="tax_down"), InlineKeyboardButton("📈 افزایش (۵+)", callback_data="tax_up")]]
    await context.bot.send_message(uid, text, parse_mode="Markdown", reply_markup=kb(rows))

async def regions_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    c = await get_country(uid)
    if not c or c["status"] != "active": return
        
    text = (
        f"🗺️ *مدیریت مناطق {c['name']}*\n\n"
        f"هزینه تاسیس هر منطقه: ۱۰ میلیون دلار\n\n"
        f"🔹 *صنعتی*: افزایش ۵۰,۰۰۰ دلاری GDP\n"
        f"🔹 *کشاورزی*: افزایش ۵۰,۰۰۰ دلاری GDP"
    )
    rows = [[InlineKeyboardButton("🏭 منطقه صنعتی", callback_data="region_industrial")], [InlineKeyboardButton("🌾 منطقه کشاورزی", callback_data="region_agricultural")]]
    await context.bot.send_message(uid, text, parse_mode="Markdown", reply_markup=kb(rows))

async def infra_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    c = await get_country(uid)
    if not c or c["status"] != "active": return
        
    async with pool.acquire() as conn:
        infras = await conn.fetch("SELECT sector_type, count(*) as count FROM infrastructure WHERE user_id = $1 GROUP BY sector_type", uid)
    counts = {r['sector_type']: r['count'] for r in infras}
    
    text = f"🏭 *مدیریت صنایع {c['name']}*\n\n🧠 تکنسین: {c.get('technicians', 0):,}\n👷 کارگر: {c.get('workers', 0):,}\n⚡️ برق: {c.get('power', 0):,}\n\n"
    
    rows = []
    for key, data in INDUSTRIES.items():
        if counts.get(key, 0) < data['max_limit']:
            rows.append([InlineKeyboardButton(f"➕ {data['name']} ({fmt_money(data['cost'])})", callback_data=f"infra_build_{key}")])
        else:
            rows.append([InlineKeyboardButton(f"🚫 {data['name']} (تکمیل)", callback_data="infra_maxed")])
    await context.bot.send_message(uid, text, parse_mode="Markdown", reply_markup=kb(rows))

async def mines_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    c = await get_country(uid)
    if not c or c["status"] != "active": return
        
    async with pool.acquire() as conn:
        facilities = await conn.fetch("SELECT sector_type, count(*) as count FROM infrastructure WHERE user_id = $1 AND (sector_type LIKE 'mine_%' OR sector_type LIKE 'ref_%') GROUP BY sector_type", uid)
    counts = {r['sector_type']: r['count'] for r in facilities}
    
    text = f"⛏ *معادن و پالایشگاه‌ها {c['name']}*\n\n🧠 تکنسین: {c.get('technicians', 0):,}\n👷 کارگر: {c.get('workers', 0):,}\n⚡️ برق: {c.get('power', 0):,}\n\n"
    
    rows = []
    for key, data in RESOURCE_FACILITIES.items():
        if counts.get(key, 0) < data['max_limit']:
            rows.append([InlineKeyboardButton(f"➕ {data['name']} ({fmt_money(data['cost'])})", callback_data=f"facility_build_{key}")])
        else:
            rows.append([InlineKeyboardButton(f"🚫 {data['name']} (تکمیل)", callback_data="facility_maxed")])
    await context.bot.send_message(uid, text, parse_mode="Markdown", reply_markup=kb(rows))

async def prospect_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    c = await get_country(uid)
    if not c or c["status"] != "active": return
    
    text = "⛏ *سیستم استخراج*\n\nهزینه: ۱.۵ میلیون دلار\nشانس موفقیت کاهش می‌یابد.\n\nیک گزینه را انتخاب کنید:"
    rows = [[InlineKeyboardButton("🛢 استخراج نفت", callback_data="prospect_oil")], [InlineKeyboardButton("⛏ استخراج معدن", callback_data="prospect_mine")]]
    await context.bot.send_message(uid, text, parse_mode="Markdown", reply_markup=kb(rows))

async def war_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    c = await get_country(uid)
    if not c or c["status"] != "active": return

    async with pool.acquire() as conn:
        enemies = await conn.fetch("SELECT user_id, name, army FROM countries WHERE user_id != $1 AND status = 'active'", uid)
        
    if not enemies:
        await context.bot.send_message(uid, "⚠️ در حال حاضر هیچ کشور دیگری در بازی وجود ندارد.")
        return

    text = "⚔️ *وزارت دفاع - اتاق جنگ*\n\nکشور مورد نظر برای حمله را انتخاب کنید:\n\n"
    rows = []
    for enemy in enemies:
        text += f"🔹 {enemy['name']} (ارتش: {enemy['army']:,})\n"
        rows.append([InlineKeyboardButton(f"حمله به {enemy['name']}", callback_data=f"war_target_{enemy['user_id']}")])
        
    await context.bot.send_message(uid, text, parse_mode="Markdown", reply_markup=kb(rows))

async def turn_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    async with pool.acquire() as conn:
        incomes = await conn.fetch("SELECT user_id, SUM(income) as total_income FROM infrastructure GROUP BY user_id")
        text = "⏳ *پردازش درآمد...*\n\n"
        for row in incomes:
            if row['total_income'] > 0:
                await conn.execute("UPDATE countries SET treasury = treasury + $1 WHERE user_id = $2", row['total_income'], row['user_id'])
                country = await get_country(row['user_id'])
                if country: text += f"✅ {country['name']}: +{fmt_money(row['total_income'])}\n"
    await context.bot.send_message(update.effective_user.id, text, parse_mode="Markdown")

# --- ADMIN PANEL ---
async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    await admin_panel(update.effective_user.id, None, context)

async def admin_panel(chat_id, msg_id, context, page=0):
    async with pool.acquire() as conn:
        countries = await conn.fetch("SELECT * FROM countries ORDER BY created_at DESC")
    
    per_page = 5
    start = page * per_page
    end = start + per_page
    page_countries = countries[start:end]
    
    text = f"👑 *پنل مدیریت (صفحه {page+1})*\n\n"
    buttons = []
    for c in page_countries:
        status_icon = "✅" if c['status'] == 'active' else "🚫" if c['status'] == 'banned' else "⏳"
        buttons.append([InlineKeyboardButton(f"{status_icon} {c['name']} (ID: {c['user_id']})", callback_data=f"adm_manage_{c['user_id']}")])
    
    nav = []
    if page > 0: nav.append(InlineKeyboardButton("⬅️", callback_data=f"adm_page_{page-1}"))
    if end < len(countries): nav.append(InlineKeyboardButton("➡️", callback_data=f"adm_page_{page+1}"))
    if nav: buttons.append(nav)
    buttons.append([InlineKeyboardButton("🔙 بستن", callback_data="adm_close")])
    
    if msg_id:
        try: await context.bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=text, parse_mode="Markdown", reply_markup=kb(buttons))
        except: pass
    else:
        await context.bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=kb(buttons))

# ---------- HANDLERS ----------

temp = {}

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text.strip()
    t = temp.get(uid, {})

    if t.get("step") == "NAME":
        t["name"] = text; t["step"] = "LEADER"; temp[uid] = t
        await context.bot.send_message(uid, "👤 نام رهبر کشور را وارد کنید:")
        
    elif t.get("step") == "LEADER":
        t["leader"] = text; t["step"] = "GOV_MAIN"; temp[uid] = t
        rows = [[InlineKeyboardButton(v["name"], callback_data=f"gov_{k}")] for k, v in GOVERNMENTS.items()]
        await context.bot.send_message(uid, "⚙️ نوع نظام حکومتی خود را انتخاب کنید:", reply_markup=kb(rows))

    elif t.get("step") == "CITY_NAME_NEW":
        async with pool.acquire() as conn:
            await conn.execute("UPDATE countries SET treasury = treasury - 5000 WHERE user_id = $1", uid)
            await conn.execute("INSERT INTO cities (user_id, name) VALUES ($1, $2)", uid, text)
        temp.pop(uid, None)
        await context.bot.send_message(uid, f"✅ شهر «{text}» تاسیس شد و ۵ میلیون دلار کسر شد.")

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cb = update.callback_query
    data = cb.data
    uid = cb.from_user.id
    c = await get_country(uid)
    t = temp.get(uid, {})
    await cb.answer()

    if data.startswith("gov_"):
        main_gov = data.replace("gov_", "")
        t["gov_main"] = main_gov; t["step"] = "GOV_SUB"; temp[uid] = t
        subs = GOVERNMENTS[main_gov]["subs"]
        rows = [[InlineKeyboardButton(v, callback_data=f"subgov_{k}")] for k, v in subs.items()]
        await cb.edit_message_text("زیرشاخه حکومت را انتخاب کنید:", reply_markup=kb(rows))
        
    elif data.startswith("subgov_"):
        sub_gov = data.replace("subgov_", "")
        t["gov_sub"] = sub_gov; temp.pop(uid, None)
        async with pool.acquire() as conn:
            await conn.execute("INSERT INTO countries (user_id, username, name, leader, gov_main, gov_sub, status) VALUES ($1, $2, $3, $4, $5, $6, 'pending')", uid, cb.from_user.username, t["name"], t["leader"], t["gov_main"], sub_gov)
        await cb.edit_message_text("⏳ درخواست ارسال شد. منتظر تایید باشید.")
        gov_name = GOVERNMENTS[t['gov_main']]['name'] + " - " + GOVERNMENTS[t['gov_main']]['subs'][sub_gov]
        admin_btn = kb([[InlineKeyboardButton("✅ تایید", callback_data=f"adm_ok_{uid}"), InlineKeyboardButton("❌ رد", callback_data=f"adm_rej_{uid}")]])
        await context.bot.send_message(ADMIN_ID, f"📥 **ثبت‌نام جدید**\n\n🏛️ {t['name']}\n👤 {t['leader']}\n⚙️ {gov_name}\n🆔 `{uid}`", parse_mode="Markdown", reply_markup=admin_btn)

    elif data.startswith("adm_ok_"):
        target_uid = int(data.split("_")[2])
        async with pool.acquire() as conn: await conn.execute("UPDATE countries SET status = 'active' WHERE user_id = $1", target_uid)
        await cb.edit_message_text("✅ تایید شد.")
        await context.bot.send_message(target_uid, "🎉 کشور شما تایید شد!")

    elif data.startswith("adm_rej_"):
        target_uid = int(data.split("_")[2])
        async with pool.acquire() as conn: await conn.execute("DELETE FROM countries WHERE user_id = $1", target_uid)
        await cb.edit_message_text("❌ رد شد.")
        await context.bot.send_message(target_uid, "❌ درخواست شما رد شد.")

    # --- War Mechanics (Without AI Prompt for now) ---
    elif data.startswith("war_target_"):
        target_uid = int(data.split("_")[2])
        async with pool.acquire() as conn:
            enemy = await conn.fetchrow("SELECT * FROM countries WHERE user_id = $1", target_uid)
            
        if not enemy:
            await cb.answer("❌ این کشور وجود ندارد.", show_alert=True)
            return
            
        await cb.edit_message_text(f"⚔️ **اعلام جنگ!**\n\nشما به کشور {enemy['name']} حمله کردید.\nدر حال تحلیل نتیجه نبرد...")
        
        # TODO: Put your AI Prompt here in the future. For now, simple python logic.
        if c['army'] > enemy['army']:
            # Attacker wins
            loot_treasury = int(enemy['treasury'] * 0.2)
            killed_army = int(enemy['army'] * 0.2)
            async with pool.acquire() as conn:
                await conn.execute("UPDATE countries SET treasury = treasury + $1 WHERE user_id = $2", loot_treasury, uid)
                await conn.execute("UPDATE countries SET treasury = treasury - $1, army = army - $2 WHERE user_id = $3", loot_treasury, killed_army, target_uid)
            await context.bot.send_message(uid, f"🏆 **پیروزی!**\n\nشما در حمله به {enemy['name']} پیروز شدید.\n💰 غرامت: {fmt_money(loot_treasury)}\n🩸 تلفات دشمن: {killed_army:,} سرباز")
            try: await context.bot.send_message(target_uid, f"🚨 **شکست در دفاع!**\n\nکشور {c['name']} به شما حمله کرد و پیروز شد.\n💰 خزانه از دست رفته: {fmt_money(loot_treasury)}\n🩸 تلفات: {killed_army:,} سرباز")
            except: pass
        else:
            # Defender wins
            lost_army = int(c['army'] * 0.2)
            async with pool.acquire() as conn:
                await conn.execute("UPDATE countries SET army = army - $1 WHERE user_id = $2", lost_army, uid)
                await conn.execute("UPDATE countries SET treasury = treasury + $1 WHERE user_id = $2", int(c['treasury']*0.1), target_uid)
            await context.bot.send_message(uid, f"❌ **شکست!**\n\nحمله شما به {enemy['name']} دفع شد.\n🩸 تلفات شما: {lost_army:,} سرباز")
            try: await context.bot.send_message(target_uid, f"🛡️ **دفاع موفق!**\n\nشما حمله {c['name']} را دفع کردید.")
            except: pass

    # --- Admin Panel Actions ---
    elif data.startswith("adm_page_"):
        page = int(data.split("_")[2])
        await admin_panel(uid, cb.message.message_id, context, page)
        
    elif data == "adm_close":
        await cb.message.delete()

    elif data.startswith("adm_manage_"):
        target_id = int(data.split("_")[2])
        async with pool.acquire() as conn: target_c = await conn.fetchrow("SELECT * FROM countries WHERE user_id = $1", target_id)
        if not target_c: return
        text = f"👤 *کشور: {target_c['name']}*\nID: `{target_c['user_id']}`\nوضعیت: {target_c['status']}"
        buttons = [[InlineKeyboardButton("🚫 بن", callback_data=f"adm_ban_{target_id}")], [InlineKeyboardButton("✅ آنبن", callback_data=f"adm_unban_{target_id}")], [InlineKeyboardButton("🗑 حذف", callback_data=f"adm_del_{target_id}")], [InlineKeyboardButton("🔙 بازگشت", callback_data="adm_page_0")]]
        await cb.edit_message_text(text, parse_mode="Markdown", reply_markup=kb(buttons))

    elif data.startswith("adm_ban_"):
        target_id = int(data.split("_")[2])
        async with pool.acquire() as conn: await conn.execute("UPDATE countries SET status='banned' WHERE user_id=$1", target_id)
        await cb.answer("کاربر بن شد.")
        await admin_panel(uid, cb.message.message_id, context)

    elif data.startswith("adm_unban_"):
        target_id = int(data.split("_")[2])
        async with pool.acquire() as conn: await conn.execute("UPDATE countries SET status='active' WHERE user_id=$1", target_id)
        await cb.answer("کاربر آنبن شد.")
        await admin_panel(uid, cb.message.message_id, context)

    elif data.startswith("adm_del_"):
        target_id = int(data.split("_")[2])
        async with pool.acquire() as conn: await conn.execute("DELETE FROM countries WHERE user_id=$1", target_id)
        await cb.answer("کاربر حذف شد.")
        await admin_panel(uid, cb.message.message_id, context)

    # --- Economy / Regions / Infra ---
    elif data == "city_new":
        if c['treasury'] < 5000: await cb.answer("خزانه کافی نیست!", show_alert=True); return
        temp[uid] = {"step": "CITY_NAME_NEW"}
        await cb.edit_message_text("🏙️ نام شهر جدید:")

    elif data == "tax_up":
        new_rate = min(50, c.get('tax_rate', 10) + 5)
        async with pool.acquire() as conn: await conn.execute("UPDATE countries SET tax_rate = $1 WHERE user_id = $2", new_rate, uid)
        await cb.answer(f"نرخ مالیات: {new_rate}٪")
        await economy_cmd(update, context)

    elif data == "tax_down":
        new_rate = max(0, c.get('tax_rate', 10) - 5)
        async with pool.acquire() as conn: await conn.execute("UPDATE countries SET tax_rate = $1 WHERE user_id = $2", new_rate, uid)
        await cb.answer(f"نرخ مالیات: {new_rate}٪")
        await economy_cmd(update, context)

    elif data.startswith("region_"):
        if c['treasury'] < 10000: await cb.answer("خزانه کافی نیست!", show_alert=True); return
        async with pool.acquire() as conn: await conn.execute("UPDATE countries SET treasury = treasury - 10000, gdp = gdp + 50000 WHERE user_id = $1", uid)
        await cb.answer("✅ منطقه تاسیس شد.", show_alert=True)
        await regions_cmd(update, context)

    elif data.startswith("infra_build_"):
        sector = data.replace("infra_build_", "")
        req = INDUSTRIES[sector]
        if c['treasury'] < req['cost']: await cb.answer("خزانه کافی نیست!", show_alert=True); return
        if c.get('workers', 0) < req['build_workers']: await cb.answer("کارگر کافی نیست!", show_alert=True); return
        if c.get('technicians', 0) < req['tech'] or c.get('workers', 0) < (req['build_workers'] + req['workers']) or c.get('power', 0) < req['power']:
            await cb.answer("منابع عملیاتی کافی نیست!", show_alert=True); return
        async with pool.acquire() as conn:
            await conn.execute("UPDATE countries SET treasury = treasury - $1, technicians = technicians - $2, workers = workers - $3, power = power - $4, gdp = gdp + $5 WHERE user_id = $6", req['cost'], req['tech'], req['workers'], req['power'], req['income'] * 10, uid)
            await conn.execute("INSERT INTO infrastructure (user_id, sector_type, name, income) VALUES ($1, $2, $3, $4)", uid, sector, req['name'], req['income'])
        await cb.answer("✅ ساخته شد!", show_alert=True)
        await infra_cmd(update, context)

    elif data.startswith("facility_build_"):
        sector = data.replace("facility_build_", "")
        req = RESOURCE_FACILITIES[sector]
        if c['treasury'] < req['cost']: await cb.answer("خزانه کافی نیست!", show_alert=True); return
        if c.get('workers', 0) < req['build_workers']: await cb.answer("کارگر کافی نیست!", show_alert=True); return
        if c.get('technicians', 0) < req['tech'] or c.get('workers', 0) < (req['build_workers'] + req['workers']) or c.get('power', 0) < req['power']:
            await cb.answer("منابع عملیاتی کافی نیست!", show_alert=True); return
        async with pool.acquire() as conn:
            await conn.execute("UPDATE countries SET treasury = treasury - $1, technicians = technicians - $2, workers = workers - $3, power = power - $4, gdp = gdp + $5 WHERE user_id = $6", req['cost'], req['tech'], req['workers'], req['power'], req['income'] * 10, uid)
            await conn.execute("INSERT INTO infrastructure (user_id, sector_type, name, income) VALUES ($1, $2, $3, $4)", uid, sector, req['name'], req['income'])
        await cb.answer("✅ ساخته شد!", show_alert=True)
        await mines_cmd(update, context)

    # --- Prospect ---
    elif data.startswith("prospect_") and data != "prospect_cmd":
        p_type = data.replace("prospect_", "")
        if c.get('last_prospect'):
            now = datetime.datetime.now(datetime.timezone.utc)
            last = c['last_prospect'].replace(tzinfo=datetime.timezone.utc)
            diff = (now - last).total_seconds()
            if diff < 3600:
                await cb.answer(f"⏳ باید {int((3600-diff)//60)} دقیقه صبر کنید!", show_alert=True); return
        if c['treasury'] < 1500: await cb.answer("نیاز به ۱.۵ میلیون دلار!", show_alert=True); return
        async with pool.acquire() as conn: await conn.execute("UPDATE countries SET treasury = treasury - 1500, last_prospect = NOW() WHERE user_id = $1", uid)
        await cb.edit_message_text("⏳ تیم‌ها اعزام شدند. نتیجه تا ۱۵ دقیقه دیگر...")
        asyncio.create_task(resolve_prospect(context, uid, p_type, uid))

async def resolve_prospect(context, uid, p_type, chat_id):
    delay = random.randint(300, 900)
    await asyncio.sleep(delay)
    async with pool.acquire() as conn:
        c = await conn.fetchrow("SELECT * FROM countries WHERE user_id = $1", uid)
        count = c[f'prospect_{p_type}_count']
        chance = 0.50 - (count * 0.05) if count < 10 else max(0.000005, 0.05 * (0.5 ** (count - 9)))
        success = random.random() < chance
        
        if success:
            if p_type == "oil":
                amount = random.randint(5000, 15000)
                await conn.execute("UPDATE countries SET treasury = treasury + $1 WHERE user_id = $2", amount * 10, uid)
                msg = f"🛢 **کشف بزرگ نفتی!**\n💰 درآمد: {fmt_money(amount * 10)}"
            else:
                amount = random.randint(2000, 5000)
                await conn.execute("UPDATE countries SET treasury = treasury + $1 WHERE user_id = $2", amount * 20, uid)
                msg = f"⛏ **کشف معدن غنی!**\n💰 درآمد: {fmt_money(amount * 20)}"
        else:
            msg = f"❌ **عملیات ناموفق**\nتیم‌ها دست خالی برگشتند..."
            
        await conn.execute(f"UPDATE countries SET prospect_{p_type}_count = prospect_{p_type}_count + 1 WHERE user_id = $1", uid)
        
    try: await context.bot.send_message(chat_id, msg, parse_mode="Markdown")
    except: pass

async def post_init(app):
    await init_db()
    await set_commands(app)
    await app.bot.delete_webhook(drop_pending_updates=True)

def main():
    app = Application.builder().token(TOKEN).post_init(post_init).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CommandHandler("country", country_cmd))
    app.add_handler(CommandHandler("cities", cities_cmd))
    app.add_handler(CommandHandler("economy", economy_cmd))
    app.add_handler(CommandHandler("regions", regions_cmd))
    app.add_handler(CommandHandler("infra", infra_cmd))
    app.add_handler(CommandHandler("mines", mines_cmd))
    app.add_handler(CommandHandler("prospect", prospect_cmd))
    app.add_handler(CommandHandler("war", war_cmd))
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
