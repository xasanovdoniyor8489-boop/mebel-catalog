# Qarzdorlik SMS Xabarnoma Tizimi — Sozlash

## 1. Google Sheets tayyorlash

1. [sheets.google.com](https://sheets.google.com) da yangi jadval oching
2. **Birinchi qatorda** quyidagi ustun nomlarini yozing (aynan shunday):

| A | B | C | D | E | F |
|---|---|---|---|---|---|
| Ism | Telefon | Summa | Muddat | Izoh | Tolandi |

3. Ikkinchi qatordan boshlab ma'lumot kiriting:

| Ism | Telefon | Summa | Muddat | Izoh | Tolandi |
|---|---|---|---|---|---|
| Eshmat | +998901234567 | 500000 | 25.06.2025 | do'stdan qarz | |
| Toshmat | 998911234567 | 1200000 | 30.06.2025 | | ha |

- **Muddat formati:** KK.OO.YYYY (masalan: 25.06.2025)
- **Tolandi ustuni:** `ha` yozsangiz — o'sha qator o'tkazib yuboriladi

4. Ulashish: `Fayl → Ulashish → Havola orqali ulashing → Har kim ko'ra oladi`
5. Havola: `https://docs.google.com/spreadsheets/d/`**{SHEET_ID}**`/edit`
   - **{SHEET_ID}** — mana shu qismni oling

## 2. Eskiz.uz SMS akkaunti

1. [eskiz.uz](https://eskiz.uz) da ro'yxatdan o'ting
2. Email va parolni environment variable ga kiriting

## 3. Environment Variables (Render/Railway)

| O'zgaruvchi | Qiymat |
|---|---|
| `GOOGLE_SHEET_ID` | Sheets ID (yuqorida izohlanган) |
| `ESKIZ_EMAIL` | Eskiz.uz emailingiz |
| `ESKIZ_PASSWORD` | Eskiz.uz parolingiz |
| `ESKIZ_SENDER` | SMS jo'natuvchi nomi (default: 4546) |

## 4. SMS qachon ketadi?

- Muddat **3 kun** qolganda
- Muddat **1 kun** qolganda
- Muddat **kuni**
- Muddat **o'tgandan** keyin (har kuni)

Bir kunda bir xil SMS ikki marta yuborilmaydi.
