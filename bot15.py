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
                satisfaction INT DEFAULT 50,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        # اضافه کردن ستون رضایت در صورت وجود نداشتن (آپدیت ایمن)
        try:
            await conn.execute("ALTER TABLE countries ADD COLUMN satisfaction INT DEFAULT 50")
            logger.info("Added satisfaction column to countries table.")
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

def fmt_money(units):
    try:
        dollars = int(units) * 1000
    except (TypeError, ValueError):
        return "0 دلار"
    if dollars >= 1_000_000_000:
        return f"${dollars / 1_000_000_000:.2f} میلیارد دلار"
    if dollars >= 1_000_000:
        return f"${dollars / 1_000_000:.1f} میلیون دلار"
    if dollars >= 1_000:
        return f"${dollars / 1_000:.0f} هزار دلار"
    return f"${dollars:,.0f} دلار"

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
    logger.error(f"All JSON parsing layers failed for: {raw}")
    return {}

async def ask_ai(prompt: str, system_prompt: str = "You are a game master API. Output raw JSON only.") -> str:
    url = f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/ai/run/@cf/meta/llama-3.3-70b-instruct-fp8-fast"
    headers = {"Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}],
        "max_tokens": 1500,
        "temperature": 0.7 # افزایش خلاقیت برای نوشتن متن‌های حماسی
    }

    def fallback(reason, narrative):
        return json.dumps({"success": False, "reason": reason, "narrative": narrative}, ensure_ascii=False)

    for attempt in range(2):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, json=payload, timeout=90.0)
                logger.info(f"CF Status {response.status_code} (attempt {attempt+1})")
                if response.status_code == 429:
                    if attempt == 0: 
                        await asyncio.sleep(5)
                        continue
                    return fallback("محدودیت روزانه هوش مصنوعی", "سهمیه روزانه AI تمام شده. لطفاً بعداً تلاش کنید.")
                if response.status_code != 200:
                    logger.error(f"CF Error body: {response.text[:400]}")
                    if attempt == 0: 
                        await asyncio.sleep(3)
                        continue
                    return fallback(f"خطای سرویس ({response.status_code})", "سرویس هوش مصنوعی در دسترس نیست.")
                res_data = response.json()
                if res_data.get("success"):
                    resp = res_data["result"]["response"]
                    if isinstance(resp, dict): return json.dumps(resp, ensure_ascii=False)
                    return str(resp)
                else:
                    if attempt == 0: 
                        await asyncio.sleep(3)
                        continue
                    return fallback("مدل خطا داد", "مدل قادر به پاسخ‌دهی نبود.")
        except httpx.TimeoutException:
            if attempt == 0: 
                await asyncio.sleep(2)
                continue
            return fallback("پاسخ AI زمان زیادی طول کشید", "سرویس AI پاسخگو نبود.")
        except Exception as e:
            logger.error(f"AI Exception: {type(e).__name__}: {e}")
            if attempt == 0: 
                await asyncio.sleep(2)
                continue
            return fallback("خطای شبکه", "ارتباط با AI برقرار نشد.")

def _build_prompt(country: dict, order_text: str, category: str) -> str:
    if category == "political":
        narrative_rule = "The narrative MUST be a highly dramatic, grandiloquent (گنده‌گوزی) political speech or declaration to the world. It should sound arrogant, epic, and theatrical, like a dictator addressing a massive crowd."
    elif category == "military":
        narrative_rule = "The narrative MUST be an epic war report. Describe the marching armies, the thunder of boots, or the devastating failure on the battlefield with dramatic tension."
    else:
        narrative_rule = "The narrative MUST be a dramatic economic news report. If successful, describe the golden age and prosperity. If failed, describe the despair of the people and the empty national treasury."

    return f"""You are the Epic Game Master and narrator of a grand strategy roleplaying game.
Your task is to analyze the player's order, calculate the impact, and write a cinematic narrative (in Persian).

COUNTRY INFO:
- Name: {country['name']}
- Treasury: {country['treasury']} units (1 unit = $1,000)
- GDP: {country['gdp']} units
- Army: {country['army']} soldiers

ORDER CATEGORY: {category}
PLAYER ORDER: "{order_text}"

STRICT RULES (YOU WILL BE TERMINATED IF YOU BREAK THESE):
1. CALCULATION: 1 unit = $1,000. Example: $5,000,000 costs 5,000 units.
2. LOGIC: If cost > treasury, success MUST be false. All changes MUST be 0.
3. NARRATIVE STYLE: {narrative_rule}
4. FAILURE NARRATIVE: If success is false, the narrative MUST explicitly describe the failure, the lack of funds, or the rejection by the government/people. Do NOT write contradictory sentences (e.g., never say "rejected due to sufficient funds").
5. LANGUAGE: Use ONLY Persian (Farsi) alphabet. Do NOT use English, Chinese, Arabic, or any other characters.
6. FORMATTING: NO literal newlines (\\n) inside the narrative string. NO quotation marks inside the string.
7. OUTPUT: Valid JSON only.

EXACT JSON FORMAT:
{{
  "success": true or false,
  "reason": "A strict, logical Persian explanation of WHY it succeeded or failed (max 100 chars).",
  "treasury_change": integer,
  "army_change": integer,
  "gdp_change": integer,
  "satisfaction_change": integer (between -10 and +10),
  "narrative": "The epic, cinematic Persian text (max 800 chars)."
}}
"""

async def analyze_and_apply_order(order_id: int, context):
    try:
        return await asyncio.wait_for(_analyze_inner(order_id), timeout=120.0)
    except asyncio.TimeoutError:
        data = {"success": False, "reason": "پردازش طول کشید", "narrative": "ستاد فرماندهی اعلام کرد بررسی به تعویق افتاد."}
        async with pool.acquire() as conn:
            await conn.execute("UPDATE orders SET status='ai_analyzed', ai_analysis_raw=$1 WHERE id=$2", json.dumps(data, ensure_ascii=False), order_id)
        return data

async def _analyze_inner(order_id: int):
    order = await get_order(order_id)
    if not order: return {"success": False, "reason": "سفارش یافت نشد", "narrative": ""}
    country = await get_country(order["user_id"])
    if not country: return {"success": False, "reason": "کشور یافت نشد", "narrative": ""}

    prompt = _build_prompt(country, order["order_text"], order["category"])
    sys_prompt = "You are a strict JSON-only API. You speak only Persian in your responses. Never use foreign characters. Never break JSON format. Do not include markdown fences like ```json."
    
    ai_response = await ask_ai(prompt, system_prompt=sys_prompt)
    logger.info(f"AI RAW for order {order_id}:\n{ai_response}")

    data = _safe_parse_json(ai_response)

    if "success" not in data or "narrative" not in data:
        data = {"success": False, "reason": "پاسخ نامعتبر بود", "narrative": "دستور ثبت شد اما نیاز به بررسی دستی دارد.", "treasury_change": 0, "army_change": 0, "gdp_change": 0, "satisfaction_change": 0}

    if data.get("success"):
        try:
            t_change = int(data.get("treasury_change") or 0)
            a_change = int(data.get("army_change") or 0)
            g_change = int(data.get("gdp_change") or 0)
            s_change = int(data.get("satisfaction_change") or 0)
        except (TypeError, ValueError):
            data = {"success": False, "reason": "خطای عددی", "narrative": "", "treasury_change": 0, "army_change": 0, "gdp_change": 0, "satisfaction_change": 0}
        else:
            if country["treasury"] + t_change < 0:
                data = {"success": False, "reason": f"کمبود بودجه: {abs(t_change):,} > {country['treasury']:,}", "treasury_change": 0, "army_change": 0, "gdp_change": 0, "satisfaction_change": 0, "narrative": f"دولت {country['name']} اعلام کرد بودجه کافی نیست."}
            elif country["army"] + a_change < 0:
                data = {"success": False, "reason": "نیرو کم است", "treasury_change": 0, "army_change": 0, "gdp_change": 0, "satisfaction_change": 0, "narrative": "فرماندهی ارتش مخالفت کرد."}
            else:
                new_satisfaction = country.get("satisfaction", 50) + s_change
                new_satisfaction = max(0, min(100, new_satisfaction))
                data["satisfaction_change"] = new_satisfaction - country.get("satisfaction", 50)
                
                async with pool.acquire() as conn:
                    row = await conn.fetchrow(
                        "UPDATE countries SET treasury = treasury + $1, army = army + $2, gdp = GREATEST(1000, gdp + $3), satisfaction = $4 WHERE user_id = $5 AND treasury + $1 >= 0 AND army + $2 >= 0 RETURNING treasury", 
                        t_change, a_change, g_change, new_satisfaction, order["user_id"]
                    )
                    if not row:
                        data = {"success": False, "reason": "تغییر هم‌زمان", "narrative": "", "satisfaction_change": 0}

    async with pool.acquire() as conn:
        await conn.execute("UPDATE orders SET status='ai_analyzed', ai_analysis_raw=$1 WHERE id=$2", json.dumps(data, ensure_ascii=False), order_id)
    return data

temp = {}

async def set_commands(app):
    await app.bot.set_my_commands([
        BotCommand("start", "ثبت‌نام"), 
        BotCommand("country", "اطلاعات کشور"), 
        BotCommand("order", "دستور جدید"), 
        BotCommand("next_turn", "پایان نوبت (ادمین)"),
        BotCommand("cancel", "لغو")
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    c = await get_country(uid)
    if c:
        if c["status"] == "active": 
            await update.message.reply_text(f"✅ کشور {c['name']} فعال است. /order")
        elif c["status"] == "pending": 
            await update.message.reply_text("⏳ در انتظار تایید ادمین.")
        return
    temp[uid] = {"step": "NAME"}
    await update.message.reply_text("🏛️ Welcome to rustabad RP\n\nلطفاً **نام کشور** خود را وارد کنید:", parse_mode="Markdown")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    temp.pop(update.effective_user.id, None)
    await update.message.reply_text("❌ عملیات لغو شد.")

async def country_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    c = await get_country(update.effective_user.id)
    if not c or c["status"] != "active": 
        return await update.message.reply_text("⚠️ ابتدا ثبت‌نام کنید. /start")
    gmn = GOVERNMENTS.get(c["gov_main"], {}).get("name", "")
    gsn = GOVERNMENTS.get(c["gov_main"], {}).get("subs", {}).get(c["gov_sub"], "")
    sat = c.get("satisfaction", 50)
    
    await update.message.reply_text(
        f"🏛️ *کشور: {c['name']}*\n"
        f"👤 رهبر: {c['leader']}\n"
        f"⚙️ حکومت: {gmn} - {gsn}\n\n"
        f"💰 خزانه: {fmt_money(c['treasury'])}\n"
        f"🎖 ارتش: {c['army']:,} نفر\n"
        f"📈 GDP: {fmt_money(c['gdp'])}\n"
        f"❤️ رضایت عمومی: {sat}%", 
        parse_mode="Markdown"
    )

async def order_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    c = await get_country(uid)
    if not c or c["status"] != "active": 
        return await update.message.reply_text("⚠️ شما مجاز نیستید.")
    if not context.args: 
        return await update.message.reply_text("⚠️ دستور را بنویسید. مثال: `/order سرمایه‌گذاری ۱۰ میلیون دلاری در نفت`")
    
    temp[uid] = {"order_text": " ".join(context.args), "step": "ORDER_CATEGORY"}
    await update.message.reply_text("دسته‌بندی؟", reply_markup=kb([
        [InlineKeyboardButton("💰 اقتصادی", callback_data="cat_economic")], 
        [InlineKeyboardButton("🏛️ سیاسی", callback_data="cat_political")], 
        [InlineKeyboardButton("⚔️ نظامی", callback_data="cat_military")]
    ]))

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
        async with pool.acquire() as conn:
            await conn.execute("UPDATE orders SET order_text = $1 WHERE id = $2", text, t["order_id"])
        temp.pop(uid, None)
        await update.message.reply_text("✅ ویرایش شد. تحلیل...")
        await analyze_and_send_to_admin(update, context, t["order_id"])

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
        await cb.edit_message_text("⏳ در انتظار تایید ادمین.")
        ad_text = f"📥 **درخواست جدید**\n\n🏛️ {t['name']}\n👤 {t['leader']}\n⚙️ {GOVERNMENTS[t['gov_main']]['name']} - {GOVERNMENTS[t['gov_main']]['subs'][t['gov_sub']]}\n🆔 `{uid}`"
        await context.bot.send_message(ADMIN_ID, ad_text, parse_mode="Markdown", reply_markup=kb([[InlineKeyboardButton("✅ تایید", callback_data=f"adm_ok_{uid}"), InlineKeyboardButton("❌ رد", callback_data=f"adm_rej_{uid}")]]))
        
    elif data.startswith("adm_ok_"):
        target = int(data.split("_")[2])
        async with pool.acquire() as conn:
            await conn.execute("UPDATE countries SET status = 'active' WHERE user_id = $1", target)
        await cb.edit_message_text("✅ تایید شد.")
        await context.bot.send_message(target, "🎉 کشور شما تایید شد! /order")
        
    elif data.startswith("adm_rej_"):
        target = int(data.split("_")[2])
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM countries WHERE user_id = $1", target)
        await cb.edit_message_text("❌ رد شد.")
        await context.bot.send_message(target, "❌ درخواست رد شد.")
        
    elif data.startswith("cat_"):
        ot = t.get("order_text")
        temp.pop(uid, None)
        if not ot: 
            return await cb.edit_message_text("⚠️ منقضی شده. /order")
        async with pool.acquire() as conn:
            oid = await conn.fetchval("INSERT INTO orders (user_id, order_text, category) VALUES ($1, $2, $3) RETURNING id", uid, ot, data.replace("cat_", ""))
        c = await get_country(uid)
        await context.bot.send_message(ADMIN_ID, f"📜 **دستور جدید از {c['name']}**\n📝 {ot}", parse_mode="Markdown", reply_markup=kb([
            [InlineKeyboardButton("✅ تایید", callback_data=f"ord_appr_{oid}")], 
            [InlineKeyboardButton("✏️ ویرایش", callback_data=f"ord_edit_{oid}")], 
            [InlineKeyboardButton("❌ رد", callback_data=f"ord_rej_{oid}")]
        ]))
        await cb.edit_message_text("⏳ ارسال به ادمین.")
        
    elif data.startswith("ord_appr_"):
        oid = int(data.split("_")[2])
        await cb.edit_message_text("⏳ تحلیل (70B)...")
        await analyze_and_send_to_admin(cb, context, oid)
        
    elif data.startswith("ord_edit_"):
        temp[uid] = {"step": "ADMIN_EDIT_ORDER", "order_id": int(data.split("_")[2])}
        await cb.edit_message_text("✏️ متن جدید:")
        
    elif data.startswith("ord_rej_"):
        oid = int(data.split("_")[2])
        async with pool.acquire() as conn:
            await conn.execute("UPDATE orders SET status = 'rejected' WHERE id = $1", oid)
        await cb.edit_message_text("❌ رد شد.")
        
    elif data.startswith("pub_"):
        oid = int(data.split("_")[2])
        await cb.answer("در حال ارسال...")
        order = await get_order(oid)
        try:
            ai_data = json.loads(order["ai_analysis_raw"] or "{}")
        except Exception:
            ai_data = {}
        narrative = ai_data.get('narrative', 'اتفاقی افتاد.')
        final_text = f"📢 بیانیه رسمی\n\n{narrative}"
        if CHANNEL_ID:
            try:
                await context.bot.send_message(CHANNEL_ID, final_text)
                async with pool.acquire() as conn:
                    await conn.execute("UPDATE orders SET status = 'published', published_at = NOW() WHERE id = $1", oid)
                await cb.edit_message_text("✅ با موفقیت در کانال منتشر شد.")
            except Exception as e:
                logger.error(f"Channel publish error: {e}")
                await cb.edit_message_text(f"❌ خطا در ارسال به کانال!\nدلیل تلگرام: {e}\n\n(چک کن ربات ادمین باشه و دسترسی ارسال پیام داشته باشه)")
        else:
            await cb.edit_message_text("⚠️ آیدی کانال (CHANNEL_ID) تنظیم نشده است.")
            
    elif data == "pub_economy_report":
        await cb.answer("در حال ارسال...")
        report_text = cb.message.text
        if CHANNEL_ID:
            try:
                await context.bot.send_message(CHANNEL_ID, report_text)
                await cb.edit_message_text(report_text + "\n\n✅ در کانال منتشر شد.")
            except Exception as e:
                logger.error(f"Channel publish error: {e}")
                await cb.edit_message_text(report_text + f"\n\n❌ خطا در ارسال: {e}")
        else:
            await cb.edit_message_text(report_text + "\n\n⚠️ آیدی کانال تنظیم نشده.")
            
    elif data == "cancel_pub": 
        await cb.edit_message_text("❌ لغو شد.")

async def analyze_and_send_to_admin(update_or_cb, context, order_id):
    ai_data = await analyze_and_apply_order(order_id, context)
    st = "✅ موفق" if ai_data.get("success") else "❌ ناموفق"
    ch = ""
    if ai_data.get("success"):
        ch = f"\n💰 خزانه: {ai_data.get('treasury_change',0):+,} | 🎖 ارتش: {ai_data.get('army_change',0):+,} | 📈 GDP: {ai_data.get('gdp_change',0):+,} | ❤️ رضایت: {ai_data.get('satisfaction_change',0):+,}\n"
        
    txt = f"🧠 نتیجه تحلیل (70B)\n\n📌 وضعیت: {st}\n📝 تحلیل: {ai_data.get('reason', '')}\n{ch}\n📖 پیش‌نمایش انتشار:\n{ai_data.get('narrative', '')}\n\nتایید می‌کنید؟"
    btn = kb([[InlineKeyboardButton("📢 انتشار", callback_data=f"pub_{order_id}")], [InlineKeyboardButton("❌ لغو", callback_data="cancel_pub")]])
    
    if isinstance(update_or_cb, CallbackQuery):
        try: 
            await update_or_cb.edit_message_text(txt, reply_markup=btn)
            return
        except: 
            pass
    await context.bot.send_message(update_or_cb.from_user.id, txt, reply_markup=btn)

def _build_economy_prompt(country: dict) -> str:
    return f"""You are the Economic Engine of a grand strategy game.
Calculate the income and growth for the next turn for this country.

COUNTRY INFO:
- Name: {country['name']}
- Treasury: {country['treasury']} units (1 unit = $1,000)
- GDP: {country['gdp']} units
- Army: {country['army']} soldiers

INSTRUCTIONS:
1. Treasury usually grows by 5% to 15% of the current GDP per turn (due to taxes, trade, etc.).
2. GDP can grow by 2% to 5% per turn.
3. Write a short, epic "narrative" in Persian (max 300 chars) about the country's economic prosperity and the new budget. NO literal newlines.
4. Output strictly valid JSON.

EXACT JSON FORMAT:
{{
  "treasury_change": integer (in units),
  "gdp_change": integer (in units),
  "narrative": "Persian economic news here"
}}
"""

async def next_turn_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid != ADMIN_ID:
        return await update.message.reply_text("⚠️ فقط ادمین می‌تواند نوبت را رد کند.")
    
    msg = await update.message.reply_text("⏳ در حال محاسبه اقتصاد جهانی و درآمد کشورها... (ممکن است کمی طول بکشد)")
    
    async with pool.acquire() as conn:
        countries = await conn.fetch("SELECT * FROM countries WHERE status = 'active'")
    
    if not countries:
        return await msg.edit_text("⚠️ هیچ کشور فعالی وجود ندارد.")
    
    report_lines = []
    
    for row in countries:
        country = dict(row)
        prompt = _build_economy_prompt(country)
        ai_res = await ask_ai(prompt, system_prompt="You are an economic API. Output JSON only.")
        data = _safe_parse_json(ai_res)
        
        try:
            t_change = int(data.get("treasury_change", 0))
            g_change = int(data.get("gdp_change", 0))
            narrative = data.get("narrative", "اقتصاد روند عادی خود را طی کرد.")
        except:
            t_change, g_change, narrative = 0, 0, "خطا در محاسبات اقتصادی."
            
        max_income = int(country['gdp'] * 0.2)
        if t_change > max_income: t_change = max_income
        if t_change < 0: t_change = 0
        
        max_gdp_growth = int(country['gdp'] * 0.1)
        if g_change > max_gdp_growth: g_change = max_gdp_growth
        
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE countries SET treasury = treasury + $1, gdp = gdp + $2 WHERE user_id = $3",
                t_change, g_change, country["user_id"]
            )
            
        report_lines.append(f"🏛️ {country['name']}:\n💰 +{t_change:,} واحد | 📈 +{g_change:,} واحد\n📰 {narrative}\n")
    
    final_report = "📊 **گزارش پایان نوبت و درآمد کشورها**\n\n" + "\n".join(report_lines)
    btn = kb([[InlineKeyboardButton("📢 انتشار گزارش در کانال", callback_data="pub_economy_report")]])
    
    if len(final_report) > 4000:
        await msg.edit_text("✅ اقتصاد آپدیت شد، اما متن گزارش طولانی است. لاگ‌ها را چک کنید.")
    else:
        await msg.edit_text(final_report, reply_markup=btn)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(f"Update {update} caused error {context.error}")

async def post_init(app):
    await init_db()
    await set_commands(app)
    await app.bot.delete_webhook(drop_pending_updates=True)

def main():
    app = Application.builder().token(TOKEN).post_init(post_init).build()
    app.add_error_handler(error_handler)
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CommandHandler("country", country_cmd))
    app.add_handler(CommandHandler("order", order_cmd))
    app.add_handler(CommandHandler("next_turn", next_turn_cmd))
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
