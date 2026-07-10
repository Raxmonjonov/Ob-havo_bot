import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone

import aiohttp
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")
WEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"
TIMEOUT = aiohttp.ClientTimeout(total=15)

dp = Dispatcher()

WEATHER_EMOJI = {
    "Clear": "☀️", "Clouds": "☁️", "Rain": "🌧", "Drizzle": "🌦",
    "Thunderstorm": "⛈", "Snow": "❄️", "Mist": "🌫", "Fog": "🌫", "Haze": "🌫",
}
POPULAR_CITIES = ["Toshkent", "Samarqand", "Buxoro", "Namangan", "Andijon", "Nukus"]


def cities_keyboard():
    builder = ReplyKeyboardBuilder()
    for city in POPULAR_CITIES:
        builder.button(text=city)
    builder.adjust(3)
    return builder.as_markup(resize_keyboard=True)


async def get_weather(city: str) -> dict | None:
    params = {"q": city, "appid": WEATHER_API_KEY, "units": "metric", "lang": "en"}
    try:
        async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
            async with session.get(WEATHER_URL, params=params) as resp:
                return await resp.json()
    except (aiohttp.ClientError, asyncio.TimeoutError):
        return None


def fmt_time(ts: int, tz_offset: int) -> str:
    return (datetime.fromtimestamp(ts, tz=timezone.utc) + timedelta(seconds=tz_offset)).strftime("%H:%M")


@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "🌤 <b>Ob-havo Bot</b>ga xush kelibsiz!\n\n"
        "Shahar nomini yozing yoki pastdagi tugmalardan tanlang.",
        reply_markup=cities_keyboard(),
    )


@dp.message(Command("help"))
async def help_cmd(message: Message):
    await message.answer(
        "🌤 <b>Ob-havo Bot</b> — yordam\n\n"
        "• Shahar nomini yozing → real vaqtli ob-havo\n"
        "• Tugmalardan mashhur shaharlarni tanlang\n"
        "• /start, /help"
    )


@dp.message(F.text)
async def weather(message: Message):
    if not WEATHER_API_KEY or WEATHER_API_KEY == "your_openweathermap_api_key":
        await message.answer("⚠️ WEATHER_API_KEY sozlanmagan. .env faylini tekshiring.")
        return

    await message.bot.send_chat_action(message.chat.id, "typing")
    data = await get_weather(message.text.strip())
    if data is None:
        await message.answer("🌐 Tarmoqda muammo. Birozdan so'ng qayta urinib ko'ring.")
        return
    if str(data.get("cod")) != "200":
        await message.answer("❌ Bunday shahar topilmadi. Nomini tekshirib qayta yozing.")
        return

    w = data["weather"][0]
    main = data.get("main", {})
    wind = data.get("wind", {})
    sys = data.get("sys", {})
    tz = data.get("timezone", 0)
    emoji = WEATHER_EMOJI.get(w.get("main"), "🌡")

    lines = [
        f"{emoji} <b>{data.get('name')}</b> ob-havosi",
        "",
        f"🌡 Harorat: <b>{round(main.get('temp', 0))}°C</b> (his: {round(main.get('feels_like', 0))}°C)",
        f"🔺 Maks: {round(main.get('temp_max', 0))}°C   🔻 Min: {round(main.get('temp_min', 0))}°C",
        f"📋 Holat: {w.get('description', '').capitalize()}",
        f"💧 Namlik: {main.get('humidity', '?')}%",
        f"🎚 Bosim: {main.get('pressure', '?')} hPa",
        f"💨 Shamol: {wind.get('speed', '?')} m/s",
    ]
    if sys.get("sunrise") and sys.get("sunset"):
        lines.append(f"🌅 {fmt_time(sys['sunrise'], tz)}   🌇 {fmt_time(sys['sunset'], tz)}")
    await message.answer("\n".join(lines))


async def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN topilmadi. .env faylini to'ldiring.")
    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
