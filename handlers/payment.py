import logging
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import LabeledPrice, PreCheckoutQuery
from datetime import datetime, timedelta

from database import get_db, User
from config import config
from keyboards.main_menu import get_main_menu, get_more_submenu

router = Router()
logger = logging.getLogger(__name__)

CURRENCY = "XTR"  # Telegram Stars

@router.message(F.text == "💎 Купить Premium")
@router.message(Command("buy"))
async def buy_premium(message: types.Message):
    """Показывает варианты подписки"""
    # Проверим, не премиум ли уже пользователь
    with next(get_db()) as db:
        user = db.query(User).filter(User.telegram_id == message.from_user.id).first()
        if user and user.is_premium:
            # Проверим, не истекла ли подписка (опционально)
            if user.premium_until and user.premium_until > datetime.now():
                await message.answer(
                    "💎 *У вас уже активна премиум-подписка*\n\n"
                    f"Действует до: {user.premium_until.strftime('%d.%m.%Y')}\n\n"
                    "Спасибо за поддержку!",
                    parse_mode="Markdown",
                    reply_markup=get_more_submenu()
                )
                return

    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="1 месяц (50 ⭐)", callback_data="buy_month")],
        [types.InlineKeyboardButton(text="1 год (500 ⭐) – скидка 20%", callback_data="buy_year")],
        [types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_buy")]
    ])
    await message.answer(
        "💎 *Премиум-подписка CarWise Bot*\n\n"
        "Доступные варианты:\n"
        "• 1 месяц – 50 ⭐\n"
        "• 1 год – 500 ⭐ (экономия 100 ⭐)\n\n"
        "Выберите срок:",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

@router.callback_query(F.data.startswith("buy_"))
async def process_buy_callback(callback: types.CallbackQuery):
    """Обработка выбора срока и создание счёта"""
    await callback.answer()

    if callback.data == "cancel_buy":
        await callback.message.edit_text("❌ Покупка отменена.")
        return

    # Определяем цену и название
    if callback.data == "buy_month":
        price = config.PREMIUM_PRICE_MONTH
        period = "месяц"
        description = "Премиум-подписка на 1 месяц"
        payload = "premium_month"
    elif callback.data == "buy_year":
        price = config.PREMIUM_PRICE_YEAR
        period = "год"
        description = "Премиум-подписка на 1 год"
        payload = "premium_year"
    else:
        return

    # Создаём счёт
    prices = [LabeledPrice(label=f"Premium ({period})", amount=price)]
    try:
        await callback.message.answer_invoice(
            title="CarWise Premium",
            description=description,
            payload=payload,
            provider_token="",   # для Stars оставляем пустым
            currency=CURRENCY,
            prices=prices,
            start_parameter="premium"
        )
        # Удаляем предыдущее сообщение с выбором
        await callback.message.delete()
    except Exception as e:
        logger.error(f"Ошибка создания счёта: {e}")
        await callback.message.answer("❌ Произошла ошибка при создании счёта. Попробуйте позже.")

@router.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery):
    """Подтверждение платежа (обязательный обработчик)"""
    await pre_checkout_query.answer(ok=True)

@router.message(F.successful_payment)
async def successful_payment_handler(message: types.Message):
    """Обработка успешной оплаты"""
    payment = message.successful_payment
    payload = payment.invoice_payload  # premium_month или premium_year
    total_amount = payment.total_amount

    logger.info(f"Успешная оплата от {message.from_user.id}: {payload}, сумма {total_amount} звезд")

    # Определяем срок подписки
    days = 30 if "month" in payload else 365
    premium_until = datetime.now() + timedelta(days=days)

    # Обновляем статус пользователя в БД
    with next(get_db()) as db:
        user = db.query(User).filter(User.telegram_id == message.from_user.id).first()
        if user:
            user.is_premium = True
            user.premium_until = premium_until
            db.commit()
        else:
            # Если пользователя почему-то нет (хотя должен быть при вызове /buy), создаём
            user = User(
                telegram_id=message.from_user.id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name,
                is_premium=True,
                premium_until=premium_until
            )
            db.add(user)
            db.commit()

    # Отправляем благодарность
    await message.answer(
        f"🎉 *Поздравляем!* Вы стали премиум-пользователем на {days} дней!\n\n"
        "Теперь вам доступны:\n"
        "• Неограниченное количество автомобилей\n"
        "• Экспорт данных в CSV\n"
        "• Сравнение расходов месяц к месяцу\n"
        "• AI-советы от GigaChat\n\n"
        "Спасибо за поддержку! 🙏",
        parse_mode="Markdown",
        reply_markup=get_main_menu()
    )
