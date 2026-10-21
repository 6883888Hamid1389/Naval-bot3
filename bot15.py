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


# ============ DB ============

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
    logger.info("Database initialized.")


async def get_country(uid):
    async with pool.acquire() as conn:
        r = await conn.fetchrow("SELECT * FROM countries WHERE user_id = $1", uid)
        return dict(r) if r else None


async def get_order(order_id):
    async with pool.acquire() as conn:
        r = await conn.fetchrow("SELECT * FROM orders WHERE id = $1", order_id)
        return dict(r) if r else None


# ============ Utils ============

def kb(rows):
    return InlineKeyboardMarkup(rows)


def fmt_money(units):
    """units = thousands of dollars. 1 unit = $1000."""
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


def _safe_parse_json(raw: str) -> dict:
    """چندلایه پارسر مقاوم در برابر خروجی‌های ناقص AI."""
    if not raw:
        return {}
    start, end = raw.find('{'), raw.rfind('}')
    if start == -1 or end == -1:
        return {}
    s = raw[start:end + 1].replace("```json", "").replace("```", "").strip()

    # تلاش ۱: JSON استاندارد
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass

    # تلاش ۲: دیکشنری پایتون (سینگل کوت)
    try:
        return ast.literal_eval(s)
    except Exception:
        pass

    # تلاش ۳: JS-style booleans → Python
    try:
        return ast.literal_eval(
            s.replace("true", "True").replace("false", "False").replace("null", "None")
        )
    except Exception:
        pass

    # تلاش ۴: تعمیر newline خام داخل رشته‌ها
    try:
        fixed = re.sub(r'(?<!\\)\n', r'\\n', s)
        return json.loads(fixed)
    except Exception:
        pass

    return {}


# ============ AI ============

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
        "max_tokens": 1024,
        "temperature": 0.2
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


def _build_prompt(country: dict, order_text: str) -> str:
    return f"""You are the economic engine of a text-based strategy game. Output ONLY valid JSON, no markdown fences, no commentary.

COUNTRY (all values in "units"; 1 unit = $1,000):
- Name: {country['name']}
- Treasury: {country['treasury']} units
- GDP: {country['gdp']} units
- Army: {country['army']} soldiers

PLAYER ORDER: "{order_text}"

UNIT SCALE reference:
- "$5 million" = 5,000 units
- "$100 million" = 100,000 units
- "$50 billion" = 50,000,000 units

HARD RULES:
1. If total cost > treasury, success MUST be false, and treasury_change / army_change / gdp_change MUST all be 0.
2. Treasury must never go below 0. Army must never go below 0.
3. "narrative" must be a SINGLE LINE in Persian, max 300 characters. NO literal newlines, NO quotation marks.
4. "reason" must be in Persian, max 150 characters.
5. Output must be strictly valid JSON (double quotes, no trailing commas).

EXACT format:
{{"success": true, "reason": "...", "treasury_change": 0, "army_change": 0, "gdp_change": 0, "narrative": "..."}}
"""


async def analyze_and_apply_order(order_id: int, context):
    order = await get_order(order_id)
    if not order:
        return {"success": False, "reason": "سفارش یافت نشد", "narrative": ""}
    country = await get_country(order["user_id"])
    if not country:
        return {"success": False, "reason": "کشور یافت نشد", "narrative": ""}

    prompt = _build_prompt(country, order["order_text"])

    # تلاش دوباره اگر پارس شکست بخوره
    data = {}
    for attempt in range(2):
        ai_response = await ask_ai(prompt)
        logger.info(f"AI RAW (attempt {attempt+1}) for order {order_id}:\n{ai_response}")
        data = _safe_parse_json(ai_response)
        if "success" in data and "narrative" in data:
            break
        logger.warning(f"Parse failed on attempt {attempt+1} for order {order_id}")
        await asyncio.sleep(1)

    if "success" not in data:
        data = {
            "success": False,
            "reason": "AI پاسخ نامعتبر داد",
            "narrative": "ستاد فرماندهی اعلام کرد این دستور به بررسی دستی نیاز دارد."
        }

    # ============ HARD SAFETY LAYER (VETO) ============
    if data.get("success"):
        try:
            t_change = int(data.get("treasury_change") or 0)
            a_change = int(data.get("army_change") or 0)
            g_change = int(data.get("gdp_change") or 0)
        except (TypeError, ValueError):
            data = {"success": False, "reason": "خروجی عددی AI نامعتبر بود", "narrative": ""}
        else:
            if country["treasury"] + t_change < 0:
                data = {
                    "success": False,
                    "reason": f"خزانه کافی نیست: هزینه {abs(t_change):,} واحد > موجودی {country['treasury']:,} واحد",
                    "treasury_change": 0, "army_change": 0, "gdp_change": 0,
                    "narrative": f"دولت {country['name']} اعلام کرد این طرح به دلیل کمبود بودجه قابل اجرا نیست."
                }
            elif country["army"] + a_change < 0:
                data = {
                    "success": False,
                    "reason": "نیروی نظامی کافی وجود ندارد",
                    "treasury_change": 0, "army_change": 0, "gdp_change": 0,
                    "narrative": "فرماندهی ارتش اعلام کرد امکان اجرای این دستور وجود ندارد."
                }
            else:
                # آپدیت اتمیک — قید در SQL هم race condition را می‌بندد
                async with pool.acquire() as conn:
                    row = await conn.fetchrow(
                        "UPDATE countries "
                        "SET treasury = treasury + $1, "
                        "    army = army + $2, "
                        "    gdp = GREATEST(1000, gdp + $3) "
                        "WHERE user_id = $4 AND treasury + $1 >= 0 AND army + $2 >= 0 "
                        "RETURNING treasury, army, gdp",
                        t_change, a_change, g_change, order["user_id"]
                    )
                    if not row:
                        data = {
                            "success": False,
                            "reason": "اجرای عملیات به دلیل تغییر هم‌زمان ممکن نشد.",
                            "treasury_change": 0, "army_change": 0, "gdp_change": 0,
                            "narrative": ""
                        }

    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE orders SET status='ai_analyzed', ai_analysis_raw=$1 WHERE id=$2",
            json.dumps(data, ensure_ascii=False), order_id
        )

    return data


# ============ State (in-memory) ============

temp = {}


async def set_commands(app):
    cmds = [
        BotCommand("start", "ثبت‌نام و شروع بازی"),
        BotCommand("country", "مشاهده اطلاعات کشور"),
        BotCommand("order", "ثبت دستور جدید"),
        BotCommand("cancel", "لغو عملیات")
    ]
    await app.bot.set_my_commands(cmds)


# ============ Handlers ============

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

    gov_main_name = GOVERNMENTS.get(c["gov_main"], {}).get("name", "")
    gov_sub_name = GOVERNMENTS.get(c["gov_main"], {}).get("subs", {}).get(c["gov_sub"], "")

    text = (
        f"🏛️ *کشور: {c['name']}*\n"
        f"👤 رهبر: {c['leader']}\n"
        f"⚙️ حکومت: {gov_main_name} - {gov_sub_name}\n\n"
        f"💰 خزانه: {fmt_money(c['treasury'])}\n"
        f"🎖 ارتش: {c['army']:,} نفر\n"
        f"📈 GDP: {fmt_money(c['gdp'])}"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def order_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    c = await get_country(uid)

    if not c or c["status"] != "active":
        await update.message.reply_text("⚠️ شما مجاز به ثبت دستور نیستید.")
        return

    if not context.args:
        await update.message.reply_text("⚠️ دستور خود را بعد از کامند بنویسید.\nمثال: `/order سرمایه‌گذاری ۱۰ میلیون دلاری در بخش نفت`")
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


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cb = update.callback_query
    data = cb.data
    uid = cb.from_user.id
    t = temp.get(uid, {})
    await cb.answer()

    # ---- ثبت‌نام ----
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
        if not t.get("gov_main") or not t.get("name") or not t.get("leader"):
            await cb.edit_message_text("⚠️ اطلاعات ثبت‌نام ناقص است. دوباره /start بزنید.")
            temp.pop(uid, None)
            return
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

    # ---- تایید/رد ثبت‌نام ----
    elif data.startswith("adm_ok_"):
        target_uid = int(data.split("_")[2])
        async with pool.acquire() as conn:
            await conn.execute("UPDATE countries SET status = 'active' WHERE user_id = $1", target_uid)
        await cb.edit_message_text("✅ کشور تایید شد.")
        try:
            await context.bot.send_message(target_uid, "🎉 کشور شما تایید شد! از این پس می‌توانید با /order دستور ثبت کنید.")
        except Exception as e:
            logger.warning(f"Could not notify user {target_uid}: {e}")

    elif data.startswith("adm_rej_"):
        target_uid = int(data.split("_")[2])
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM countries WHERE user_id = $1", target_uid)
        await cb.edit_message_text("❌ درخواست رد شد.")
        try:
            await context.bot.send_message(target_uid, "❌ درخواست ثبت کشور شما رد شد.")
        except Exception as e:
            logger.warning(f"Could not notify user {target_uid}: {e}")

    # ---- دسته‌بندی سفارش ----
    elif data.startswith("cat_"):
        category = data.replace("cat_", "")
        order_text = t.get("order_text")
        temp.pop(uid, None)

        if not order_text:
            await cb.edit_message_text("⚠️ اطلاعات شما منقضی شده. دوباره /order بزنید.")
            return

        async with pool.acquire() as conn:
            order_id = await conn.fetchval(
                "INSERT INTO orders (user_id, order_text, category) VALUES ($1, $2, $3) RETURNING id",
                uid, order_text, category
            )

        c = await get_country(uid)
        cat_fa = {"economic": "اقتصادی", "political": "سیاسی", "military": "نظامی"}.get(category, category)

        admin_text = (
            f"📜 **دستور جدید از {c['name']}**\n\n"
            f"🗂 دسته: {cat_fa}\n"
            f"📝 متن دستور: {order_text}\n\n"
            f"آیا با این تحلیل توسط هوش مصنوعی موافقید؟"
        )
        admin_btn = kb([
            [InlineKeyboardButton("✅ تایید و تحلیل", callback_data=f"ord_appr_{order_id}")],
            [InlineKeyboardButton("✏️ ویرایش دستور", callback_data=f"ord_edit_{order_id}")],
            [InlineKeyboardButton("❌ رد دستور", callback_data=f"ord_rej_{order_id}")]
        ])
        await context.bot.send_message(ADMIN_ID, admin_text, parse_mode="Markdown", reply_markup=admin_btn)
        await cb.edit_message_text("⏳ دستور شما به ادمین برای بررسی ارسال شد.")

    # ---- ادمین روی سفارش ----
    elif data.startswith("ord_appr_"):
        order_id = int(data.split("_")[2])
        await cb.edit_message_text("⏳ در حال تحلیل توسط هوش مصنوعی...")
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

    # ---- انتشار در کانال ----
    elif data.startswith("pub_"):
        order_id = int(data.split("_")[2])
        order = await get_order(order_id)
        if not order:
            await cb.edit_message_text("⚠️ سفارش یافت نشد.")
            return

        try:
            ai_data = json.loads(order["ai_analysis_raw"] or "{}")
        except json.JSONDecodeError:
            ai_data = {}

        narrative = ai_data.get("narrative") or "اتفاقی افتاد."
        final_text = f"📢 **بیانیه رسمی**\n\n{narrative}"

        if CHANNEL_ID:
            try:
                await context.bot.send_message(CHANNEL_ID, final_text, parse_mode="Markdown")
                async with pool.acquire() as conn:
                    await conn.execute("UPDATE orders SET status = 'published', published_at = NOW() WHERE id = $1", order_id)
                await cb.edit_message_text("✅ در کانال منتشر شد.")
            except Exception as e:
                await cb.edit_message_text(f"❌ خطا در ارسال به کانال: {e}")
        else:
            await cb.edit_message_text("⚠️ آیدی کانال تنظیم نشده است.")

    elif data == "cancel_pub":
        await cb.edit_message_text("❌ انتشار لغو شد.")


async def analyze_and_send_to_admin(update_or_cb, context, order_id):
    ai_data = await analyze_and_apply_order(order_id, context)

    status_icon = "✅ موفقیت‌آمیز" if ai_data.get("success") else "❌ ناموفق"

    # خلاصه‌ی تغییرات اقتصادی اگر موفق بود
    changes_line = ""
    if ai_data.get("success"):
        tc = ai_data.get("treasury_change", 0)
        ac = ai_data.get("army_change", 0)
        gc = ai_data.get("gdp_change", 0)
        changes_line = (
            f"\n💰 خزانه: {tc:+,} واحد\n"
            f"🎖 ارتش: {ac:+,} نفر\n"
            f"📈 GDP: {gc:+,} واحد\n"
        )

    text = (
        f"🧠 **نتیجه تحلیل هوش مصنوعی**\n\n"
        f"📌 وضعیت عملیات: {status_icon}\n"
        f"📝 تحلیل: {ai_data.get('reason', 'دلیلی ذکر نشد')}\n"
        f"{changes_line}\n"
        f"📖 **انتشار برای کانال:**\n"
        f"{ai_data.get('narrative', '')}\n\n"
        f"برای کانال تایید می‌شود؟"
    )

    btn = kb([
        [InlineKeyboardButton("📢 انتشار در کانال", callback_data=f"pub_{order_id}")],
        [InlineKeyboardButton("❌ لغو", callback_data="cancel_pub")]
    ])

    if isinstance(update_or_cb, CallbackQuery):
        try:
            await update_or_cb.edit_message_text(text, parse_mode="Markdown", reply_markup=btn)
        except Exception:
            await update_or_cb.message.reply_text(text, parse_mode="Markdown", reply_markup=btn)
    else:
        await update_or_cb.message.reply_text(text, parse_mode="Markdown", reply_markup=btn)


# ============ Bootstrap ============

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
