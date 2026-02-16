from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

router = Router()

class AddFuel(StatesGroup):
    waiting_for_amount = State()
    waiting_for_cost = State()

@router.message(F.text == "⛽ Заправка")
@router.message(Command("fuel"))
async def add_fuel_start(message: types.Message, state: FSMContext):
    await state.set_state(AddFuel.waiting_for_amount)
    await message.answer(
        "⛽ Добавление заправки\n\n"
        "Введите количество литров:\n"
        "(Например: 45.5)"
    )

@router.message(AddFuel.waiting_for_amount)
async def process_fuel_amount(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text.replace(',', '.'))
        await state.update_data(amount=amount)
        await state.set_state(AddFuel.waiting_for_cost)
        await message.answer(
            f"⛽ {amount} литров\n\n"
            "Введите сумму в рублях:\n"
            "(Например: 2500)"
        )
    except ValueError:
        await message.answer("❌ Введите число (например: 45.5)")

@router.message(AddFuel.waiting_for_cost)
async def process_fuel_cost(message: types.Message, state: FSMContext):
    try:
        cost = float(message.text.replace(',', '.'))
        data = await state.get_data()
        price_per_liter = cost / data['amount']
        await message.answer(
            f"✅ Заправка добавлена!\n\n"
            f"Количество: {data['amount']:.2f} л\n"
            f"Сумма: {cost:.2f} ₽\n"
            f"Цена за литр: {price_per_liter:.2f} ₽\n\n"
            f"💡 Совет: Чтобы рассчитать расход, обновите пробег в автомобиле."
        )
        await state.clear()
    except ValueError:
        await message.answer("❌ Введите число (например: 2500)")
