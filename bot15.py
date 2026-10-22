import os
import json
import ast
import re
import asyncio
import logging
import asyncpg
import httpx
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

GOVERNMENTS = {
    "communist": {"name": "☭ کمونیستی", "subs": {"marxist": "مارکسیسم-لنینیسم", "stalinist": "استالینیسم", "maoist": "مائوئیسم", "trotskyist": "تروتسکیسم", "titoist": "تیتوئیسم", "castrist": "کاستروئیسم", "council": "کمونیسم شورایی"}},
    "dictator": {"name": "✊ دیکتاتوری", "subs": {"military": "دیکتاتوری نظامی", "personal": "دیکتاتوری فردی", "party": "دیکتاتوری حزبی", "oligarchy": "الیگارشی", "technocracy": "تکنوکراسی"}},
    "democracy": {"name": "🗳️ دموکراسی", "subs": {"parliamentary": "پارلمانی", "presidential": "ریاستی", "semi_presidential": "نیمه‌ریاستی", "federal": "فدرال", "direct": "مستقیم", "social_democracy": "سوسیال دموکراسی"}},
    "monarchy": {"name": "👑 سلطنتی", "subs": {"absolute": "مطلقه", "constitutional": "مشروطه", "federal": "فدرال", "elective": "انتخابی", "empire": "امپراتوری"}},
    "republic": {"name": "🏛️ جمهوری", "subs": {"secular": "سکولار", "islamic": "اسلامی", "theocratic": "تئوکراتیک", "socialist": "سوسیالیستی", "federal_rep": "فدرال", "liberal": "لیبرال"}},
    "religious": {"name": "🕌 دینی", "subs": {"shia_theo": "تئوکراسی شیعه", "suni_theo": "تئوکراتیک سنی", "caliphate": "خلافتی", "velayat": "ولایت فقیه", "confucian": "کنفوسیوسی", "buddhist": "بودایی"}}
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
                gdp BIGINT DEFAULT 500000000,
                army INT DEFAULT 10000,
                satisfaction INT DEFAULT 50,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        try:
            await conn.execute("ALTER TABLE countries ADD COLUMN satisfaction INT DEFAULT 50")
        except asyncpg.exceptions.DuplicateColumnError:
            pass
            
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

def fmt_money(dollars):
    try:
        d = int(dollars)
    except (TypeError, ValueError):
        return "0 دلار"
    if d >= 1_000_000_000:
        return f"${d / 1_000_000_000:.2f} میلیارد دلار"
    if d >= 1_000_000:
        return f"${d / 1_000_000:.1f} میلیون دلار"
    if d >= 1_000:
        return f"${d / 1_000:.0f} هزار دلار"
    return f"${d:,.0f} دلار"

def _safe_parse_json(raw) -> dict:
    if isinstance(raw, dict): return raw
    if not raw or not isinstance(raw, str): return {}
    start, end = raw.find('{'), raw.rfind('}')
    if start == -1 or end == -1: return {}
    s = raw[start:end + 1].replace("```json", "").replace("```", "").strip()
    try: return json.loads(s)
    except json.JSONDecodeError: pass
    try: return ast.literal_eval(s)
    except Exception: pass
    try: return ast.literal_eval(s.replace("true", "True").replace("false", "False").replace("null", "None"))
    except Exception: pass
    try: return json.loads(re.sub(r'(?<!\\)\n', r'\\n', s))
    except Exception: pass
    return {}

def _clean_persian_text(text: str) -> str:
    if not isinstance(text, str): return ""
    cleaned = re.sub(r'[^\u0600-\u06FF0-9\s\.\,\!\?\:\-\؛\(\)\[\]\«\»\n]', '', text)
    return cleaned.strip()

async def ask_ai(prompt: str, system_prompt: str = "You are a game master API. Output raw JSON only.") -> str:
    url = f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/ai/run/@cf/meta/llama-3.3-70b-instruct-fp8-fast"
    headers = {"Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}],
        "max_tokens": 1500,
        "temperature": 0.7
    }

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
                    return fallback("محدودیت روزانه", "سهمیه روزانه AI تمام شده.")
                if response.status_code != 200:
                    if attempt == 0: 
                        await asyncio.sleep(3)
                        continue
                    return fallback(f"خطای سرویس ({response.status_code})", "سرویس در دسترس نیست.")
                res_data = response.json()
                if res_data.get("success"):
                    resp = res_data["result"]["response"]
                    if isinstance(resp, dict): return json.dumps(resp, ensure_ascii=False)
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
            logger.error(f"AI Exception: {type(e).__name__}: {e}")
            if attempt == 0: 
                await asyncio.sleep(2)
                continue
            return fallback("خطای شبکه", "ارتباط برقرار نشد.")

def _build_prompt(country: dict, order_text: str, category: str) -> str:
    military_budget = int(country['gdp'] * 0.07)
    
    if category == "political":
        narrative_rule = "The narrative MUST be a highly dramatic, grandiloquent political speech."
    elif category == "military":
        narrative_rule = "The narrative MUST be an epic war report."
    else:
        narrative_rule = "The narrative MUST be a dramatic economic news report."

    return f"""You are the strict Game Master of a grand strategy game.
Analyze the order and write TWO Persian narratives (short & long).

COUNTRY:
- Name: {country['name']}
- GDP: ${country['gdp']:,} (Use EXACT DOLLARS, e.g., 500000000)
- Military Budget (7% GDP): ${military_budget:,}
- Army: {country['army']}
- Satisfaction: {country.get('satisfaction', 50)}%

ORDER CATEGORY: {category}
ORDER: "{order_text}"

ECONOMY RULES (DO NOT IGNORE):
1. The wealth is the GDP in EXACT US DOLLARS. Do not use "thousands". A $500 Million GDP is written as 500000000.
2. Military actions cost from the Military Budget. Economic actions cost from the overall GDP.
3. If cost > available funds, "success" MUST be false.

STRICT RULES:
1. Output MUST be valid JSON.
2. "narrative_short": A 1-sentence breaking news flash in Persian (max 150 chars). No newlines.
3. "narrative_long": A detailed, epic, cinematic report in Persian (max 800 chars). No newlines.
4. Use ONLY Persian alphabet. No English/Chinese/Russian letters.
5. If failed, describe the tragic failure in both narratives.

EXACT JSON FORMAT:
{{
  "success": true/false,
  "reason": "Strict Persian reason (max 100 chars)",
  "gdp_change": integer (e.g., -5000000),
  "army_change": integer,
  "satisfaction_change": integer (-10 to +10),
  "narrative_short": "Persian short news...",
  "narrative_long": "Persian epic report..."
}}
"""

async def analyze_and_apply_order(order_id: int, context):
    try:
        return await asyncio.wait_for(_analyze_inner(order_id), timeout=120.0)
    except asyncio.TimeoutError:
        data = {"success": False, "reason": "پردازش طول کشید", "narrative_short": "بررسی به تعویق افتاد.", "narrative_long": "بررسی به تعویق افتاد."}
        async with pool.acquire() as conn:
            await conn.execute("UPDATE orders SET status='ai_analyzed', ai_analysis_raw=$1 WHERE id=$2", json.dumps(data, ensure_ascii=False), order_id)
        return data

async def _analyze_inner(order_id: int):
    order = await get_order(order_id)
    if not order: return {"success": False, "reason": "سفارش یافت نشد", "narrative_short": "", "narrative_long": ""}
    country = await get_country(order["user_id"])
    if not country: return {"success": False, "reason": "کشور یافت نشد", "narrative_short": "", "narrative_long": ""}

    prompt = _build_prompt(country, order["order_text"], order["category"])
    sys_prompt = "You are a strict JSON-only API. Use ONLY Persian characters. Output raw JSON."
    
    ai_response = await ask_ai(prompt, system_prompt=sys_prompt)
    data = _safe_parse_json(ai_response)

    if "success" not in data or "narrative_long" not in data:
        data = {"success": False, "reason": "پاسخ نامعتبر بود", "narrative_short": "خطای تحلیل", "narrative_long": "نیاز به بررسی دستی دارد.", "gdp_change": 0, "army_change": 0, "satisfaction_change": 0}

    if "narrative_short" in data: data["narrative_short"] = _clean_persian_text(str(data["narrative_short"]))
    if "narrative_long" in data: data["narrative_long"] = _clean_persian_text(str(data["narrative_long"]))
    if "reason" in data: data["reason"] = _clean_persian_text(str(data["reason"]))

    if data.get("success"):
        try:
            g_change = int(data.get("gdp_change") or 0)
            a_change = int(data.get("army_change") or 0)
            s_change = int(data.get("satisfaction_change") or 0)
        except (TypeError, ValueError):
            data = {"success": False, "reason": "خطای عددی", "narrative_short": "", "narrative_long": "", "gdp_change": 0, "army_change": 0, "satisfaction_change": 0}
        else:
            if country["gdp"] + g_change < 0:
                data = {
                    "success": False, 
                    "reason": f"ورشکستگی! هزینه ${abs(g_change):,} > GDP ${country['gdp']:,}", 
                    "gdp_change": 0, "army_change": 0, "satisfaction_change": -5, 
                    "narrative_short": "اقتصاد کشور فروپاشید.",
                    "narrative_long": f"با خالی شدن خزانه ملی، طرح پیشنهادی دولت {country['name']} با شکست سختی مواجه شد."
                }
            else:
                new_sat = max(0, min(100, country.get("satisfaction", 50) + s_change))
                data["satisfaction_change"] = new_sat - country.get("satisfaction", 50)
                
                async with pool.acquire() as conn:
                    await conn.execute(
                        "UPDATE countries SET gdp = GREATEST(0, gdp + $1), army = army + $2, satisfaction = $3 WHERE user_id = $4", 
                        g_change, a_change, new_sat, order["user_id"]
                    )

    async with pool.acquire() as conn:
        await conn.execute("UPDATE orders SET status='ai_analyzed', ai_analysis_raw=$1 WHERE id=$2", json.dumps(data, ensure_ascii=False), order_id)
    return data

temp = {}

async def set_commands(app):
    await app.bot.set_my_commands([
        BotCommand("start", "ثبت‌نام"), 
        BotCommand("country", "اطلاعات کشور"), 
        BotCommand("order", "دستور جدید"), 
        BotCommand("admin", "پنل مدیریت (ادمین)"),
        BotCommand("cancel", "لغو")
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    c = await get_country(uid)
    if c:
        if c["status"] == "active": await update.message.reply_text(f"✅ کشور {c['name']} فعال است. /order")
        elif c["status"] == "pending": await update.message.reply_text("⏳ در انتظار تایید ادمین.")
        return
    temp[uid] = {"step": "NAME"}
    await update.message.reply_text("🏛️ Welcome to rustabad RP\n\nلطفاً **نام کشور** خود را وارد کنید:", parse_mode="Markdown")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    temp.pop(update.effective_user.id, None)
    await update.message.reply_text("❌ لغو شد.")

async def country_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    c = await get_country(update.effective_user.id)
    if not c or c["status"] != "active": return await update.message.reply_text("⚠️ ثبت‌نام کنید. /start")
    gmn = GOVERNMENTS.get(c["gov_main"], {}).get("name", "")
    gsn = GOVERNMENTS.get(c["gov_main"], {}).get("subs", {}).get(c["gov_sub"], "")
    sat = c.get("satisfaction", 50)
    mil = int(c['gdp'] * 0.07)
    
    await update.message.reply_text(
        f"🏛️ *کشور: {c['name']}*\n"
        f"👤 رهبر: {c['leader']}\n"
        f"⚙️ حکومت: {gmn} - {gsn}\n\n"
        f"📈 GDP (ثروت ملی): {fmt_money(c['gdp'])}\n"
        f"🛡 بودجه نظامی (۷٪): {fmt_money(mil)}\n"
        f"🎖 ارتش: {c['army']:,} نفر\n"
        f"❤️ رضایت عمومی: {sat}%", 
        parse_mode="Markdown"
    )

async def order_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    c = await get_country(uid)
    if not c or c["status"] != "active": return await update.message.reply_text("⚠️ مجاز نیستید.")
    if not context.args: return await update.message.reply_text("⚠️ دستور را بنویسید. مثال: `/order سرمایه‌گذاری ۱۰ میلیون دلاری`")
    
    temp[uid] = {"order_text": " ".join(context.args), "step": "ORDER_CATEGORY"}
    await update.message.reply_text("دسته‌بندی؟", reply_markup=kb([
        [InlineKeyboardButton("💰 اقتصادی", callback_data="cat_economic")], 
        [InlineKeyboardButton("🏛️ سیاسی", callback_data="cat_political")], 
        [InlineKeyboardButton("⚔️ نظامی", callback_data="cat_military")]
    ]))

async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    await update.message.reply_text("🛠 **پنل ادمین**\nیک گزینه را انتخاب کنید:", reply_markup=kb([
        [InlineKeyboardButton("📊 لیست کشورها", callback_data="adm_list")],
        [InlineKeyboardButton("🔄 رد کردن نوبت", callback_data="adm_next_turn")],
        [InlineKeyboardButton("💰 تنظیم GDP", callback_data="adm_set_gdp")]
    ]), parse_mode="Markdown")

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text.strip()
    t = temp.get(uid, {})
    
    if t.get("step") == "NAME":
        t.update({"name": text, "step": "LEADER"})
        temp[uid] = t
        await update.message.reply_text("👤 نام رهبر:")
    elif t.get("step") == "LEADER":
        t.update({"leader": text, "step": "GOV_MAIN"})
        temp[uid] = t
        await update.message.reply_text("⚙️ نظام حکومتی:", reply_markup=kb([[InlineKeyboardButton(v["name"], callback_data=f"gov_{k}")] for k, v in GOVERNMENTS.items()]))
    elif t.get("step") == "ADMIN_EDIT_ORDER" and uid == ADMIN_ID:
        async with pool.acquire() as conn: await conn.execute("UPDATE orders SET order_text = $1 WHERE id = $2", text, t["order_id"])
        temp.pop(uid, None); await update.message.reply_text("✅ ویرایش شد."); await analyze_and_send_to_admin(update, context, t["order_id"])
    elif t.get("step") == "ADMIN_SET_GDP" and uid == ADMIN_ID:
        try:
            amount = int(text.replace(",", "").replace(".", ""))
            async with pool.acquire() as conn: await conn.execute("UPDATE countries SET gdp = $1 WHERE user_id = $2", amount, t["target_id"])
            temp.pop(uid, None)
            await update.message.reply_text(f"✅ GDP با موفقیت روی {fmt_money(amount)} تنظیم شد.")
        except ValueError:
            await update.message.reply_text("❌ لطفاً فقط عدد وارد کنید (مثلاً 500000000).")

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cb = update.callback_query
    data = cb.data
    uid = cb.from_user.id
    t = temp.get(uid, {})
    await cb.answer()
    
    if data.startswith("gov_"):
        t.update({"gov_main": data.replace("gov_", ""), "step": "GOV_SUB"})
        temp[uid] = t
        await cb.edit_message_text("زیرشاخه:", reply_markup=kb([[InlineKeyboardButton(v, callback_data=f"subgov_{k}")] for k, v in GOVERNMENTS[t["gov_main"]]["subs"].items()]))
    elif data.startswith("subgov_"):
        t["gov_sub"] = data.replace("subgov_", "")
        temp.pop(uid, None)
        async with pool.acquire() as conn:
            await conn.execute("INSERT INTO countries (user_id, username, name, leader, gov_main, gov_sub, status) VALUES ($1, $2, $3, $4, $5, $6, 'pending')", uid, cb.from_user.username, t["name"], t["leader"], t["gov_main"], t["gov_sub"])
        await cb.edit_message_text("⏳ در انتظار تایید.")
        ad_text = f"📥 **درخواست جدید**\n\n🏛️ {t['name']}\n👤 {t['leader']}\n🆔 `{uid}`"
        await context.bot.send_message(ADMIN_ID, ad_text, parse_mode="Markdown", reply_markup=kb([[InlineKeyboardButton("✅ تایید", callback_data=f"adm_ok_{uid}"), InlineKeyboardButton("❌ رد", callback_data=f"adm_rej_{uid}")]]))
    elif data.startswith("adm_ok_"):
        target = int(data.split("_")[2])
        async with pool.acquire() as conn: await conn.execute("UPDATE countries SET status = 'active' WHERE user_id = $1", target)
        await cb.edit_message_text("✅ تایید شد.")
        await context.bot.send_message(target, "🎉 کشور شما تایید شد! /order")
    elif data.startswith("adm_rej_"):
        target = int(data.split("_")[2])
        async with pool.acquire() as conn: await conn.execute("DELETE FROM countries WHERE user_id = $1", target)
        await cb.edit_message_text("❌ رد شد.")
        await context.bot.send_message(target, "❌ درخواست رد شد.")
        
    # بخش‌های پنل ادمین
    elif data == "adm_list":
        async with pool.acquire() as conn:
            countries = await conn.fetch("SELECT * FROM countries WHERE status = 'active'")
        if not countries: return await cb.edit_message_text("هیچ کشوری وجود ندارد.")
        txt = "📊 **لیست کشورها:**\n\n"
        for c in countries:
            txt += f"🏛️ {c['name']} | GDP: {fmt_money(c['gdp'])} | 🆔 `{c['user_id']}`\n"
        await cb.edit_message_text(txt, parse_mode="Markdown", reply_markup=kb([[InlineKeyboardButton("🔙 بازگشت", callback_data="adm_back")]]))
        
    elif data == "adm_next_turn":
        await cb.edit_message_text("⏳ در حال رد کردن نوبت...")
        await next_turn_cmd(cb.message, context)
        
    elif data == "adm_set_gdp":
        await cb.edit_message_text("🆔 آیدی عددی کاربر (User ID) را وارد کنید:")
        temp[uid] = {"step": "ADMIN_SET_GDP_ID"}
        
    elif data == "adm_back":
        await cb.edit_message_text("🛠 **پنل ادمین**", reply_markup=kb([
            [InlineKeyboardButton("📊 لیست کشورها", callback_data="adm_list")],
            [InlineKeyboardButton("🔄 رد کردن نوبت", callback_data="adm_next_turn")],
            [InlineKeyboardButton("💰 تنظیم GDP", callback_data="adm_set_gdp")]
        ]), parse_mode="Markdown")

    elif data.startswith("cat_"):
        ot = t.get("order_text")
        temp.pop(uid, None)
        if not ot: return await cb.edit_message_text("⚠️ منقضی شده. /order")
        async with pool.acquire() as conn: oid = await conn.fetchval("INSERT INTO orders (user_id, order_text, category) VALUES ($1, $2, $3) RETURNING id", uid, ot, data.replace("cat_", ""))
        c = await get_country(uid)
        await context.bot.send_message(ADMIN_ID, f"📜 **دستور جدید از {c['name']}**\n📝 {ot}", parse_mode="Markdown", reply_markup=kb([[InlineKeyboardButton("✅ تایید", callback_data=f"ord_appr_{oid}")], [InlineKeyboardButton("✏️ ویرایش", callback_data=f"ord_edit_{oid}")], [InlineKeyboardButton("❌ رد", callback_data=f"ord_rej_{oid}")]]))
        await cb.edit_message_text("⏳ ارسال به ادمین.")
        
    elif data.startswith("ord_appr_"):
        oid = int(data.split("_")[2]); await cb.edit_message_text("⏳ تحلیل..."); await analyze_and_send_to_admin(cb, context, oid)
    elif data.startswith("ord_edit_"):
        temp[uid] = {"step": "ADMIN_EDIT_ORDER", "order_id": int(data.split("_")[2])}; await cb.edit_message_text("✏️ متن جدید:")
    elif data.startswith("ord_rej_"):
        oid = int(data.split("_")[2]); async with pool.acquire() as conn: await conn.execute("UPDATE orders SET status = 'rejected' WHERE id = $1", oid)
        await cb.edit_message_text("❌ رد شد.")
        
    # بخش‌های انتشار (خلاصه یا کامل)
    elif data.startswith("pub_short_") or data.startswith("pub_long_"):
        is_short = "pub_short_" in data
        oid = int(data.split("_")[2])
        await cb.answer("در حال ارسال...")
        order = await get_order(oid)
        try: ai_data = json.loads(order["ai_analysis_raw"] or "{}")
        except: ai_data = {}
        
        text_to_send = ai_data.get('narrative_short', '') if is_short else ai_data.get('narrative_long', '')
        final_text = f"📢 بیانیه رسمی\n\n{text_to_send}"
        
        if CHANNEL_ID:
            try:
                await context.bot.send_message(int(CHANNEL_ID.strip()), final_text)
                async with pool.acquire() as conn: await conn.execute("UPDATE orders SET status = 'published', published_at = NOW() WHERE id = $1", oid)
                await cb.edit_message_text("✅ با موفقیت در کانال منتشر شد.")
            except Exception as e:
                await cb.edit_message_text(f"❌ خطا: {e}")
        else:
            await cb.edit_message_text("⚠️ آیدی کانال تنظیم نشده.")
            
    elif data == "pub_economy_report":
        await cb.answer("در حال ارسال...")
        report_text = cb.message.text
        if CHANNEL_ID:
            try:
                await context.bot.send_message(int(CHANNEL_ID.strip()), report_text)
                await cb.edit_message_text(report_text + "\n\n✅ منتشر شد.")
            except Exception as e:
                await cb.edit_message_text(report_text + f"\n\n❌ خطا: {e}")
        else:
            await cb.edit_message_text(report_text + "\n\n⚠️ آیدی کانال تنظیم نشده.")
    elif data == "cancel_pub": 
        await cb.edit_message_text("❌ لغو شد.")

async def analyze_and_send_to_admin(update_or_cb, context, order_id):
    ai_data = await analyze_and_apply_order(order_id, context)
    st = "✅ موفق" if ai_data.get("success") else "❌ ناموفق"
    ch = f"\n📈 GDP: {ai_data.get('gdp_change',0):+,} $ | 🎖 ارتش: {ai_data.get('army_change',0):+,} | ❤️ رضایت: {ai_data.get('satisfaction_change',0):+,}\n" if ai_data.get("success") else ""
    
    txt = f"🧠 تحلیل (70B)\n\n📌 وضعیت: {st}\n📝 دلیل: {ai_data.get('reason', '')}\n{ch}\n📰 **خلاصه خبری:**\n{ai_data.get('narrative_short', '')}\n\n📖 **گزارش کامل:**\n{ai_data.get('narrative_long', '')}"
    
    btn = kb([
        [InlineKeyboardButton("📢 انتشار خلاصه", callback_data=f"pub_short_{order_id}"), InlineKeyboardButton("📜 انتشار کامل", callback_data=f"pub_long_{order_id}")],
        [InlineKeyboardButton("❌ لغو", callback_data="cancel_pub")]
    ])
    
    if isinstance(update_or_cb, CallbackQuery):
        try: await update_or_cb.edit_message_text(txt, reply_markup=btn); return
        except: pass
    await context.bot.send_message(update_or_cb.from_user.id, txt, reply_markup=btn)

def _build_economy_prompt(country: dict) -> str:
    return f"""You are the Economic Engine of a grand strategy game.
Calculate the income and growth for the next turn for this country.

COUNTRY:
- Name: {country['name']}
- GDP: ${country['gdp']:,}
- Army: {country['army']}

INSTRUCTIONS:
1. GDP usually grows by 2% to 5% per turn. Output exact dollars.
2. Write a short, epic "narrative" in Persian (max 300 chars). NO literal newlines.
3. Output strictly valid JSON.

EXACT JSON FORMAT:
{{
  "gdp_change": integer (exact dollars),
  "narrative": "Persian economic news here"
}}
"""

async def next_turn_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # اگر از پنل ادمین صدا زده شده، آپدیت یک CallbackQuery است
    is_cb = isinstance(update, CallbackQuery)
    if (is_cb and update.from_user.id != ADMIN_ID) or (not is_cb and update.effective_user.id != ADMIN_ID):
        return
        
    msg = await context.bot.send_message(ADMIN_ID, "⏳ در حال محاسبه اقتصاد...")
    
    async with pool.acquire() as conn: countries = await conn.fetch("SELECT * FROM countries WHERE status = 'active'")
    if not countries: return await msg.edit_text("⚠️ هیچ کشوری وجود ندارد.")
    
    report_lines = []
    for row in countries:
        country = dict(row)
        prompt = _build_economy_prompt(country)
        ai_res = await ask_ai(prompt, system_prompt="Economic API. JSON only.")
        data = _safe_parse_json(ai_res)
        
        try:
            g_change = int(data.get("gdp_change", 0))
            narrative = _clean_persian_text(data.get("narrative", "اقتصاد عادی."))
        except: g_change, narrative = 0, "خطا."
            
        max_growth = int(country['gdp'] * 0.05)
        if g_change > max_growth: g_change = max_growth
        if g_change < 0: g_change = 0
        
        async with pool.acquire() as conn: await conn.execute("UPDATE countries SET gdp = gdp + $1 WHERE user_id = $2", g_change, country["user_id"])
        report_lines.append(f"🏛️ {country['name']}:\n📈 +${g_change:,}\n📰 {narrative}\n")
    
    final_report = "📊 **گزارش پایان نوبت**\n\n" + "\n".join(report_lines)
    btn = kb([[InlineKeyboardButton("📢 انتشار گزارش", callback_data="pub_economy_report")]])
    if len(final_report) > 4000: await msg.edit_text("✅ اقتصاد آپدیت شد (متن طولانی).")
    else: await msg.edit_text(final_report, reply_markup=btn)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(f"Update {update} caused error {context.error}")

async def post_init(app):
    await init_db(); await set_commands(app); await app.bot.delete_webhook(drop_pending_updates=True)

def main():
    app = Application.builder().token(TOKEN).post_init(post_init).build()
    app.add_error_handler(error_handler)
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CommandHandler("country", country_cmd))
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
