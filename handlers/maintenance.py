from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

router = Router()

class AddMaintenance(StatesGroup):
    waiting_for_description = State()
    waiting_for_cost = State()

@router.message(F.text == "🔧 Обслуживание")
@router.message(Command("add_maintenance"))
async def add_maintenance_start(message: types.Message, state: FSMContext):
    await state.set_state(AddMaintenance.waiting_for_description)
    await message.answer(
        "🔧 *Добавление обслуживания*\n\n"
        "Введите, что сделали (например: замена масла, шиномонтаж):",

    )

@router.message(AddMaintenance.waiting_for_description)
async def process_maint_description(message: types.Message, state: FSMContext):
    await state.update_data(description=message.text)
    await state.set_state(AddMaintenance.waiting_for_cost)
    await message.answer(
        "Введите стоимость в рублях:",
       
    )

@router.message(AddMaintenance.waiting_for_cost)
async def process_maint_cost(message: types.Message, state: FSMContext):
    try:
        cost = float(message.text.replace(',', '.'))
        data = await state.get_data()
        
        await message.answer(
            f"✅ *Обслуживание добавлено!*\n\n"
            f"*{data['description']}*\n"
            f"Стоимость: *{cost:.2f} ₽*",
            
        )
        
        await state.clear()
    except ValueError:
        await message.answer("❌ Введите число (например: 2500)") 


