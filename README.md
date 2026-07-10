# 🌤 Ob-havo Bot

Tanlangan shaharning ob-havosini ko'rsatuvchi Telegram bot.

## ✨ Imkoniyatlar
- Shahar nomi bo'yicha real vaqtli ob-havo
- Harorat, "his qilinishi", namlik, shamol tezligi
- Ob-havo holatiga mos emoji
- Mashhur shaharlar uchun tezkor tugmalar

## 🛠 Texnologiyalar
- Python 3.11+
- [aiogram 3.x](https://docs.aiogram.dev/)
- [OpenWeatherMap API](https://openweathermap.org/api)

## 🚀 O'rnatish

1. Kutubxonalarni o'rnating:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate      # Windows
   pip install -r requirements.txt
   ```

2. `.env.example` dan nusxa olib `.env` yarating:
   ```
   BOT_TOKEN=...
   WEATHER_API_KEY=...
   ```
   - `BOT_TOKEN` — [@BotFather](https://t.me/BotFather) dan.
   - `WEATHER_API_KEY` — https://openweathermap.org/api dan bepul oling.

3. Ishga tushiring:
   ```bash
   python main.py
   ```

## 💬 Foydalanish
- `/start` — botni ishga tushirish
- Shahar nomini yozing yoki tugmadan tanlang
