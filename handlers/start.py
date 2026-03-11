from aiogram import Router, types
from aiogram.filters import Command
from keyboards.main_menu import get_main_menu

router = Router()

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "🚗 *Добро пожаловать в CarWise Bot – ваш персональный авто-помощник!*\n\n"
        "Я помогу вам:\n"
        "• 📊 Вести полный учёт расходов на автомобиль (заправки, обслуживание, страховки)\n"
        "• 🔔 Вовремя напоминать о ТО, истечении страховки и замене деталей\n"
        "• 🤖 Получать персональные AI-рекомендации по обслуживанию\n"
        "• 📸 Прикреплять и хранить фото чеков\n"
        "• 📤 Экспортировать все данные в CSV\n"
        "• 💎 Купить Premium и получить доступ к эксклюзивным функциям\n\n"
        "Поддерживаю популярные китайские марки и более 50 моделей.\n\n"
        "Нажмите кнопку **Меню** или /help, чтобы узнать подробнее.",
        parse_mode="Markdown",
        reply_markup=get_main_menu()
    )

@router.message(Command("help"))
async def cmd_help(message: types.Message):
    # Здесь можно разместить ваш длинный текст помощи
    await message.answer("Раздел помощи в разработке.", reply_markup=get_main_menu())
