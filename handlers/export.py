import csv
import io
from datetime import datetime
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import BufferedInputFile

from database import get_db, User, Car, FuelEvent, MaintenanceEvent, Insurance, Part
from keyboards.main_menu import get_main_menu, get_more_submenu

router = Router()

@router.message(F.text == "📤 Экспорт данных")
@router.message(Command("export"))
async def export_data(message: types.Message):
    with next(get_db()) as db:
        user = db.query(User).filter(User.telegram_id == message.from_user.id).first()
        if not user:
            await message.answer("Сначала зарегистрируйтесь, отправив /start")
            return

        cars = db.query(Car).filter(Car.user_id == user.id, Car.is_active == True).all()
        if not cars:
            await message.answer("У вас нет автомобилей для экспорта.")
            return

        output = io.StringIO()
        writer = csv.writer(output, delimiter=';', quoting=csv.QUOTE_MINIMAL)
        writer.writerow([
            'Тип', 'Автомобиль', 'Дата', 'Описание/Деталь', 'Пробег', 'Стоимость',
            'Литры', 'Категория', 'Номер полиса/Компания', 'Интервал км', 'Интервал мес.'
        ])

        for car in cars:
            car_name = f"{car.brand} {car.model} ({car.year})"

            fuel_events = db.query(FuelEvent).filter(FuelEvent.car_id == car.id).all()
            for ev in fuel_events:
                writer.writerow([
                    'Заправка',
                    car_name,
                    ev.date.strftime('%Y-%m-%d %H:%M'),
                    '',
                    ev.mileage if ev.mileage else '',
                    ev.cost,
                    ev.liters,
                    ev.fuel_type or '',
                    '',
                    '',
                    ''
                ])

            maint_events = db.query(MaintenanceEvent).filter(MaintenanceEvent.car_id == car.id).all()
            for ev in maint_events:
                writer.writerow([
                    'Обслуживание',
                    car_name,
                    ev.date.strftime('%Y-%m-%d %H:%M'),
                    ev.description,
                    ev.mileage if ev.mileage else '',
                    ev.cost,
                    '',
                    ev.category,
                    '',
                    '',
                    ''
                ])

            insurances = db.query(Insurance).filter(Insurance.car_id == car.id).all()
            for ins in insurances:
                writer.writerow([
                    'Страховка',
                    car_name,
                    ins.end_date.strftime('%Y-%m-%d'),
                    ins.notes or '',
                    '',
                    ins.cost,
                    '',
                    '',
                    f"{ins.policy_number or ''} / {ins.company or ''}",
                    '',
                    ''
                ])

            parts = db.query(Part).filter(Part.car_id == car.id).all()
            for part in parts:
                writer.writerow([
                    'Деталь',
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
        filename = f"carwise_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        bytes_output = io.BytesIO()
        bytes_output.write(output.getvalue().encode('utf-8-sig'))
        bytes_output.seek(0)

        await message.answer_document(
            document=BufferedInputFile(
                bytes_output.read(),
                filename=filename
            ),
            caption="📊 Ваши данные в формате CSV. Открыть можно в Excel или любом табличном редакторе."
        )

        await message.answer("Главное меню:", reply_markup=get_main_menu())
