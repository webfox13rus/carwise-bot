import logging
from datetime import datetime, timedelta
from aiogram import Router, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import func, and_

from database import SessionLocal, User, Car, FuelEvent, MaintenanceEvent
from config import config
from keyboards.main_menu import get_stats_submenu

router = Router()
logger = logging.getLogger(__name__)

def get_monthly_stats(db, user_id, year, month):
    """Возвращает словарь с суммами топлива и обслуживания за месяц, используя переданную сессию."""
    start_date = datetime(year, month, 1)
    if month == 12:
        end_date = datetime(year+1, 1, 1)
    else:
        end_date = datetime(year, month+1, 1)

    cars = db.query(Car).filter(Car.user_id == user_id, Car.is_active == True).all()
    total_fuel = 0
    total_maintenance = 0
    car_details = []

    for car in cars:
        fuel = db.query(func.sum(FuelEvent.cost)).filter(
            FuelEvent.car_id == car.id,
            FuelEvent.date >= start_date,
            FuelEvent.date < end_date
        ).scalar() or 0

        maint = db.query(func.sum(MaintenanceEvent.cost)).filter(
            MaintenanceEvent.car_id == car.id,
            MaintenanceEvent.date >= start_date,
            MaintenanceEvent.date < end_date
        ).scalar() or 0

        total_fuel += fuel
        total_maintenance += maint
        car_details.append({
            "name": f"{car.brand} {car.model}",
            "fuel": fuel,
            "maint": maint,
            "mileage": car.current_mileage
        })

    return {
        "total_fuel": total_fuel,
        "total_maintenance": total_maintenance,
        "cars": car_details
    }

def format_monthly_report(db, user_id, year, month, with_comparison=False):
    """Формирует текст отчёта, используя переданную сессию."""
    current = get_monthly_stats(db, user_id, year, month)
    month_name = datetime(year, month, 1).strftime('%B %Y')

    if with_comparison:
        prev_month = month - 1 if month > 1 else 12
        prev_year = year if month > 1 else year - 1
        previous = get_monthly_stats(db, user_id, prev_year, prev_month)

        fuel_diff = current["total_fuel"] - previous["total_fuel"]
        maint_diff = current["total_maintenance"] - previous["total_maintenance"]
        total_diff = (current["total_fuel"] + current["total_maintenance"]) - (previous["total_fuel"] + previous["total_maintenance"])

        def format_diff(val):
            if val > 0:
                return f"📈 +{val:,.2f} ₽"
            elif val < 0:
                return f"📉 {val:,.2f} ₽"
            else:
                return "➖ 0 ₽"

        header = f"📊 *Сравнение расходов: {month_name}*"
        lines = [
            f"⛽ Топливо: {current['total_fuel']:,.2f} ₽  ({format_diff(fuel_diff)})",
            f"🔧 Обслуживание: {current['total_maintenance']:,.2f} ₽  ({format_diff(maint_diff)})",
            f"💰 Всего: {current['total_fuel'] + current['total_maintenance']:,.2f} ₽  ({format_diff(total_diff)})"
        ]
        return header + "\n" + "\n".join(lines)
    else:
        header = f"📊 *Отчёт за {month_name}*"
        lines = [
            f"⛽ Топливо: {current['total_fuel']:,.2f} ₽",
            f"🔧 Обслуживание: {current['total_maintenance']:,.2f} ₽",
            f"💰 Всего: {current['total_fuel'] + current['total_maintenance']:,.2f} ₽"
        ]
        return header + "\n" + "\n".join(lines)

async def send_monthly_reports(bot):
    today = datetime.utcnow()
    if today.day != 1:
        return

    if today.month == 1:
        report_month = 12
        report_year = today.year - 1
    else:
        report_month = today.month - 1
        report_year = today.year

    logger.info(f"📅 Ежемесячная рассылка за {report_month}.{report_year}")

    with SessionLocal() as db:
        users = db.query(User).all()
        for user in users:
            cars = db.query(Car).filter(Car.user_id == user.id, Car.is_active == True).count()
            if cars == 0:
                continue

            if user.is_premium:
                report_text = format_monthly_report(db, user.id, report_year, report_month, with_comparison=True)
            else:
                report_text = format_monthly_report(db, user.id, report_year, report_month, with_comparison=False)

            keyboard = None
            if not user.is_premium:
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📈 Сравнить с прошлым месяцем (Premium)", callback_data="compare_premium")]
                ])

            try:
                await bot.send_message(user.telegram_id, report_text, parse_mode="Markdown", reply_markup=keyboard)
                logger.debug(f"Отчёт отправлен пользователю {user.telegram_id}")
            except Exception as e:
                logger.error(f"Ошибка отправки пользователю {user.telegram_id}: {e}")

@router.callback_query(F.data == "compare_premium")
async def compare_premium_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    with SessionLocal() as db:
        user = db.query(User).filter(User.telegram_id == user_id).first()
        if user and user.is_premium:
            today = datetime.utcnow()
            if today.month == 1:
                report_month = 12
                report_year = today.year - 1
            else:
                report_month = today.month - 1
                report_year = today.year
            report_text = format_monthly_report(db, user.id, report_year, report_month, with_comparison=True)
            await callback.message.answer(report_text, parse_mode="Markdown")
        else:
            await callback.message.answer(
                "❌ *Сравнение расходов* доступно только для премиум-пользователей.\n\n"
                "Оформите подписку, чтобы видеть динамику месяц к месяцу.",
                parse_mode="Markdown"
            )
    await callback.answer()

@router.message(F.text == "📈 Сравнение расходов (Premium)")
async def compare_stats_command(message: types.Message):
    user_id = message.from_user.id
    with SessionLocal() as db:
        user = db.query(User).filter(User.telegram_id == user_id).first()
        if not user:
            await message.answer("Сначала зарегистрируйтесь, отправив /start")
            return

        if not user.is_premium and message.from_user.id not in config.ADMIN_IDS:
            await message.answer(
                "❌ *Сравнение расходов* доступно только для премиум-пользователей.\n\n"
                "Оформите подписку, чтобы видеть динамику месяц к месяцу.",
                parse_mode="Markdown",
                reply_markup=get_stats_submenu()
            )
            return

        today = datetime.utcnow()
        if today.month == 1:
            report_month = 12
            report_year = today.year - 1
        else:
            report_month = today.month - 1
            report_year = today.year

        report_text = format_monthly_report(db, user.id, report_year, report_month, with_comparison=True)
        await message.answer(report_text, parse_mode="Markdown", reply_markup=get_stats_submenu())
