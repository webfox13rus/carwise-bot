from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext

from keyboards.main_menu import (
    get_main_menu,
    get_cars_submenu,
    get_fuel_submenu,
    get_maintenance_submenu,
    get_insurance_submenu,
    get_more_submenu,
    get_stats_submenu
)

router = Router()

# Обработчики пунктов главного меню
@router.message(F.text == "🚗 Мои авто")
async def go_to_cars(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Управление автомобилями:", reply_markup=get_cars_submenu())

@router.message(F.text == "⛽ Заправки")
async def go_to_fuel(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Управление заправками:", reply_markup=get_fuel_submenu())

@router.message(F.text == "🔧 Обслуживание")
async def go_to_maintenance(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Управление обслуживанием:", reply_markup=get_maintenance_submenu())

@router.message(F.text == "📄 Страховки")
async def go_to_insurance(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Управление страховками:", reply_markup=get_insurance_submenu())

@router.message(F.text == "📊 Статистика")
async def go_to_stats_menu(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Выберите формат статистики:", reply_markup=get_stats_submenu())

@router.message(F.text == "⚙️ Ещё")
async def go_to_more(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Дополнительные функции:", reply_markup=get_more_submenu())

# Обработчик кнопки "Назад" (возврат в главное меню)
@router.message(F.text == "◀️ Назад")
async def back_to_main(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Главное меню:", reply_markup=get_main_menu())
