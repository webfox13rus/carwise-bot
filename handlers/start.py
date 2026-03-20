from aiogram import Router, types, F
from aiogram.filters import Command
from keyboards.main_menu import get_main_menu
from database import SessionLocal, User
import logging

logger = logging.getLogger(__name__)
router = Router()

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    # Проверяем, есть ли пользователь в БД
    with SessionLocal() as db:
        user = db.query(User).filter(User.telegram_id == message.from_user.id).first()
        if not user:
            user = User(
                telegram_id=message.from_user.id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            logger.info(f"Новый пользователь зарегистрирован: {message.from_user.id}")

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
@router.message(F.text == "📞 Помощь / О боте")
async def cmd_help(message: types.Message):
    help_text = (
        "📋 *CarWise Bot – полное руководство*\n\n"
        "Бот предназначен для учёта всех расходов, связанных с автомобилем, и своевременных напоминаний.\n\n"
        "🚗 *Главное меню*\n"
        "Состоит из шести разделов, каждый из которых открывает своё подменю:\n"
        "• `🚗 Мои авто` – управление автомобилями\n"
        "• `⛽ Заправки` – учёт заправок и чеки\n"
        "• `🔧 Обслуживание` – ТО, ремонт, запчасти, жидкости\n"
        "• `📄 Страховки` – полисы и напоминания\n"
        "• `📊 Статистика` – полная статистика по расходам, заправкам, заменам, страховке\n"
        "• `⚙️ Ещё` – все чеки, покупка Premium, помощь, обратная связь, админ-панель\n\n"
        "🔧 *Подменю «Обслуживание»*\n"
        "• `🔧 Добавить событие` – выбор категории (ТО, мойка, ремонт, запчасти, шиномонтаж, жидкости, другое)\n"
        "• `🔧 Плановые замены` – отчёт о деталях и жидкостях с истекающими интервалами\n"
        "• `⏰ Напоминания ТО` – настройка интервалов для следующего ТО (по пробегу и/или времени)\n"
        "• `📸 Мои чеки обслуживания` – просмотр фото чеков\n\n"
        "💎 *Премиум-подписка*\n"
        "• Цена: 50 ⭐/мес или 500 ⭐/год.\n"
        "• Доступные функции: неограниченное количество авто, экспорт данных, сравнение расходов, AI-советы.\n\n"
        "© 2026 CarWise Bot. Все права защищены. Не для коммерческого использования."
    )
    await message.answer(help_text, parse_mode="Markdown", reply_markup=get_main_menu())
