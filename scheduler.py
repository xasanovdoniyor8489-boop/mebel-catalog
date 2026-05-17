"""
Qarzdorlik SMS Xabarnoma Tizimi
- Google Sheets dan o'qiydi (public link)
- Eskiz.uz orqali SMS yuboradi
- Har kuni soat 9:00 da ishlaydi
"""

import asyncio
import logging
import sqlite3
import os
import csv
import io
from datetime import datetime, timedelta, date

import aiohttp

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "")          # Google Sheets ID
ESKIZ_EMAIL = os.getenv("ESKIZ_EMAIL", "")
ESKIZ_PASSWORD = os.getenv("ESKIZ_PASSWORD", "")
ESKIZ_SENDER = os.getenv("ESKIZ_SENDER", "4546")
NOTIFY_DAYS = [3, 1, 0]                               # 3 kun, 1 kun, bugun
SEND_OVERDUE = True                                   # Muddati o'tganlarga ham SMS

LOG_DB = "sms_log.db"


def init_log_db():
    conn = sqlite3.connect(LOG_DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sent_sms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT NOT NULL,
            type TEXT NOT NULL,
            sent_date TEXT NOT NULL,
            UNIQUE(phone, type, sent_date)
        )
    """)
    conn.commit()
    conn.close()


def already_sent(phone: str, sms_type: str) -> bool:
    today = date.today().isoformat()
    conn = sqlite3.connect(LOG_DB)
    row = conn.execute(
        "SELECT 1 FROM sent_sms WHERE phone=? AND type=? AND sent_date=?",
        (phone, sms_type, today)
    ).fetchone()
    conn.close()
    return row is not None


def mark_sent(phone: str, sms_type: str):
    today = date.today().isoformat()
    conn = sqlite3.connect(LOG_DB)
    try:
        conn.execute(
            "INSERT OR IGNORE INTO sent_sms (phone, type, sent_date) VALUES (?,?,?)",
            (phone, sms_type, today)
        )
        conn.commit()
    finally:
        conn.close()


def format_amount(amount):
    try:
        return f"{float(amount):,.0f} so'm"
    except Exception:
        return f"{amount} so'm"


def format_date(date_str):
    for fmt in ["%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y"]:
        try:
            return datetime.strptime(date_str, fmt).strftime("%d.%m.%Y")
        except ValueError:
            continue
    return date_str


def parse_date(date_str):
    for fmt in ["%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y"]:
        try:
            return datetime.strptime(date_str.strip(), fmt).date()
        except ValueError:
            continue
    return None


def normalize_phone(phone: str) -> str:
    phone = phone.replace("+", "").replace(" ", "").replace("-", "").strip()
    if phone.startswith("0"):
        phone = "998" + phone[1:]
    elif not phone.startswith("998"):
        phone = "998" + phone
    return phone


async def get_eskiz_token(session: aiohttp.ClientSession) -> str | None:
    try:
        async with session.post(
            "https://notify.eskiz.uz/api/auth/login",
            json={"email": ESKIZ_EMAIL, "password": ESKIZ_PASSWORD}
        ) as resp:
            data = await resp.json()
            return data.get("data", {}).get("token")
    except Exception as e:
        logging.error(f"Eskiz login xatosi: {e}")
        return None


async def send_sms(session: aiohttp.ClientSession, token: str, phone: str, message: str) -> bool:
    try:
        normalized = normalize_phone(phone)
        async with session.post(
            "https://notify.eskiz.uz/api/message/sms/send",
            headers={"Authorization": f"Bearer {token}"},
            json={"mobile_phone": normalized, "message": message, "from": ESKIZ_SENDER, "callback_url": ""}
        ) as resp:
            data = await resp.json()
            return data.get("status") == "waiting"
    except Exception as e:
        logging.error(f"SMS yuborish xatosi ({phone}): {e}")
        return False


async def read_sheet() -> list[dict]:
    if not SHEET_ID:
        logging.error("GOOGLE_SHEET_ID sozlanmagan!")
        return []

    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=0"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    logging.error(f"Sheet o'qishda xato: HTTP {resp.status}")
                    return []
                content = await resp.text()
    except Exception as e:
        logging.error(f"Sheet o'qishda xato: {e}")
        return []

    debtors = []
    reader = csv.DictReader(io.StringIO(content))
    for i, row in enumerate(reader, start=2):
        # Ustun nomlari: Ism, Telefon, Summa, Muddat, Izoh, Tolandi
        name = (row.get("Ism") or row.get("ism") or "").strip()
        phone = (row.get("Telefon") or row.get("telefon") or "").strip()
        amount = (row.get("Summa") or row.get("summa") or "").strip()
        due_raw = (row.get("Muddat") or row.get("muddat") or "").strip()
        notes = (row.get("Izoh") or row.get("izoh") or "").strip()
        paid = (row.get("Tolandi") or row.get("tolandi") or row.get("To'landi") or "").strip().lower()

        if not name or not phone or not due_raw:
            continue
        if paid in ("ha", "yes", "1", "true", "+"):
            continue

        due_date = parse_date(due_raw)
        if not due_date:
            logging.warning(f"{i}-qator: '{due_raw}' sana noto'g'ri formatda")
            continue

        debtors.append({
            "name": name,
            "phone": phone,
            "amount": amount,
            "due_date": due_date,
            "notes": notes,
        })

    logging.info(f"Sheet dan {len(debtors)} ta faol qarzdor o'qildi")
    return debtors


def build_sms(debtor: dict, sms_type: str) -> str:
    name = debtor["name"]
    amount = format_amount(debtor["amount"])
    due = format_date(debtor["due_date"].strftime("%d.%m.%Y"))

    if sms_type == "3kun":
        return f"Salom {name}! Eslatma: {amount} qarzingiz 3 kun ichida ({due}) qaytarilishi kerak."
    if sms_type == "1kun":
        return f"Salom {name}! Ertaga ({due}) {amount} qarzingizni qaytarish muddati tugaydi."
    if sms_type == "bugun":
        return f"Salom {name}! Bugun ({due}) {amount} qarzingizni qaytarish muddati. Iltimos, to'lang."
    if sms_type == "kechikkan":
        overdue_days = (date.today() - debtor["due_date"]).days
        return f"Salom {name}! {amount} qarzingiz muddati {overdue_days} kun oldin ({due}) o'tdi. Iltimos, to'lang."
    return ""


async def run_daily_check():
    init_log_db()
    debtors = await read_sheet()
    if not debtors:
        return

    today = date.today()
    to_send = []

    for d in debtors:
        days_left = (d["due_date"] - today).days

        if days_left == 3:
            sms_type = "3kun"
        elif days_left == 1:
            sms_type = "1kun"
        elif days_left == 0:
            sms_type = "bugun"
        elif days_left < 0 and SEND_OVERDUE:
            sms_type = "kechikkan"
        else:
            continue

        if already_sent(d["phone"], sms_type):
            logging.info(f"SMS allaqachon yuborilgan: {d['name']} ({sms_type})")
            continue

        to_send.append((d, sms_type))

    if not to_send:
        logging.info("Bugun yuborish kerak bo'lgan SMS yo'q")
        return

    if not ESKIZ_EMAIL or not ESKIZ_PASSWORD:
        logging.error("ESKIZ_EMAIL yoki ESKIZ_PASSWORD sozlanmagan!")
        for d, sms_type in to_send:
            msg = build_sms(d, sms_type)
            logging.info(f"[TEST] {d['phone']}: {msg}")
        return

    async with aiohttp.ClientSession() as session:
        token = await get_eskiz_token(session)
        if not token:
            logging.error("Eskiz token olishda xato!")
            return

        for d, sms_type in to_send:
            message = build_sms(d, sms_type)
            success = await send_sms(session, token, d["phone"], message)
            if success:
                mark_sent(d["phone"], sms_type)
                logging.info(f"✅ SMS yuborildi: {d['name']} ({d['phone']}) — {sms_type}")
            else:
                logging.error(f"❌ SMS yuborilmadi: {d['name']} ({d['phone']})")

            await asyncio.sleep(0.5)  # rate limit


async def main():
    init_log_db()
    logging.info("SMS Xabarnoma Tizimi ishga tushdi")

    while True:
        now = datetime.now()
        next_run = now.replace(hour=9, minute=0, second=0, microsecond=0)
        if now >= next_run:
            next_run += timedelta(days=1)

        wait_seconds = (next_run - now).total_seconds()
        logging.info(f"Keyingi tekshiruv: {next_run.strftime('%d.%m.%Y %H:%M')} ({int(wait_seconds/3600)} soatdan keyin)")

        await asyncio.sleep(wait_seconds)
        await run_daily_check()


if __name__ == "__main__":
    asyncio.run(main())
