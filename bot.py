import asyncio
import logging
import sqlite3
import os
from datetime import datetime, timedelta, date
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command
import aiohttp

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "")
ESKIZ_EMAIL = os.getenv("ESKIZ_EMAIL", "")
ESKIZ_PASSWORD = os.getenv("ESKIZ_PASSWORD", "")
ESKIZ_SENDER = os.getenv("ESKIZ_SENDER", "4546")

DB = "debts.db"


def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS debtors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            amount REAL NOT NULL,
            due_date TEXT NOT NULL,
            notes TEXT DEFAULT '',
            is_paid INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            debtor_id INTEGER,
            amount REAL NOT NULL,
            paid_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


init_db()


class AddDebtor(StatesGroup):
    name = State()
    phone = State()
    amount = State()
    due_date = State()
    notes = State()


class PartialPay(StatesGroup):
    amount = State()


async def get_eskiz_token():
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://notify.eskiz.uz/api/auth/login",
            json={"email": ESKIZ_EMAIL, "password": ESKIZ_PASSWORD}
        ) as resp:
            data = await resp.json()
            return data.get("data", {}).get("token")


async def send_sms(phone: str, message: str) -> bool:
    if not ESKIZ_EMAIL or not ESKIZ_PASSWORD:
        return False
    try:
        token = await get_eskiz_token()
        if not token:
            return False
        phone = phone.replace("+", "").replace(" ", "").replace("-", "")
        if not phone.startswith("998"):
            phone = "998" + (phone[1:] if phone.startswith("0") else phone)
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://notify.eskiz.uz/api/message/sms/send",
                headers={"Authorization": f"Bearer {token}"},
                json={"mobile_phone": phone, "message": message, "from": ESKIZ_SENDER, "callback_url": ""}
            ) as resp:
                data = await resp.json()
                return data.get("status") == "waiting"
    except Exception as e:
        logging.error(f"SMS error: {e}")
        return False


def format_amount(amount):
    return f"{amount:,.0f} so'm"


def format_date(date_str):
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").strftime("%d.%m.%Y")
    except Exception:
        return date_str


def days_until(date_str):
    try:
        return (datetime.strptime(date_str, "%Y-%m-%d").date() - date.today()).days
    except Exception:
        return None


def get_paid_total(debtor_id):
    conn = get_db()
    row = conn.execute("SELECT SUM(amount) as t FROM payments WHERE debtor_id=?", (debtor_id,)).fetchone()
    conn.close()
    return row["t"] or 0


def status_text(days):
    if days is None:
        return "❓ Noma'lum"
    if days < 0:
        return f"🔴 Muddati o'tgan ({abs(days)} kun)"
    if days == 0:
        return "🔴 Bugun muddati tugaydi!"
    if days <= 3:
        return f"🟡 {days} kundan keyin"
    return f"🟢 {days} kun qoldi"


def debtor_info_text(d):
    days = days_until(d["due_date"])
    paid_total = get_paid_total(d["id"])
    remaining = d["amount"] - paid_total

    text = (
        f"👤 <b>{d['name']}</b>\n"
        f"📱 Telefon: {d['phone']}\n"
        f"💵 Umumiy qarz: {format_amount(d['amount'])}\n"
    )
    if paid_total > 0:
        text += f"✅ To'langan: {format_amount(paid_total)}\n"
        text += f"🔸 Qolgan: {format_amount(remaining)}\n"
    text += (
        f"📅 Muddat: {format_date(d['due_date'])}\n"
        f"📌 Holat: {('✅ To\'langan' if d['is_paid'] else status_text(days))}\n"
    )
    if d["notes"]:
        text += f"📝 Izoh: {d['notes']}\n"
    return text


def main_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Qarzdor qo'shish", callback_data="add_debtor")],
        [InlineKeyboardButton(text="📋 Qarzdorlar ro'yxati", callback_data="list_debtors")],
        [InlineKeyboardButton(text="📊 Statistika", callback_data="stats")],
    ])


def debtor_kb(debtor_id, is_paid):
    buttons = []
    if not is_paid:
        buttons.append([
            InlineKeyboardButton(text="✅ To'langan", callback_data=f"paid_{debtor_id}"),
            InlineKeyboardButton(text="💰 Qisman to'lov", callback_data=f"partial_{debtor_id}"),
        ])
        buttons.append([
            InlineKeyboardButton(text="📱 SMS yuborish", callback_data=f"sms_{debtor_id}"),
        ])
    buttons.append([
        InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"delete_{debtor_id}"),
        InlineKeyboardButton(text="◀️ Orqaga", callback_data="list_debtors"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
dp = Dispatcher(storage=MemoryStorage())


@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "🏦 <b>Qarzdorlik Nazorat Tizimi</b>\n\n"
        "Salom! Men sizning qarz va nasiya hisobingizni yuritaman.\n"
        "Har kuni muddati yaqinlashayotgan qarzlar haqida xabardor qilaman.",
        reply_markup=main_menu_kb()
    )


@dp.callback_query(F.data == "menu")
async def cb_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text(
        "🏦 <b>Qarzdorlik Nazorat Tizimi</b>\n\nAsosiy menyu:",
        reply_markup=main_menu_kb()
    )


@dp.callback_query(F.data == "add_debtor")
async def cb_add_debtor(call: CallbackQuery, state: FSMContext):
    await state.set_state(AddDebtor.name)
    await call.message.edit_text("👤 Qarzdorning <b>ismini</b> kiriting:")


@dp.message(AddDebtor.name)
async def add_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await state.set_state(AddDebtor.phone)
    await message.answer("📱 Telefon raqamini kiriting:\n(masalan: +998901234567)")


@dp.message(AddDebtor.phone)
async def add_phone(message: Message, state: FSMContext):
    await state.update_data(phone=message.text.strip())
    await state.set_state(AddDebtor.amount)
    await message.answer("💵 Qarz miqdorini kiriting (so'mda):\n(masalan: 500000)")


@dp.message(AddDebtor.amount)
async def add_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.replace(" ", "").replace(",", ""))
    except ValueError:
        await message.answer("❌ Noto'g'ri format. Raqam kiriting (masalan: 500000):")
        return
    await state.update_data(amount=amount)
    await state.set_state(AddDebtor.due_date)
    await message.answer("📅 Qaytarish sanasini kiriting:\n(masalan: 25.06.2025)")


@dp.message(AddDebtor.due_date)
async def add_due_date(message: Message, state: FSMContext):
    date_str = None
    for fmt in ["%d.%m.%Y", "%d/%m/%Y", "%Y-%m-%d"]:
        try:
            date_str = datetime.strptime(message.text.strip(), fmt).strftime("%Y-%m-%d")
            break
        except ValueError:
            continue
    if not date_str:
        await message.answer("❌ Noto'g'ri sana. Qaytadan kiriting (masalan: 25.06.2025):")
        return
    await state.update_data(due_date=date_str)
    await state.set_state(AddDebtor.notes)
    await message.answer("📝 Izoh qo'shing (ixtiyoriy):\n(O'tkazib yuborish uchun — tire \"-\" yuboring)")


@dp.message(AddDebtor.notes)
async def add_notes(message: Message, state: FSMContext):
    data = await state.get_data()
    notes = "" if message.text.strip() == "-" else message.text.strip()

    conn = get_db()
    conn.execute(
        "INSERT INTO debtors (name, phone, amount, due_date, notes) VALUES (?,?,?,?,?)",
        (data["name"], data["phone"], data["amount"], data["due_date"], notes)
    )
    conn.commit()
    conn.close()
    await state.clear()

    days = days_until(data["due_date"])
    days_text = f"{days} kun qoldi" if days and days > 0 else "muddati yaqin!"

    await message.answer(
        f"✅ <b>Qarzdor qo'shildi!</b>\n\n"
        f"👤 {data['name']}\n"
        f"📱 {data['phone']}\n"
        f"💵 {format_amount(data['amount'])}\n"
        f"📅 {format_date(data['due_date'])} ({days_text})",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 Ro'yxatga qaytish", callback_data="list_debtors")],
            [InlineKeyboardButton(text="🏠 Asosiy menyu", callback_data="menu")],
        ])
    )


@dp.callback_query(F.data == "list_debtors")
async def cb_list_debtors(call: CallbackQuery, state: FSMContext):
    await state.clear()
    conn = get_db()
    debtors = conn.execute("SELECT * FROM debtors WHERE is_paid=0 ORDER BY due_date ASC").fetchall()
    conn.close()

    if not debtors:
        await call.message.edit_text(
            "📋 Hozircha faol qarzdorlar yo'q.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="➕ Qarzdor qo'shish", callback_data="add_debtor")],
                [InlineKeyboardButton(text="🏠 Asosiy menyu", callback_data="menu")],
            ])
        )
        return

    buttons = []
    for d in debtors:
        days = days_until(d["due_date"])
        icon = "🔴" if (days is not None and days < 0) else ("🟡" if (days is not None and days <= 3) else "🟢")
        label = f"{icon} {d['name']} — {format_amount(d['amount'])} ({format_date(d['due_date'])})"
        buttons.append([InlineKeyboardButton(text=label, callback_data=f"view_{d['id']}")])

    buttons.append([InlineKeyboardButton(text="✅ To'langan qarzlar", callback_data="list_paid")])
    buttons.append([InlineKeyboardButton(text="🏠 Asosiy menyu", callback_data="menu")])

    await call.message.edit_text(
        f"📋 <b>Faol qarzdorlar:</b> {len(debtors)} ta",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )


@dp.callback_query(F.data == "list_paid")
async def cb_list_paid(call: CallbackQuery):
    conn = get_db()
    debtors = conn.execute(
        "SELECT * FROM debtors WHERE is_paid=1 ORDER BY created_at DESC LIMIT 20"
    ).fetchall()
    conn.close()

    if not debtors:
        await call.message.edit_text(
            "📋 To'langan qarzlar yo'q.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Orqaga", callback_data="list_debtors")],
            ])
        )
        return

    buttons = [[InlineKeyboardButton(text=f"✅ {d['name']} — {format_amount(d['amount'])}", callback_data=f"view_{d['id']}")] for d in debtors]
    buttons.append([InlineKeyboardButton(text="◀️ Orqaga", callback_data="list_debtors")])

    await call.message.edit_text(
        f"✅ <b>To'langan qarzlar:</b> {len(debtors)} ta",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )


@dp.callback_query(F.data.startswith("view_"))
async def cb_view_debtor(call: CallbackQuery):
    debtor_id = int(call.data.split("_")[1])
    conn = get_db()
    d = conn.execute("SELECT * FROM debtors WHERE id=?", (debtor_id,)).fetchone()
    conn.close()
    if not d:
        await call.answer("Topilmadi!")
        return
    await call.message.edit_text(debtor_info_text(d), reply_markup=debtor_kb(d["id"], d["is_paid"]))


@dp.callback_query(F.data.startswith("paid_"))
async def cb_mark_paid(call: CallbackQuery):
    debtor_id = int(call.data.split("_")[1])
    conn = get_db()
    d = conn.execute("SELECT * FROM debtors WHERE id=?", (debtor_id,)).fetchone()
    conn.execute("UPDATE debtors SET is_paid=1 WHERE id=?", (debtor_id,))
    conn.commit()
    conn.close()
    await call.message.edit_text(
        f"✅ <b>{d['name']}</b> qarz to'langan deb belgilandi!\n💵 {format_amount(d['amount'])}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 Ro'yxat", callback_data="list_debtors")],
            [InlineKeyboardButton(text="🏠 Menyu", callback_data="menu")],
        ])
    )


@dp.callback_query(F.data.startswith("partial_"))
async def cb_partial_pay(call: CallbackQuery, state: FSMContext):
    debtor_id = int(call.data.split("_")[1])
    conn = get_db()
    d = conn.execute("SELECT * FROM debtors WHERE id=?", (debtor_id,)).fetchone()
    conn.close()

    paid_total = get_paid_total(debtor_id)
    remaining = d["amount"] - paid_total

    await state.set_state(PartialPay.amount)
    await state.update_data(debtor_id=debtor_id)
    await call.message.edit_text(
        f"💰 <b>Qisman to'lov</b>\n\n"
        f"👤 {d['name']}\n"
        f"🔸 Qolgan qarz: {format_amount(remaining)}\n\n"
        f"To'langan miqdorni kiriting:"
    )


@dp.message(PartialPay.amount)
async def process_partial_pay(message: Message, state: FSMContext):
    try:
        amount = float(message.text.replace(" ", "").replace(",", ""))
    except ValueError:
        await message.answer("❌ Noto'g'ri format. Raqam kiriting:")
        return

    data = await state.get_data()
    debtor_id = data["debtor_id"]

    conn = get_db()
    d = conn.execute("SELECT * FROM debtors WHERE id=?", (debtor_id,)).fetchone()
    conn.execute("INSERT INTO payments (debtor_id, amount) VALUES (?,?)", (debtor_id, amount))
    conn.commit()

    paid_total = get_paid_total(debtor_id)
    if paid_total >= d["amount"]:
        conn.execute("UPDATE debtors SET is_paid=1 WHERE id=?", (debtor_id,))
        conn.commit()
    conn.close()
    await state.clear()

    remaining = max(0, d["amount"] - paid_total)
    text = f"✅ To'lov qabul qilindi!\n💵 Miqdor: {format_amount(amount)}\n"
    text += "🎉 Qarz to'liq uzildi!" if remaining == 0 else f"🔸 Qolgan qarz: {format_amount(remaining)}"

    await message.answer(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👤 Qarzdorga qaytish", callback_data=f"view_{debtor_id}")],
            [InlineKeyboardButton(text="📋 Ro'yxat", callback_data="list_debtors")],
        ])
    )


@dp.callback_query(F.data.startswith("sms_"))
async def cb_send_sms(call: CallbackQuery):
    debtor_id = int(call.data.split("_")[1])
    conn = get_db()
    d = conn.execute("SELECT * FROM debtors WHERE id=?", (debtor_id,)).fetchone()
    conn.close()

    paid_total = get_paid_total(debtor_id)
    remaining = d["amount"] - paid_total
    days = days_until(d["due_date"])

    if days is not None and days < 0:
        days_text = f"Muddatingiz {abs(days)} kun oldin o'tdi."
    elif days == 0:
        days_text = "Bugun muddat tugaydi."
    elif days is not None:
        days_text = f"{days} kun qoldi."
    else:
        days_text = ""

    sms_text = (
        f"Salom {d['name']}! "
        f"Sizda {format_amount(remaining)} qarz bor. "
        f"Qaytarish muddati: {format_date(d['due_date'])}. "
        f"{days_text}"
    )

    await call.answer("SMS yuborilmoqda...")
    success = await send_sms(d["phone"], sms_text)

    if success:
        await call.message.answer(f"✅ SMS yuborildi!\n📱 {d['phone']}\n\n📝 {sms_text}")
    else:
        await call.message.answer(
            f"❌ SMS yuborilmadi (Eskiz.uz sozlanmagan).\n\n"
            f"📝 SMS matni:\n<code>{sms_text}</code>\n\n"
            f"SMS yuborish uchun ESKIZ_EMAIL va ESKIZ_PASSWORD ni sozlang."
        )


@dp.callback_query(F.data.startswith("delete_"))
async def cb_delete_debtor(call: CallbackQuery):
    debtor_id = int(call.data.split("_")[1])
    conn = get_db()
    d = conn.execute("SELECT * FROM debtors WHERE id=?", (debtor_id,)).fetchone()
    conn.execute("DELETE FROM debtors WHERE id=?", (debtor_id,))
    conn.execute("DELETE FROM payments WHERE debtor_id=?", (debtor_id,))
    conn.commit()
    conn.close()
    await call.message.edit_text(
        f"🗑 <b>{d['name']}</b> o'chirildi.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 Ro'yxat", callback_data="list_debtors")],
        ])
    )


@dp.callback_query(F.data == "stats")
async def cb_stats(call: CallbackQuery):
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) as c, SUM(amount) as s FROM debtors WHERE is_paid=0").fetchone()
    paid_count = conn.execute("SELECT COUNT(*) as c FROM debtors WHERE is_paid=1").fetchone()["c"]
    overdue = conn.execute("SELECT COUNT(*) as c FROM debtors WHERE is_paid=0 AND due_date < date('now')").fetchone()["c"]
    due_soon = conn.execute("SELECT COUNT(*) as c FROM debtors WHERE is_paid=0 AND due_date BETWEEN date('now') AND date('now','+3 days')").fetchone()["c"]
    conn.close()

    await call.message.edit_text(
        f"📊 <b>Statistika</b>\n\n"
        f"👥 Faol qarzdorlar: {total['c']} ta\n"
        f"💵 Umumiy qarz: {format_amount(total['s'] or 0)}\n"
        f"🔴 Muddati o'tgan: {overdue} ta\n"
        f"🟡 3 kunda tugaydi: {due_soon} ta\n"
        f"✅ To'langan: {paid_count} ta",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏠 Asosiy menyu", callback_data="menu")],
        ])
    )


async def daily_check(bot: Bot):
    while True:
        now = datetime.now()
        next_run = now.replace(hour=9, minute=0, second=0, microsecond=0)
        if now >= next_run:
            next_run += timedelta(days=1)
        await asyncio.sleep((next_run - now).total_seconds())

        if not ADMIN_CHAT_ID:
            continue

        conn = get_db()
        overdue = conn.execute(
            "SELECT * FROM debtors WHERE is_paid=0 AND due_date < date('now') ORDER BY due_date ASC"
        ).fetchall()
        due_today = conn.execute(
            "SELECT * FROM debtors WHERE is_paid=0 AND due_date = date('now')"
        ).fetchall()
        due_soon = conn.execute(
            "SELECT * FROM debtors WHERE is_paid=0 AND due_date BETWEEN date('now','+1 day') AND date('now','+3 days') ORDER BY due_date ASC"
        ).fetchall()
        conn.close()

        if not overdue and not due_today and not due_soon:
            continue

        msg = "🔔 <b>Kunlik qarz hisoboti</b>\n\n"
        if due_today:
            msg += "🔴 <b>BUGUN muddati tugaydi:</b>\n"
            for d in due_today:
                msg += f"  • {d['name']} — {format_amount(d['amount'])} ({d['phone']})\n"
            msg += "\n"
        if overdue:
            msg += "⛔ <b>Muddati o'tgan:</b>\n"
            for d in overdue:
                msg += f"  • {d['name']} — {format_amount(d['amount'])} ({abs(days_until(d['due_date']))} kun)\n"
            msg += "\n"
        if due_soon:
            msg += "🟡 <b>3 kun ichida tugaydi:</b>\n"
            for d in due_soon:
                msg += f"  • {d['name']} — {format_amount(d['amount'])} ({days_until(d['due_date'])} kun)\n"

        try:
            await bot.send_message(ADMIN_CHAT_ID, msg)
        except Exception as e:
            logging.error(f"Notification error: {e}")


async def main():
    asyncio.create_task(daily_check(bot))
    logging.info("Qarzdorlik boti ishga tushdi!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
