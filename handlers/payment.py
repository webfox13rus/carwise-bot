import logging
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import LabeledPrice, PreCheckoutQuery
from datetime import datetime, timedelta

from database import SessionLocal, User
from config import config
from keyboards.main_menu import get_main_menu, get_more_submenu

router = Router()
logger = logging.getLogger(__name__)

CURRENCY = "XTR"

@router.message(F.text == "💎 Купить Premium")
@router.message(Command("buy"))
async def buy_premium(message: types.Message):
    with SessionLocal() as db:
        user = db.query(User).filter(User.telegram_id == message.from_user.id).first()
        if user and user.is_premium:
            if user.premium_until and user.premium_until > datetime.utcnow():
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
    await callback.answer()

    if callback.data == "cancel_buy":
        await callback.message.edit_text("❌ Покупка отменена.")
        return

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

    prices = [LabeledPrice(label=f"Premium ({period})", amount=price)]
    try:
        await callback.message.answer_invoice(
            title="CarWise Premium",
            description=description,
            payload=payload,
            provider_token="",
            currency=CURRENCY,
            prices=prices,
            start_parameter="premium"
        )
        await callback.message.delete()
    except Exception as e:
        logger.error(f"Ошибка создания счёта: {e}")
        await callback.message.answer("❌ Произошла ошибка при создании счёта. Попробуйте позже.")

@router.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery):
    await pre_checkout_query.answer(ok=True)

@router.message(F.successful_payment)
async def successful_payment_handler(message: types.Message):
    payment = message.successful_payment
    payload = payment.invoice_payload
    total_amount = payment.total_amount

    logger.info(f"Успешная оплата от {message.from_user.id}: {payload}, сумма {total_amount} звезд")

    days = 30 if "month" in payload else 365

    with SessionLocal() as db:
        user = db.query(User).filter(User.telegram_id == message.from_user.id).first()
        if user:
            # Определяем базовую дату: если подписка активна, продлеваем от неё, иначе от сейчас
            base_date = user.premium_until if user.premium_until and user.premium_until > datetime.utcnow() else datetime.utcnow()
            user.premium_until = base_date + timedelta(days=days)
            user.is_premium = True
            db.commit()
        else:
            user = User(
                telegram_id=message.from_user.id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name,
                is_premium=True,
                premium_until=datetime.utcnow() + timedelta(days=days)
            )
            db.add(user)
            db.commit()

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
