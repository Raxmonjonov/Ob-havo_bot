"""
Ob-Havo Bot — Production Ready
OpenWeatherMap API orqali real vaqtli ob-havo ma'lumoti
"""

import asyncio
import logging
import os
import time

import aiohttp
import aiosqlite
from aiogram import Bot, Dispatcher, F, BaseMiddleware
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.exceptions import TelegramAPIError
from aiogram.types import Message
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from dotenv import load_dotenv

# ─── Konfiguratsiya ─────────────────────────────────────────────────
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]
DB_PATH = os.getenv("DB_PATH", "ob_havo.db")
THROTTLE_RATE = float(os.getenv("THROTTLE_RATE", "0.5"))
WEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"
TIMEOUT = aiohttp.ClientTimeout(total=15)

# ─── Logging ────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler("bot.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("ob-havo-bot")

# ─── Konstantalar ───────────────────────────────────────────────────
WEATHER_EMOJI = {
    "Clear": "☀️", "Clouds": "☁️", "Rain": "🌧", "Drizzle": "🌦",
    "Thunderstorm": "⛈", "Snow": "❄️", "Mist": "🌫", "Fog": "🌫", "Haze": "🌫",
}
POPULAR_CITIES = ["Toshkent", "Samarqand", "Buxoro", "Namangan", "Andijon", "Nukus"]


# ─── Database ───────────────────────────────────────────────────────
async def init_db():
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    full_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS searches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    city TEXT NOT NULL,
                    found INTEGER DEFAULT 1,
                    searched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.commit()
        logger.info("Database muvaffaqiyatli ishga tushirildi: %s", DB_PATH)
    except Exception as e:
        logger.error("Database xatosi: %s", e)
        raise


async def add_user(user_id: int, username: str | None, full_name: str | None):
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                INSERT OR IGNORE INTO users (user_id, username, full_name)
                VALUES (?, ?, ?)
            """, (user_id, username, full_name))
            await db.execute(
                "UPDATE users SET last_active = CURRENT_TIMESTAMP WHERE user_id = ?",
                (user_id,),
            )
            await db.commit()
    except Exception as e:
        logger.error("User qo'shishda xato: %s", e)


async def save_search(user_id: int, city: str, found: bool):
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO searches (user_id, city, found) VALUES (?, ?, ?)",
                (user_id, city, 1 if found else 0),
            )
            await db.commit()
    except Exception as e:
        logger.error("Qidiruvni saqlashda xato: %s", e)


async def get_stats() -> dict:
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            row = await db.execute("SELECT COUNT(*) FROM users")
            users = (await row.fetchone())[0]
            row = await db.execute("SELECT COUNT(*) FROM searches")
            searches = (await row.fetchone())[0]
            row = await db.execute(
                "SELECT city, COUNT(*) as cnt FROM searches WHERE found=1 GROUP BY city ORDER BY cnt DESC LIMIT 5"
            )
            top_cities = await row.fetchall()
            return {"users": users, "searches": searches, "top_cities": top_cities}
    except Exception as e:
        logger.error("Statistika xatosi: %s", e)
        return {"users": 0, "searches": 0, "top_cities": []}


# ─── Middleware ──────────────────────────────────────────────────────
class ThrottlingMiddleware(BaseMiddleware):
    def __init__(self, rate: float = 0.5):
        self.rate = rate
        self.user_timestamps: dict[int, float] = {}
        super().__init__()

    async def __call__(self, handler, event, data):
        user_id = event.from_user.id
        now = time.time()
        last = self.user_timestamps.get(user_id, 0)
        if now - last < self.rate:
            return
        self.user_timestamps[user_id] = now
        return await handler(event, data)


class ErrorMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        try:
            return await handler(event, data)
        except TelegramAPIError as e:
            logger.error("Telegram API xatosi: %s", e)
        except Exception as e:
            logger.error("Kutilmagan xatolik: %s", e, exc_info=True)
            try:
                if isinstance(event, Message):
                    await event.answer("❌ Xatolik yuz berdi.")
            except Exception:
                pass


# ─── Dispatcher ─────────────────────────────────────────────────────
dp = Dispatcher(storage=MemoryStorage())
dp.message.middleware(ThrottlingMiddleware(THROTTLE_RATE))
dp.message.middleware(ErrorMiddleware())


# ─── Keyboardlar ────────────────────────────────────────────────────
def cities_keyboard():
    builder = ReplyKeyboardBuilder()
    for city in POPULAR_CITIES:
        builder.button(text=city)
    builder.adjust(3)
    return builder.as_markup(resize_keyboard=True)


# ─── API ─────────────────────────────────────────────────────────────
async def get_weather(city: str) -> dict | None:
    params = {"q": city, "appid": WEATHER_API_KEY, "units": "metric", "lang": "en"}
    try:
        async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
            async with session.get(WEATHER_URL, params=params) as resp:
                return await resp.json()
    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        logger.error("Ob-havo API xatosi: %s", e)
        return None


def fmt_time(ts: int, tz_offset: int) -> str:
    from datetime import datetime, timedelta, timezone
    return (datetime.fromtimestamp(ts, tz=timezone.utc) + timedelta(seconds=tz_offset)).strftime("%H:%M")


def format_weather(data: dict) -> str:
    w_list = data.get("weather", [])
    if not w_list:
        return "❌ Ob-havo ma'lumoti topilmadi."
    w = w_list[0]
    main_data = data.get("main", {})
    wind = data.get("wind", {})
    sys_data = data.get("sys", {})
    tz = data.get("timezone", 0)
    emoji = WEATHER_EMOJI.get(w.get("main"), "🌡")

    lines = [
        f"{emoji} <b>{data.get('name')}</b> ob-havosi",
        "",
        f"🌡 Harorat: <b>{round(main_data.get('temp', 0))}°C</b> (his: {round(main_data.get('feels_like', 0))}°C)",
        f"🔺 Maks: {round(main_data.get('temp_max', 0))}°C   🔻 Min: {round(main_data.get('temp_min', 0))}°C",
        f"📋 Holat: {w.get('description', '').capitalize()}",
        f"💧 Namlik: {main_data.get('humidity', '?')}%",
        f"🎚 Bosim: {main_data.get('pressure', '?')} hPa",
        f"💨 Shamol: {wind.get('speed', '?')} m/s",
    ]
    if sys_data.get("sunrise") and sys_data.get("sunset"):
        lines.append(f"🌅 {fmt_time(sys_data['sunrise'], tz)}   🌇 {fmt_time(sys_data['sunset'], tz)}")
    return "\n".join(lines)


# ─── Handlerlar ─────────────────────────────────────────────────────
@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    try:
        await state.clear()
        await add_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
        logger.info("Start — user %d (@%s)", message.from_user.id, message.from_user.username)
        await message.answer(
            "🌤 <b>Ob-havo Bot</b>ga xush kelibsiz!\n\n"
            "Shahar nomini yozing yoki pastdagi tugmalardan tanlang.",
            reply_markup=cities_keyboard(),
        )
    except Exception as e:
        logger.error("Start handler xatosi: %s", e)


@dp.message(Command("help"))
async def cmd_help(message: Message):
    try:
        await message.answer(
            "🌤 <b>Ob-havo Bot</b> — Yordam\n\n"
            "📋 <b>Buyruqlar:</b>\n"
            "• /start — Botni qayta ishga tushirish\n"
            "• /help — Yordam\n"
            "• /stats — Statistika\n\n"
            "📝 <b>Foydalanish:</b>\n"
            "• Shahar nomini yozing → ob-havo\n"
            "• Tugmalardan mashhur shaharlarni tanlang"
        )
    except Exception as e:
        logger.error("Help handler xatosi: %s", e)


@dp.message(Command("stats"))
async def cmd_stats(message: Message):
    try:
        if message.from_user.id not in ADMIN_IDS:
            await message.answer("⛔ Sizda ruxsat yo'q.")
            return
        stats = await get_stats()
        text = (
            "📊 <b>Bot Statistikasi</b>\n\n"
            f"👥 Foydalanuvchilar: {stats['users']}\n"
            f"🔍 Qidiruvlar: {stats['searches']}\n\n"
            "🏙 <b>Eng ko'p qidirilgan shaharlar:</b>\n"
        )
        for city, cnt in stats["top_cities"]:
            text += f"  • {city}: {cnt} marta\n"
        await message.answer(text)
    except Exception as e:
        logger.error("Stats handler xatosi: %s", e)


@dp.message(Command("stats"))
@dp.message(StateFilter(None), F.text)
async def handle_text(message: Message):
    try:
        if not WEATHER_API_KEY or WEATHER_API_KEY == "your_openweathermap_api_key":
            await message.answer("⚠️ WEATHER_API_KEY sozlanmagan. .env faylini tekshiring.")
            return
        city = message.text.strip()
        if not city or len(city) > 100:
            await message.answer("❌ Shahar nomini to'g'ri yozing.")
            return
        await message.bot.send_chat_action(message.chat.id, "typing")
        logger.info("Ob-havo qidirildi — user %d: %s", message.from_user.id, city)
        data = await get_weather(city)
        if data is None:
            await message.answer("🌐 Tarmoqda muammo. Birozdan so'ng qayta urinib ko'ring.")
            return
        if str(data.get("cod")) != "200":
            await save_search(message.from_user.id, city, False)
            await message.answer("❌ Bunday shahar topilmadi. Nomini tekshirib qayta yozing.")
            return
        await save_search(message.from_user.id, city, True)
        await message.answer(format_weather(data))
    except Exception as e:
        logger.error("Ob-havo handler xatosi: %s", e)


# ─── Bot ishga tushirish ───────────────────────────────────────────
async def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN topilmadi. .env faylini to'ldiring.")
    if not WEATHER_API_KEY or WEATHER_API_KEY == "your_openweathermap_api_key":
        logger.warning("WEATHER_API_KEY sozlanmagan! Ob-havo ishlamaydi.")
    await init_db()
    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    me = await bot.get_me()
    logger.info("🤖 Ob-Havo Bot ishga tushdi! (@%s)", me.username)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
