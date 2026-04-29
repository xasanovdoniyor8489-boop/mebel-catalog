import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.fsm.storage.memory import MemoryStorage
import os

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN")
WEB_APP_URL = os.getenv("WEB_APP_URL", "https://your-app.railway.app/catalog")

async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    @dp.message(F.text == "/start")
    async def start(message: Message):
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text="🛍️ Katalogni ochish",
                web_app=WebAppInfo(url=WEB_APP_URL)
            )
        ]])
        await message.answer(
            "👋 Xush kelibsiz!\n\n"
            "🪑 Bizning mebel katalogimizga xush kelibsiz!\n"
            "Pastdagi tugmani bosib katalogni ko'ring.",
            reply_markup=kb
        )

    print("✅ Bot ishga tushdi!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
