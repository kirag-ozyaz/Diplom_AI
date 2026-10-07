# -*- coding: utf-8 -*-
"""
Точка входа для Telegram-бота.
Запуск: python -m src.bot
"""
import asyncio
import os
import sys


async def main() -> None:
    token = os.getenv("TG_BOT_TOKEN")
    if not token:
        print(" TG_BOT_TOKEN не задан. Укажите переменную окружения.")
        sys.exit(1)

    try:
        from aiogram import Bot, Dispatcher
        from aiogram.enums import ParseMode
        from aiogram.filters import CommandStart
        from aiogram.types import Message
    except ImportError:
        print(" aiogram не установлен. Выполните: pip install aiogram>=3.0")
        sys.exit(1)

    bot = Bot(token=token, parse_mode=ParseMode.HTML)
    dp = Dispatcher()

    @dp.message(CommandStart())
    async def cmd_start(message: Message) -> None:
        await message.answer(
            " <b>Бот по нормативной документации</b>\n\n"
            "Задайте вопрос по ПУЭ, ПТЭЭП или ГОСТ — я поищу ответ в базе знаний.\n\n"
            " RAG-модуль в разработке."
        )

    @dp.message()
    async def handle_query(message: Message) -> None:
        # TODO: RAG — поиск в Milvus + генерация через Ollama
        await message.answer(
            f" Ваш запрос: <i>{message.text[:100]}</i>\n\n"
            "RAG-обработка будет подключена после реализации модуля."
        )

    print(" Бот запущен...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
