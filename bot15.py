import os
import json
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
CHANNEL_ID = os.environ.get("CHANNEL_ID", "") # آیدی کانال عمومی
CLOUDFLARE_API_TOKEN = os.environ.get("CLOUDFLARE_API_TOKEN", "")
CLOUDFLARE_ACCOUNT_ID = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")

# --- ساختار عمیق حکومت‌ها ---
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
        # جدول کشورها
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
        # جدول دستورات (قلب سیستم)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                order_text TEXT,
                category TEXT, -- economic, political, military
                status TEXT DEFAULT 'pending', 
                admin_note TEXT,
                ai_analysis_raw TEXT,
                final_text TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                published_at TIMESTAMP DEFAULT NULL
            )
        """)
    logger.info("Database initialized.")

# --- توابع کمکی ---
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

# --- ارتباط با هوش مصنوعی (Cloudflare) ---
async def ask_ai(prompt: str, system_prompt: str = "You are a game master AI for a geopolitical strategy game.") -> str:
    url = f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/ai/run/@cf/meta/llama-3-8b-instruct"
    headers = {"Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}"}
    payload = {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]
    }
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload, timeout=40)
            res_data = response.json()
            if res_data.get("success"):
                return res_data["result"]["response"]
            return "⚠️ خطا در ارسال خروجی AI."
    except Exception as e:
        logger.error(f"AI Error: {e}")
        return "⚠️ ارتباط  قطع شد."

# --- تحلیل دستور توسط AI و ثبت در دیتابیس ---
async def analyze_and_apply_order(order_id: int):
    order = await get_order(order_id)
    country = await get_country(order["user_id"])
    
    # پرامپت برای تحلیل (اجبار به خروجی JSON)
    prompt = f"""
    Country: {country['name']}
    Current Treasury: {country['treasury']}
    Current Army: {country['army']}
    Current GDP: {country['gdp']}
    
    Player's Order: "{order['order_text']}"
    Category: {order['category']}
    
    Analyze this order and respond ONLY with a JSON object in Persian (Farsi) format:
    {{
        "success": true/false,
        "reason": "دلیل موفقیت یا شکست",
        "treasury_change": integer (negative for cost, positive for gain),
        "army_change": integer,
        "gdp_change": integer,
        "narrative": "یک توضیح کوتاه و هیجان‌انگیز به زبان فارسی درباره اتفاقی که افتاد."
    }}
    """
    
    ai_response = await ask_ai(prompt)
    
    # استخراج JSON از پاسخ
    try:
        import re
        json_match = re.search(r'\{.*\}', ai_response, re.DOTALL)
        data = json.loads(json_match.group(0)) if json_match else {}
    except:
        data = {"success": False, "reason": "خطای پردازش", "narrative": "فرماندهی نتوانست دستور را اجرا کند."}

    # آپدیت دیتابیس
    async with pool.acquire() as conn:
        if data.get("success"):
            new_treasury = max(0, country['treasury'] + data.get("treasury_change", 0))
            new_army = max(0, country['army'] + data.get("army_change", 0))
            new_gdp = max(1000, country['gdp'] + data.get("gdp_change", 0))
            
            await conn.execute("UPDATE countries SET treasury=$1, army=$2, gdp=$3 WHERE user_id=$4", 
                               new_treasury, new_army, new_gdp, order["user_id"])
            
        await conn.execute("UPDATE orders SET status='ai_analyzed', ai_analysis_raw=$1 WHERE id=$2", 
                           json.dumps(data, ensure_ascii=False), order_id)
    
    return data


# --- وضعیت موقت برای فرم ثبت‌نام ---
temp = {}

async def set_commands(app):
    cmds = [
        BotCommand("start", "ثبت‌نام و شروع بازی"),
        BotCommand("country", "مشاهده اطلاعات کشور"),
        BotCommand("order", "ثبت دستور جدید (اقتصادی/سیاسی/نظامی)"),
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
    await update.message.reply_text("🏛️ به سیستم ناوال خوش آمدید.\nلطفاً **نام کشور** خود را وارد کنید:")

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
        f"📈 GDP: {fmt_money(c['gdp'])}"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

# --- ثبت دستور جدید توسط بازیکن ---
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

# --- هندلر پیام‌های متنی (برای فرم ثبت‌نام و ویرایش ادمین) ---
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text.strip()
    t = temp.get(uid, {})

    # --- مراحل ثبت‌نام ---
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

    # --- ویرایش دستور توسط ادمین ---
    elif t.get("step") == "ADMIN_EDIT_ORDER" and uid == ADMIN_ID:
        order_id = t["order_id"]
        async with pool.acquire() as conn:
            await conn.execute("UPDATE orders SET order_text = $1 WHERE id = $2", text, order_id)
        temp.pop(uid, None)
        await update.message.reply_text("✅ دستور ویرایش شد. در حال تحلیل با هوش مصنوعی...")
        await analyze_and_send_to_admin(update, context, order_id)

# --- پردازش دکمه‌های شیشه‌ای ---
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cb = update.callback_query
    data = cb.data
    uid = cb.from_user.id
    t = temp.get(uid, {})
    await cb.answer()

    # --- انتخاب زیرشاخه حکومت در ثبت‌نام ---
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
        
        # ثبت در دیتابیس با وضعیت pending
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO countries (user_id, username, name, leader, gov_main, gov_sub, status) VALUES ($1, $2, $3, $4, $5, $6, 'pending')",
                uid, cb.from_user.username, t["name"], t["leader"], t["gov_main"], sub_gov
            )
            
        await cb.edit_message_text("⏳ درخواست ثبت کشور شما ارسال شد. منتظر تایید ادمین باشید.")
        
        # ارسال به ادمین
        gov_name = GOVERNMENTS[t['gov_main']]['name'] + " - " + GOVERNMENTS[t['gov_main']]['subs'][sub_gov]
        admin_text = f"📥 **درخواست ثبت کشور جدید**\n\n🏛️ {t['name']}\n👤 رهبر: {t['leader']}\n⚙️ حکومت: {gov_name}\n🆔 `{uid}`"
        admin_btn = kb([[InlineKeyboardButton("✅ تایید", callback_data=f"adm_ok_{uid}"), InlineKeyboardButton("❌ رد", callback_data=f"adm_rej_{uid}")]])
        await context.bot.send_message(ADMIN_ID, admin_text, parse_mode="Markdown", reply_markup=admin_btn)

    # --- تایید/رد ثبت‌نام توسط ادمین ---
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

    # --- دسته‌بندی دستور توسط بازیکن ---
    elif data.startswith("cat_"):
        category = data.replace("cat_", "")
        order_text = t.get("order_text")
        temp.pop(uid, None)
        
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
            f"آیا با این تحلیل  توسط هوش مصنوعی موافقید؟"
        )
        admin_btn = kb([
            [InlineKeyboardButton("✅ تایید و تحلیل", callback_data=f"ord_appr_{order_id}")],
            [InlineKeyboardButton("✏️ ویرایش دستور", callback_data=f"ord_edit_{order_id}")],
            [InlineKeyboardButton("❌ رد دستور", callback_data=f"ord_rej_{order_id}")]
        ])
        await context.bot.send_message(ADMIN_ID, admin_text, parse_mode="Markdown", reply_markup=admin_btn)
        await cb.edit_message_text("⏳ دستور شما برای بررسی به فرماندهی ارسال شد.")

    # --- تایید اولیه ادمین (شروع تحلیل AI) ---
    elif data.startswith("ord_appr_"):
        order_id = int(data.split("_")[2])
        await cb.edit_message_text("⏳ در حال تحلیل توسط هوش مصنوعی...")
        await analyze_and_send_to_admin(cb, context, order_id)

    # --- ویرایش دستور توسط ادمین ---
    elif data.startswith("ord_edit_"):
        order_id = int(data.split("_")[2])
        temp[uid] = {"step": "ADMIN_EDIT_ORDER", "order_id": order_id}
        await cb.edit_message_text("✏️ لطفاً متن اصلاح‌شده دستور را ارسال کنید:")

    # --- رد دستور ---
    elif data.startswith("ord_rej_"):
        order_id = int(data.split("_")[2])
        async with pool.acquire() as conn:
            await conn.execute("UPDATE orders SET status = 'rejected' WHERE id = $1", order_id)
        await cb.edit_message_text("❌ دستور رد شد.")

    # --- انتشار در کانال توسط ادمین ---
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

# --- تابع کمکی برای اتصال AI به ادمین ---
async def analyze_and_send_to_admin(update_or_cb, context, order_id):
    ai_data = await analyze_and_apply_order(order_id)
    
    if ai_data.get("success"):
        status_icon = "✅ موفقیت‌آمیز"
    else:
        status_icon = "❌ ناموفق"
        
    text = (
        f"🧠 **نتیجه تحلیل هوش مصنوعی**\n\n"
        f"📌 وضعیت عملیات: {status_icon}\n"
        f"📝 تحلیل: {ai_data.get('reason', 'دلیلی ذکر نشد')}\n\n"
        f"📖 **انتشار برای کانال:**\n"
        f"{ai_data.get('narrative', '')}\n\n"
        f" برای کانال تایید می‌شود؟"
    )
    
    btn = kb([
        [InlineKeyboardButton("📢 انتشار در کانال", callback_data=f"pub_{order_id}")],
        [InlineKeyboardButton("❌ لغو", callback_data="cancel_pub")]
    ])
    
    if hasattr(update_or_cb, "message"):
        await update_or_cb.message.reply_text(text, parse_mode="Markdown", reply_markup=btn)
    else:
        await update_or_cb.edit_message_text(text, parse_mode="Markdown", reply_markup=btn)

# --- راه‌اندازی نهایی ---
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

