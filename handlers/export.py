import csv
import io
import zipfile
from datetime import datetime
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import BufferedInputFile

from database import SessionLocal, User, Car, FuelEvent, MaintenanceEvent, Insurance, Part
from keyboards.main_menu import get_stats_submenu
from config import config

router = Router()

# Лимит Telegram на отправку документов (50 МБ)
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB

@router.message(F.text == "📤 Экспорт данных (Premium)")
@router.message(Command("export"))
async def export_data(message: types.Message):
    with SessionLocal() as db:
        user = db.query(User).filter(User.telegram_id == message.from_user.id).first()
        if not user:
            await message.answer("Сначала зарегистрируйтесь, отправив /start")
            return

        is_admin = message.from_user.id in config.ADMIN_IDS
        if not user.is_premium and not is_admin:
            await message.answer(
                "❌ *Экспорт данных* доступен только для премиум-пользователей.\n\n"
                "Оформите подписку, чтобы выгружать все свои данные в CSV для анализа в Excel.",
                parse_mode="Markdown",
                reply_markup=get_stats_submenu()
            )
            return

        cars = db.query(Car).filter(Car.user_id == user.id, Car.is_active == True).all()
        if not cars:
            await message.answer("У вас нет автомобилей для экспорта.", reply_markup=get_stats_submenu())
            return

        # Создаём CSV в памяти
        output = io.StringIO()
        writer = csv.writer(output, delimiter=';', quoting=csv.QUOTE_MINIMAL)
        writer.writerow([
            'Тип', 'Автомобиль', 'Дата', 'Описание/Деталь', 'Пробег', 'Стоимость',
            'Литры', 'Категория', 'Номер полиса/Компания', 'Интервал км', 'Интервал мес.'
        ])

        for car in cars:
            car_name = f"{car.brand} {car.model} ({car.year})"

            # Заправки
            fuel_events = db.query(FuelEvent).filter(FuelEvent.car_id == car.id).all()
            for ev in fuel_events:
                writer.writerow([
                    'Заправка',
                    car_name,
                    ev.date.strftime('%Y-%m-%d %H:%M'),
                    '',
                    ev.mileage if ev.mileage else '',
                    float(ev.cost),
                    float(ev.liters),
                    ev.fuel_type or '',
                    '',
                    '',
                    ''
                ])

            # Обслуживание
            maint_events = db.query(MaintenanceEvent).filter(MaintenanceEvent.car_id == car.id).all()
            for ev in maint_events:
                writer.writerow([
                    'Обслуживание',
                    car_name,
                    ev.date.strftime('%Y-%m-%d %H:%M'),
                    ev.description,
                    ev.mileage if ev.mileage else '',
                    float(ev.cost),
                    '',
                    ev.category,
                    '',
                    '',
                    ''
                ])

            # Страховки
            insurances = db.query(Insurance).filter(Insurance.car_id == car.id).all()
            for ins in insurances:
                writer.writerow([
                    'Страховка',
                    car_name,
                    ins.end_date.strftime('%Y-%m-%d'),
                    ins.notes or '',
                    '',
                    float(ins.cost),
                    '',
                    '',
                    f"{ins.policy_number or ''} / {ins.company or ''}",
                    '',
                    ''
                ])

            # Детали и жидкости
            parts = db.query(Part).filter(Part.car_id == car.id).all()
            for part in parts:
                writer.writerow([
                    'Деталь/Жидкость',
                    car_name,
                    part.last_date.strftime('%Y-%m-%d') if part.last_date else '',
                    part.name,
                    part.last_mileage if part.last_mileage else '',
                    '',
                    '',
                    '',
                    '',
                    part.interval_mileage or '',
                    part.interval_months or ''
                ])

        output.seek(0)
        csv_data = output.getvalue().encode('utf-8-sig')
        csv_size = len(csv_data)

        filename_base = f"carwise_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        caption = "📊 Ваши данные в формате CSV. Открыть можно в Excel или любом табличном редакторе."

        # Если размер CSV превышает лимит, упаковываем в ZIP
        if csv_size > MAX_FILE_SIZE:
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                zip_file.writestr(f"{filename_base}.csv", csv_data)
            zip_buffer.seek(0)
            document = BufferedInputFile(zip_buffer.read(), filename=f"{filename_base}.zip")
            caption = f"📦 Файл CSV превысил лимит Telegram, поэтому упакован в ZIP.\n{caption}"
        else:
            document = BufferedInputFile(csv_data, filename=f"{filename_base}.csv")

        await message.answer_document(document=document, caption=caption)
        await message.answer("Выберите действие:", reply_markup=get_stats_submenu())
