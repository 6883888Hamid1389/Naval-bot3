
import os
import time
import asyncpg
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes,
)

TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_ID = 8849773822
DATABASE_URL = os.environ.get("DATABASE_URL", "")

if not TOKEN:
    raise SystemExit("BOT_TOKEN not set!")
if not DATABASE_URL:
    raise SystemExit("DATABASE_URL not set!")

GOVS = {
    "dictator": "✊ دیکتاتوری",
    "democracy": "🗳️ دموکراسی",
    "religious": "🕌 دینی (تئوکراسی)",
    "monarch": "👑 سلطنتی",
    "communist": "☭ کمونیستی",
    "republic": "🏛️ جمهوری",
}

GOV_SUBS = {
    "dictator": {
        "mil": ["🔒 دیکتاتوری نظامی", 35, "🪖 زیر نظر حکومت و ارتش"],
        "personal": ["👑 دیکتاتوری فردی", 25, "👤 زیر نظر شخص رهبر"],
    },
    "democracy": {
        "parl": ["📜 دموکراسی پارلمانی", 85, "👥 زیر نظر کل مردم"],
        "pres": ["🗳️ دموکراسی ریاستی", 80, "👥 زیر نظر کل مردم (با نفوذ نخبگان)"],
    },
    "religious": {
        "trad": ["🕌 تئوکراسی سنتی", 70, "🕌 زیر نظر روحانیت و مردم"],
        "mod": ["⚖️ تئوکراسی میانه‌رو", 80, "🤝 زیر نظر مردم و دین"],
        "mil": ["🛡️ تئوکراسی نظامی-دینی", 55, "🪖 زیر نظر ارتش و روحانیت"],
        "legal": ["📜 تئوکراسی قانون‌گرا", 75, "📜 زیر نظر قانون و مردم"],
        "radical": ["💀 تئوکراسی افراطی", 25, "💀 زیر نظر گروه کوچک قدرت"],
    },
    "monarch": {
        "abs": ["👑 سلطنت مطلقه", 45, "👑 زیر نظر خانواده سلطنتی"],
        "const": ["🏛️ سلطنت مشروطه", 75, "👥 زیر نظر مردم و پادشاه"],
    },
    "communist": {
        "one": ["☭ کمونیسم تک‌حزبی", 60, "☭ زیر نظر حزب واحد"],
    },
    "republic": {
        "sec": ["🏛️ جمهوری سکولار", 80, "👥 زیر نظر کل مردم"],
        "theo": ["⚖️ جمهوری تئوکراتیک", 55, "📖 زیر نظر مردم و روحانیت"],
    },
}

RELIGIONS = {
    "islam": "☪️ اسلام",
    "christ": "✝️ مسیحیت",
    "jew": "✡️ یهودیت",
    "hindu": "🕉️ هندوئیسم",
    "budd": "☸️ بودیسم",
    "secular": "🕊️ سکولار",
}

REL_SUBS = {
    "islam": {
        "shia12": "🔵 شیعه دوازده‌امامی",
        "shia_ism": "🟢 شیعه اسماعیلی",
        "shia_zayd": "🟡 شیعه زیدی",
        "suni_hanafi": "🟠 سنی حنفی",
        "suni_shafei": "🔴 سنی شافعی",
        "suni_maleki": "🟣 سنی مالکی",
        "suni_hanbali": "⚫ سنی حنبلی",
    },
    "christ": {"cath": "⛪ کاتولیک", "orth": "🏛️ ارتدوکس", "prot": "📖 پروتستان"},
    "jew": {"orth": "✡️ ارتدوکس", "cons": "🕎 محافظه‌کار", "ref": "📜 اصلاح‌طلب"},
    "budd": {"thera": "🟡 تراوادا", "maha": "🔴 ماهایانا", "vajra": "⚫ وجریانا"},
}

EXPERTS = {
    "heavy": "🏭 صنایع سنگین",
    "energy": "⛽ سوخت و انرژی",
    "grain": "🌾 غلات و کشاورزی",
    "military": "🔫 صنایع نظامی",
}

REGIONS = ["III", "GGG", "YYY", "OOO", "TTT", "FFF", "SSS", "AAA",
           "HHH", "KKK", "LLL", "RRR", "DDD", "WWW", "QQQ"]

temp = {}
spam_tracker = {}
banned_users = set()
spam_limit = 5
spam_window = 10

pool = None


def kb(rows):
    return InlineKeyboardMarkup(rows)


def check_spam(uid: int) -> bool:
    now = time.time()
    if uid not in spam_tracker:
        spam_tracker[uid] = []
    spam_tracker[uid] = [t for t in spam_tracker[uid] if now - t < spam_window]
    spam_tracker[uid].append(now)
    if len(spam_tracker[uid]) > spam_limit:
        banned_users.add(uid)
        return True
    return False


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
                age INT,
                reign TEXT,
                gov TEXT,
                gov_sub TEXT,
                religion TEXT,
                rel_sub TEXT,
                expert TEXT,
                region TEXT,
                happiness INT,
                science TEXT,
                flag_id TEXT,
                status TEXT,
                economy INT DEFAULT 500,
                army INT DEFAULT 100,
                revolt INT DEFAULT 5,
                ban_reason TEXT
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS pending (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                name TEXT,
                leader TEXT,
                age INT,
                reign TEXT,
                gov TEXT,
                gov_sub TEXT,
                religion TEXT,
                rel_sub TEXT,
                expert TEXT,
                region TEXT,
                happiness INT,
                science TEXT,
                flag_id TEXT
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS regions (
                code TEXT PRIMARY KEY,
                user_id BIGINT
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS spam_banned (
                user_id BIGINT PRIMARY KEY
            )
        """)
    # load banned users
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT user_id FROM spam_banned")
        for r in rows:
            banned_users.add(r["user_id"])


async def get_country(uid):
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM countries WHERE user_id = $1", uid)
        return dict(row) if row else None


async def get_pending(uid):
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM pending WHERE user_id = $1", uid)
        return dict(row) if row else None


async def save_pending(uid, data):
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO pending (user_id, username, name, leader, age, reign, gov, gov_sub,
                religion, rel_sub, expert, region, happiness, science, flag_id)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15)
            ON CONFLICT (user_id) DO UPDATE SET
                username=$2, name=$3, leader=$4, age=$5, reign=$6, gov=$7, gov_sub=$8,
                religion=$9, rel_sub=$10, expert=$11, region=$12, happiness=$13,
                science=$14, flag_id=$15
        """, uid, data.get("username"), data.get("name"), data.get("leader"),
            data.get("age"), data.get("reign"), data.get("gov"), data.get("gov_sub"),
            data.get("religion"), data.get("rel_sub"), data.get("expert"),
            data.get("region"), data.get("happiness"), data.get("science"),
            data.get("flag_id"))


async def delete_pending(uid):
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM pending WHERE user_id = $1", uid)


async def save_country(uid, data):
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO countries (user_id, username, name, leader, age, reign, gov, gov_sub,
                religion, rel_sub, expert, region, happiness, science, flag_id, status,
                economy, army, revolt)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,'approved',500,100,5)
            ON CONFLICT (user_id) DO UPDATE SET
                username=$2, name=$3, leader=$4, age=$5, reign=$6, gov=$7, gov_sub=$8,
                religion=$9, rel_sub=$10, expert=$11, region=$12, happiness=$13,
                science=$14, flag_id=$15, status='approved'
        """, uid, data.get("username"), data.get("name"), data.get("leader"),
            data.get("age"), data.get("reign"), data.get("gov"), data.get("gov_sub"),
            data.get("religion"), data.get("rel_sub"), data.get("expert"),
            data.get("region"), data.get("happiness"), data.get("science"),
            data.get("flag_id"))


async def set_country_status(uid, status, ban_reason=None):
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE countries SET status=$1, ban_reason=$2 WHERE user_id=$3",
            status, ban_reason, uid
        )


async def delete_country(uid):
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM countries WHERE user_id = $1", uid)


async def get_all_countries():
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM countries ORDER BY user_id DESC")
        return [dict(r) for r in rows]


async def get_banned_countries():
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM countries WHERE status='banned' ORDER BY user_id DESC")
        return [dict(r) for r in rows]


async def get_pending_all():
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM pending")
        return [dict(r) for r in rows]


async def get_regions():
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT code, user_id FROM regions")
        return {r["code"]: r["user_id"] for r in rows}


async def take_region(code, uid):
    async with pool.acquire() as conn:
        try:
            await conn.execute(
                "INSERT INTO regions (code, user_id) VALUES ($1, $2)", code, uid
            )
            return True
        except asyncpg.UniqueViolationError:
            return False


async def free_region(code):
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM regions WHERE code = $1", code)


async def add_spam_ban(uid):
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO spam_banned (user_id) VALUES ($1) ON CONFLICT DO NOTHING", uid
        )


async def remove_spam_ban(uid):
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM spam_banned WHERE user_id = $1", uid)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    chat_id = update.effective_chat.id

    if uid in banned_users and uid != ADMIN_ID:
        await context.bot.send_message(chat_id, "🚫 شما به دلیل اسپم مسدود شده‌اید.")
        return

    if check_spam(uid) and uid != ADMIN_ID:
        await context.bot.send_message(chat_id, "🚫 اسپم! شما مسدود شدید.")
        await add_spam_ban(uid)
        return

    c = await get_country(uid)
    if c:
        if c["status"] == "approved":
            await context.bot.send_message(chat_id, "✅ کشور شما قبلاً تأیید شده است.")
        elif c["status"] == "banned":
            await context.bot.send_message(chat_id, "🚫 کشور شما توسط ادمین مسدود شده است.")
        else:
            await context.bot.send_message(chat_id, "⏳ درخواست شما در حال بررسی ادمین است.")
        return

    temp[uid] = {
        "username": update.effective_user.username or update.effective_user.first_name,
        "step": "MENU",
    }
    keyboard = kb([[InlineKeyboardButton("🏛️ ثبت کشور", callback_data="register_country")]])
    await context.bot.send_message(
        chat_id,
        "🌊 *به ناوال لیگ خوش آمدی!*\n\nWelcome to Naval League",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    temp.pop(uid, None)
    await update.message.reply_text("❌ لغو شد.")


async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid != ADMIN_ID:
        return
    temp.pop(uid, None)
    chat_id = update.effective_chat.id

    all_c = await get_all_countries()
    total = len(all_c)
    approved = len([c for c in all_c if c["status"] == "approved"])
    banned = len([c for c in all_c if c["status"] == "banned"])
    pending_list = await get_pending_all()
    pending = len(pending_list)

    text = (
        f"👑 *پنل مدیریت ناوال لیگ*\n\n"
        f"📊 آمار کلی:\n"
        f"• کل کشورها: {total}\n"
        f"• فعال: {approved}\n"
        f"• مسدود: {banned}\n"
        f"• در انتظار تأیید: {pending}\n\n"
        f"یکی از گزینه‌ها را انتخاب کن:"
    )

    keyboard = kb([
        [InlineKeyboardButton("📋 لیست کشورها", callback_data="adm_list_0")],
        [InlineKeyboardButton("🚫 لیست مسدودها", callback_data="adm_banned_0")],
        [InlineKeyboardButton("⏳ درخواست‌های در انتظار", callback_data="adm_pending_0")],
        [InlineKeyboardButton("🗺️ وضعیت مناطق", callback_data="adm_regions")],
        [InlineKeyboardButton("🛡️ لیست مسدودهای اسپم", callback_data="adm_spamlist")],
    ])

    await context.bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=keyboard)


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cb = update.callback_query
    data = cb.data
    uid = cb.from_user.id
    chat_id = cb.message.chat.id
    msg_id = cb.message.message_id
    t = temp.get(uid, {})

    await cb.answer()

    async def edit(text, keyboard=None):
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id, message_id=msg_id,
                text=text, parse_mode="Markdown", reply_markup=keyboard,
            )
        except Exception:
            pass

    if data == "adm_panel" and uid == ADMIN_ID:
        all_c = await get_all_countries()
        total = len(all_c)
        approved = len([c for c in all_c if c["status"] == "approved"])
        banned = len([c for c in all_c if c["status"] == "banned"])
        pending_list = await get_pending_all()
        pending = len(pending_list)
        text = (
            f"👑 *پنل مدیریت ناوال لیگ*\n\n"
            f"📊 آمار کلی:\n"
            f"• کل کشورها: {total}\n"
            f"• فعال: {approved}\n"
            f"• مسدود: {banned}\n"
            f"• در انتظار تأیید: {pending}\n\n"
            f"یکی از گزینه‌ها را انتخاب کن:"
        )
        keyboard = kb([
            [InlineKeyboardButton("📋 لیست کشورها", callback_data="adm_list_0")],
            [InlineKeyboardButton("🚫 لیست مسدودها", callback_data="adm_banned_0")],
            [InlineKeyboardButton("⏳ درخواست‌های در انتظار", callback_data="adm_pending_0")],
            [InlineKeyboardButton("🗺️ وضعیت مناطق", callback_data="adm_regions")],
            [InlineKeyboardButton("🛡️ لیست مسدودهای اسپم", callback_data="adm_spamlist")],
        ])
        await edit(text, keyboard)
        return

    if data == "adm_spamlist" and uid == ADMIN_ID:
        if not banned_users:
            await edit("🛡️ هیچ کاربر اسپمی مسدود نشده.",
                       kb([[InlineKeyboardButton("🔙 پنل", callback_data="adm_panel")]]))
            return
        text = "🛡️ *کاربران مسدود (اسپم):*\n\n"
        buttons = []
        for bu in banned_users:
            text += f"🆔 `{bu}`\n"
            buttons.append([InlineKeyboardButton(f"✅ رفع مسدودی {bu}", callback_data=f"adm_unspam_{bu}")])
        buttons.append([InlineKeyboardButton("🔙 پنل", callback_data="adm_panel")])
        await edit(text, kb(buttons))
        return

    if data.startswith("adm_unspam_") and uid == ADMIN_ID:
        try:
            target = int(data.replace("adm_unspam_", ""))
        except ValueError:
            return
        banned_users.discard(target)
        spam_tracker.pop(target, None)
        await remove_spam_ban(target)
        await edit("✅ کاربر از مسدودی اسپم خارج شد.",
                   kb([[InlineKeyboardButton("🔙 لیست", callback_data="adm_spamlist")]]))
        return

    if data == "register_country":
        c = await get_country(uid)
        if c:
            msg = ("✅ قبلاً ثبت شدی." if c["status"] == "approved"
                   else "🚫 مسدود هستی." if c["status"] == "banned"
                   else "⏳ در انتظار تأیید.")
            await cb.answer(msg, show_alert=True)
            return
        temp[uid] = {
            "username": cb.from_user.username or cb.from_user.first_name,
            "step": "NAME",
        }
        await edit("🏛️ *نام کشور* خود را بنویس:\n\n(Enter your country name)")
        return

    if data.startswith("reign_"):
        map_ = {
            "reign_5": "۵ سال", "reign_10": "۱۰ سال",
            "reign_20": "۲۰ سال", "reign_30": "۳۰ سال",
            "reign_life": "مادام‌العمر",
        }
        t["reign"] = map_.get(data, "۱۰ سال")
        t["step"] = "GOV"
        temp[uid] = t
        rows = [[InlineKeyboardButton(v, callback_data=f"gov_{k}")] for k, v in GOVS.items()]
        await edit("⚙️ *نوع حکومت* را انتخاب کن:", kb(rows))
        return

    if data.startswith("gov_") and not data.startswith("govsub_"):
        gov_key = data.replace("gov_", "")
        if gov_key not in GOVS:
            return
        t["gov"] = GOVS[gov_key]
        t["step"] = "GOV_SUB"
        temp[uid] = t
        rows = [[InlineKeyboardButton(v[0], callback_data=f"govsub_{gov_key}_{k}")]
                for k, v in GOV_SUBS[gov_key].items()]
        await edit("🏛️ *نظام حکومتی* را انتخاب کن:", kb(rows))
        return

    if data.startswith("govsub_"):
        parts = data.replace("govsub_", "").split("_")
        gov_key = parts[0]
        sub_key = "_".join(parts[1:])
        if gov_key not in GOV_SUBS or sub_key not in GOV_SUBS[gov_key]:
            return
        sub_name, happiness, science = GOV_SUBS[gov_key][sub_key]
        t["gov_sub"] = sub_name
        t["happiness"] = happiness
        t["science"] = science
        t["step"] = "RELIGION"
        temp[uid] = t
        rows = [[InlineKeyboardButton(v, callback_data=f"rel_{k}")] for k, v in RELIGIONS.items()]
        await edit("☪️ *دین رسمی* را انتخاب کن:", kb(rows))
        return

    if data.startswith("rel_") and not data.startswith("relsub_"):
        rel_key = data.replace("rel_", "")
        if rel_key not in RELIGIONS:
            return
        t["religion"] = RELIGIONS[rel_key]
        if rel_key == "secular" or rel_key not in REL_SUBS:
            t["rel_sub"] = "—"
            t["step"] = "EXPERT"
            temp[uid] = t
            rows = [[InlineKeyboardButton(v, callback_data=f"exp_{k}")] for k, v in EXPERTS.items()]
            await edit("🏭 *تخصص اقتصادی* را انتخاب کن:", kb(rows))
            return
        t["step"] = "REL_SUB"
        temp[uid] = t
        rows = [[InlineKeyboardButton(v, callback_data=f"relsub_{rel_key}_{k}")]
                for k, v in REL_SUBS[rel_key].items()]
        await edit("📖 *مذهب* را انتخاب کن:", kb(rows))
        return

    if data.startswith("relsub_"):
        parts = data.replace("relsub_", "").split("_")
        rel_key = parts[0]
        sub_key = "_".join(parts[1:])
        if rel_key not in REL_SUBS or sub_key not in REL_SUBS[rel_key]:
            return
        t["rel_sub"] = REL_SUBS[rel_key][sub_key]
        t["step"] = "EXPERT"
        temp[uid] = t
        rows = [[InlineKeyboardButton(v, callback_data=f"exp_{k}")] for k, v in EXPERTS.items()]
        await edit("🏭 *تخصص اقتصادی* را انتخاب کن:", kb(rows))
        return

    if data.startswith("exp_"):
        exp_key = data.replace("exp_", "")
        if exp_key not in EXPERTS:
            return
        t["expert"] = EXPERTS[exp_key]
        t["step"] = "REGION"
        temp[uid] = t

        taken = await get_regions()
        rows, row, count = [], [], 0
        for code in REGIONS:
            if code in taken:
                row.append(InlineKeyboardButton(f"🔒 {code}", callback_data="region_locked"))
            else:
                row.append(InlineKeyboardButton(f"🟢 {code}", callback_data=f"region_{code}"))
            count += 1
            if count % 3 == 0:
                rows.append(row)
                row = []
        if row:
            rows.append(row)

        await edit("📍 *منطقه مورد نظر* را انتخاب کن:\n🔒 = گرفته شده", kb(rows))
        return

    if data == "region_locked":
        await cb.answer("🔒 این منطقه قبلاً گرفته شده!", show_alert=True)
        return

    if data.startswith("region_"):
        code = data.replace("region_", "")
        taken = await get_regions()
        if code in taken:
            await cb.answer("🔒 این منطقه همین الان گرفته شد!", show_alert=True)
            return
        t["region"] = code
        t["step"] = "FLAG"
        temp[uid] = t
        await edit(f"✅ منطقه *{code}* انتخاب شد.\n\n🖼️ حالا *عکس پرچم کشور* را ارسال کن:")
        return

    if data == "confirm_restart":
        temp.pop(uid, None)
        try:
            await context.bot.edit_message_caption(
                chat_id=chat_id, message_id=msg_id,
                caption="🔄 فرم پاک شد. /start را بزن.",
            )
        except Exception:
            pass
        return

    if data == "confirm_yes":
        d = temp.get(uid)
        if not d:
            return
        taken = await get_regions()
        if d.get("region") in taken:
            try:
                await context.bot.edit_message_caption(
                    chat_id=chat_id, message_id=msg_id,
                    caption=f"❌ متأسفانه منطقه *{d['region']}* همین الان گرفته شد.\n"
                            f"/start بزن و منطقه دیگری انتخاب کن.",
                    parse_mode="Markdown",
                )
            except Exception:
                pass
            temp.pop(uid, None)
            return

        admin_text = (
            f"📥 *درخواست ثبت کشور جدید*\n\n"
            f"🏛️ کشور: {d['name']}\n👤 رهبر: {d['leader']}\n🎂 سن: {d['age']} سال\n"
            f"⏳ مدت حکومت: {d['reign']}\n⚙️ حکومت: {d['gov']}\n🏛️ نظام حکومتی: {d['gov_sub']}\n"
            f"☪️ دین: {d['religion']} — {d['rel_sub']}\n🏭 تخصص: {d['expert']}\n"
            f"📍 منطقه: {d['region']}\n😊 رضایت مردمی: {d['happiness']}٪\n🔬 علم: {d['science']}\n\n"
            f"👤 کاربر: @{d.get('username', '')}\n🆔 آیدی: `{uid}`"
        )

        keyboard = kb([
            [InlineKeyboardButton("✅ تأیید", callback_data=f"adm_ok_{uid}")],
            [InlineKeyboardButton("❌ رد", callback_data=f"adm_no_{uid}")],
        ])

        await save_pending(uid, d)

        await context.bot.send_photo(
            chat_id=ADMIN_ID, photo=d["flag_id"],
            caption=admin_text, parse_mode="Markdown", reply_markup=keyboard,
        )
        try:
            await context.bot.edit_message_caption(
                chat_id=chat_id, message_id=msg_id,
                caption="⏳ درخواست شما به ادمین ارسال شد. منتظر تأیید باش.",
            )
        except Exception:
            pass
        return

    if data.startswith("adm_list_") and uid == ADMIN_ID:
        try:
            page = int(data.replace("adm_list_", ""))
        except ValueError:
            page = 0
        await show_country_list(chat_id, msg_id, context, page, "all")
        return

    if data.startswith("adm_banned_") and uid == ADMIN_ID:
        try:
            page = int(data.replace("adm_banned_", ""))
        except ValueError:
            page = 0
        await show_country_list(chat_id, msg_id, context, page, "banned")
        return

    if data == "adm_pending_0" and uid == ADMIN_ID:
        pending_list = await get_pending_all()
        if not pending_list:
            await edit("⏳ هیچ درخواست در انتظاری وجود ندارد.",
                       kb([[InlineKeyboardButton("🔙 پنل", callback_data="adm_panel")]]))
            return
        text = "⏳ *درخواست‌های در انتظار:*\n\n"
        for d in pending_list:
            text += f"🏛️ {d['name']} — @{d.get('username', '')}\n"
        await edit(text, kb([[InlineKeyboardButton("🔙 پنل", callback_data="adm_panel")]]))
        return

    if data.startswith("adm_view_") and uid == ADMIN_ID:
        try:
            target = int(data.replace("adm_view_", ""))
        except ValueError:
            return
        await show_country_detail(chat_id, msg_id, context, target)
        return

    if data.startswith("adm_ban_") and uid == ADMIN_ID:
        try:
            target = int(data.replace("adm_ban_", ""))
        except ValueError:
            return
        temp[uid] = {"step": "BAN_REASON", "targetUid": target}
        await edit(
            f"📝 دلیل مسدود کردن کشور را بنویس:\n\n🆔 آیدی هدف: `{target}`",
            kb([[InlineKeyboardButton("❌ لغو", callback_data=f"adm_view_{target}")]]),
        )
        return

    if data.startswith("adm_unban_") and uid == ADMIN_ID:
        try:
            target = int(data.replace("adm_unban_", ""))
        except ValueError:
            return
        await set_country_status(target, "approved", None)
        try:
            await context.bot.send_message(target, "✅ کشور شما از مسدودی خارج شد!")
        except Exception:
            pass
        await show_country_detail(chat_id, msg_id, context, target)
        return

    if data.startswith("adm_del_") and uid == ADMIN_ID:
        try:
            target = int(data.replace("adm_del_", ""))
        except ValueError:
            return
        c = await get_country(target)
        if c:
            if c.get("region"):
                await free_region(c["region"])
            await delete_country(target)
            try:
                await context.bot.send_message(
                    target, f"🗑️ کشور *{c['name']}* توسط ادمین حذف شد.",
                    parse_mode="Markdown",
                )
            except Exception:
                pass
        await edit("🗑️ کشور با موفقیت حذف شد.",
                   kb([[InlineKeyboardButton("🔙 لیست", callback_data="adm_list_0")]]))
        return

    if data.startswith("adm_free_") and uid == ADMIN_ID:
        code = data.replace("adm_free_", "")
        await free_region(code)
        await show_regions_status(chat_id, msg_id, context)
        return

    if data == "adm_regions" and uid == ADMIN_ID:
        await show_regions_status(chat_id, msg_id, context)
        return

    if data == "adm_noop":
        await cb.answer("این منطقه آزاده ✅")
        return

    if data.startswith("adm_ok_") or data.startswith("adm_no_"):
        if uid != ADMIN_ID:
            return
        action = "ok" if data.startswith("adm_ok_") else "no"
        try:
            target_uid = int(data.split("_")[2])
        except (IndexError, ValueError):
            return
        d = await get_pending(target_uid)
        if not d:
            await cb.answer("⚠️ این درخواست منقضی شده!", show_alert=True)
            return
        original_caption = cb.message.caption or ""

        if action == "ok":
            ok = await take_region(d["region"], target_uid)
            if not ok:
                await cb.answer("⚠️ این منطقه الان گرفته شده!", show_alert=True)
                return
            await save_country(target_uid, d)
            await delete_pending(target_uid)
            temp.pop(target_uid, None)
            try:
                await context.bot.edit_message_caption(
                    chat_id=chat_id, message_id=msg_id,
                    caption=original_caption + "\n\n✅ *تأیید شد*",
                    parse_mode="Markdown",
                )
            except Exception:
                pass
            try:
                await context.bot.send_message(
                    target_uid,
                    f"🎉 تبریک! کشور *{d['name']}* تأیید شد.\n📍 منطقه: {d['region']}",
                    parse_mode="Markdown",
                )
            except Exception:
                pass
        else:
            await delete_pending(target_uid)
            temp.pop(target_uid, None)
            try:
                await context.bot.edit_message_caption(
                    chat_id=chat_id, message_id=msg_id,
                    caption=original_caption + "\n\n❌ *رد شد*",
                    parse_mode="Markdown",
                )
            except Exception:
                pass
            try:
                await context.bot.send_message(
                    target_uid,
                    "❌ متأسفانه درخواست کشورت رد شد.\n"
                    "می‌توانی دوباره با /start فرم پر کنی.",
                )
            except Exception:
                pass
        return


async def show_country_list(chat_id, msg_id, context, page, status):
    per_page = 5
    offset = page * per_page

    if status == "banned":
        all_list = await get_banned_countries()
    else:
        all_list = await get_all_countries()

    page_list = all_list[offset:offset + per_page]

    if not page_list:
        text = "🚫 هیچ کشور مسدودی وجود ندارد." if status == "banned" else "📋 هیچ کشوری ثبت نشده."
        await context.bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=text)
        return

    text = "🚫 *کشورهای مسدود:*\n\n" if status == "banned" else "📋 *لیست کشورها:*\n\n"
    buttons = []

    for c in page_list:
        icon = "✅" if c["status"] == "approved" else "🚫" if c["status"] == "banned" else "⏳"
        text += f"{icon} *{c['name']}* — {c['gov']}\n📍 منطقه: {c['region']}\n\n"
        buttons.append([InlineKeyboardButton(f"🔍 {c['name']}", callback_data=f"adm_view_{c['user_id']}")])

    prefix = "banned" if status == "banned" else "list"
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ قبلی", callback_data=f"adm_{prefix}_{page - 1}"))
    nav.append(InlineKeyboardButton("🔙 پنل", callback_data="adm_panel"))
    if offset + per_page < len(all_list):
        nav.append(InlineKeyboardButton("➡️ بعدی", callback_data=f"adm_{prefix}_{page + 1}"))
    buttons.append(nav)

    try:
        await context.bot.edit_message_text(
            chat_id=chat_id, message_id=msg_id,
            text=text, parse_mode="Markdown", reply_markup=kb(buttons),
        )
    except Exception:
        pass


async def show_country_detail(chat_id, msg_id, context, target_uid):
    c = await get_country(target_uid)
    if not c:
        await context.bot.edit_message_text(
            chat_id=chat_id, message_id=msg_id, text="❌ کشور پیدا نشد.",
        )
        return

    status_text = ("✅ فعال" if c["status"] == "approved"
                   else "🚫 مسدود" if c["status"] == "banned"
                   else "⏳ در انتظار")

    text = (
        f"🏛️ *{c['name']}*\n\n"
        f"👤 رهبر: {c['leader']}\n"
        f"🎂 سن: {c['age']} سال\n"
        f"⏳ مدت حکومت: {c['reign']}\n"
        f"⚙️ حکومت: {c['gov']}\n"
        f"🏛️ نظام: {c['gov_sub']}\n"
        f"☪️ دین: {c['religion']} — {c['rel_sub']}\n"
        f"🏭 تخصص: {c['expert']}\n"
        f"📍 منطقه: {c['region']}\n"
        f"😊 رضایت مردمی: {c['happiness']}٪\n"
        f"🔬 علم: {c['science']}\n"
        f"💰 اقتصاد: {c.get('economy', 0)}\n"
        f"🪖 ارتش: {c.get('army', 0)}\n"
        f"⚠️ شورش: {c.get('revolt', 0)}٪\n"
        f"📌 وضعیت: {status_text}\n\n"
        f"👤 کاربر: @{c.get('username', '')}\n🆔 آیدی: `{c['user_id']}`"
    )

    buttons = []
    if c["status"] == "banned":
        buttons.append([InlineKeyboardButton("✅ رفع مسدودی", callback_data=f"adm_unban_{target_uid}")])
    else:
        buttons.append([InlineKeyboardButton("🚫 مسدود کردن", callback_data=f"adm_ban_{target_uid}")])
    buttons.append([InlineKeyboardButton("🗑️ حذف کشور", callback_data=f"adm_del_{target_uid}")])
    buttons.append([InlineKeyboardButton("🔙 بازگشت به لیست", callback_data="adm_list_0")])

    try:
        await context.bot.edit_message_text(
            chat_id=chat_id, message_id=msg_id,
            text=text, parse_mode="Markdown", reply_markup=kb(buttons),
        )
    except Exception:
        pass


async def show_regions_status(chat_id, msg_id, context):
    taken = await get_regions()
    text = "🗺️ *وضعیت مناطق:*\n\n"
    buttons, row = [], []

    for code in REGIONS:
        if code in taken:
            text += f"🔒 {code} — گرفته شده\n"
            row.append(InlineKeyboardButton(f"🔓 {code}", callback_data=f"adm_free_{code}"))
        else:
            text += f"🟢 {code} — آزاد\n"
            row.append(InlineKeyboardButton(f"🟢 {code}", callback_data="adm_noop"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    buttons.append([InlineKeyboardButton("🔙 پنل", callback_data="adm_panel")])

    try:
        await context.bot.edit_message_text(
            chat_id=chat_id, message_id=msg_id,
            text=text, parse_mode="Markdown", reply_markup=kb(buttons),
        )
    except Exception:
        pass


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    uid = msg.from_user.id
    text = (msg.text or "").strip()
    chat_id = msg.chat.id

    if uid in banned_users and uid != ADMIN_ID:
        return

    if check_spam(uid) and uid != ADMIN_ID:
        await context.bot.send_message(chat_id, "🚫 اسپم! مسدود شدی.")
        await add_spam_ban(uid)
        return

    t = temp.get(uid)
    if not t:
        return

    if t.get("step") == "NAME":
        if len(text) < 3 or len(text) > 25:
            await context.bot.send_message(chat_id, "❌ نام کشور باید بین ۳ تا ۲۵ حرف باشد. دوباره بنویس:")
            return
        all_c = await get_all_countries()
        for c in all_c:
            if c["name"] == text:
                await context.bot.send_message(chat_id, "❌ این نام قبلاً استفاده شده. نام دیگری بنویس:")
                return
        t["name"] = text
        t["step"] = "LEADER"
        await context.bot.send_message(chat_id, "👤 *نام رهبر* را بنویس:", parse_mode="Markdown")
        return

    if t.get("step") == "LEADER":
        if len(text) < 2:
            await context.bot.send_message(chat_id, "❌ نام خیلی کوتاهه. دوباره بنویس:")
            return
        t["leader"] = text
        t["step"] = "AGE"
        await context.bot.send_message(
            chat_id, "🎂 *سن رهبر* را بنویس (بین ۳۵ تا ۴۵):", parse_mode="Markdown",
        )
        return

    if t.get("step") == "AGE":
        if not text.isdigit():
            await context.bot.send_message(chat_id, "❌ فقط عدد بنویس (بین ۳۵ تا ۴۵):")
            return
        age = int(text)
        if age < 35 or age > 45:
            await context.bot.send_message(chat_id, "❌ سن باید بین ۳۵ تا ۴۵ باشد. دوباره بنویس:")
            return
        t["age"] = age
        t["step"] = "REIGN"
        rows = [
            [InlineKeyboardButton("⏳ ۵ سال", callback_data="reign_5")],
            [InlineKeyboardButton("⏳ ۱۰ سال", callback_data="reign_10")],
            [InlineKeyboardButton("⏳ ۲۰ سال", callback_data="reign_20")],
            [InlineKeyboardButton("⏳ ۳۰ سال", callback_data="reign_30")],
            [InlineKeyboardButton("♾️ مادام‌العمر", callback_data="reign_life")],
        ]
        await context.bot.send_message(
            chat_id, "⏳ *مدت حکومت رهبر* را انتخاب کن:",
            parse_mode="Markdown", reply_markup=kb(rows),
        )
        return

    if t.get("step") == "BAN_REASON" and uid == ADMIN_ID:
        target_uid = t.get("targetUid")
        await set_country_status(target_uid, "banned", text)
        temp.pop(uid, None)
        await context.bot.send_message(
            chat_id, f"🚫 کشور با موفقیت مسدود شد.\n📝 دلیل: {text}",
        )
        try:
            await context.bot.send_message(
                target_uid, f"🚫 کشور شما توسط ادمین مسدود شد.\n📝 دلیل: {text}",
            )
        except Exception:
            pass
        return


async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    uid = msg.from_user.id
    t = temp.get(uid)

    if not t or t.get("step") != "FLAG":
        return

    file_id = msg.photo[-1].file_id
    t["flag_id"] = file_id
    t["step"] = "CONFIRM"

    text = (
        f"🏛️ کشور: *{t['name']}*\n"
        f"👤 رهبر: {t['leader']}\n"
        f"🎂 سن: {t['age']} سال\n"
        f"⏳ مدت حکومت: {t['reign']}\n"
        f"⚙️ حکومت: {t['gov']}\n"
        f"🏛️ نظام حکومتی: {t['gov_sub']}\n"
        f"☪️ دین: {t['religion']} — {t['rel_sub']}\n"
        f"🏭 تخصص: {t['expert']}\n"
        f"📍 منطقه: {t['region']}\n"
        f"😊 رضایت مردمی: {t['happiness']}٪\n"
        f"🔬 علم: {t['science']}\n\n"
        f"آیا اطلاعات صحیح است؟"
    )

    rows = [
        [InlineKeyboardButton("✅ ثبت نهایی", callback_data="confirm_yes")],
        [InlineKeyboardButton("🔄 شروع مجدد", callback_data="confirm_restart")],
    ]

    await context.bot.send_photo(
        chat_id=msg.chat.id, photo=file_id,
        caption=text, parse_mode="Markdown", reply_markup=kb(rows),
    )


async def post_init(application):
    await init_db()


def main():
    app = (
        Application.builder()
        .token(TOKEN)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    render_host = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
    if render_host:
        port = int(os.environ.get("PORT", 8443))
        app.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path=TOKEN,
            webhook_url=f"https://{render_host}/{TOKEN}",
            drop_pending_updates=True,
        )
    else:
        app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
