import asyncio
import logging
import os

import aiohttp
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import Message
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")
WEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"

dp = Dispatcher()

WEATHER_EMOJI = {
    "Clear": "☀️",
    "Clouds": "☁️",
    "Rain": "🌧",
    "Drizzle": "🌦",
    "Thunderstorm": "⛈",
    "Snow": "❄️",
    "Mist": "🌫",
    "Fog": "🌫",
    "Haze": "🌫",
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
    async with aiohttp.ClientSession() as session:
        async with session.get(WEATHER_URL, params=params) as resp:
            data = await resp.json()
    if str(data.get("cod")) == "200":
        return data
    return None


@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "🌤 <b>Ob-havo Bot</b>ga xush kelibsiz!\n\n"
        "Shahar nomini yozing yoki pastdagi tugmalardan tanlang.",
        reply_markup=cities_keyboard(),
    )


@dp.message(F.text)
async def weather(message: Message):
    if not WEATHER_API_KEY:
        await message.answer("⚠️ WEATHER_API_KEY sozlanmagan. .env faylini tekshiring.")
        return

    city = message.text.strip()
    data = await get_weather(city)
    if not data:
        await message.answer("❌ Bunday shahar topilmadi. Nomini tekshirib qayta yozing.")
        return

    main_weather = data["weather"][0]["main"]
    desc = data["weather"][0]["description"].capitalize()
    emoji = WEATHER_EMOJI.get(main_weather, "🌡")
    temp = round(data["main"]["temp"])
    feels = round(data["main"]["feels_like"])
    humidity = data["main"]["humidity"]
    wind = data["wind"]["speed"]

    await message.answer(
        f"{emoji} <b>{data['name']}</b> ob-havosi\n\n"
        f"🌡 Harorat: <b>{temp}°C</b> (his qilinishi: {feels}°C)\n"
        f"📋 Holat: {desc}\n"
        f"💧 Namlik: {humidity}%\n"
        f"💨 Shamol: {wind} m/s"
    )


async def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN topilmadi. .env faylini to'ldiring.")
    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
