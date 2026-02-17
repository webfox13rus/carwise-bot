from aiogram.fsm.state import State, StatesGroup

class AddCarStates(StatesGroup):
    waiting_for_brand = State()
    waiting_for_brand_manual = State()
    waiting_for_model = State()
    waiting_for_model_manual = State()
    waiting_for_year = State()
    waiting_for_name = State()
    waiting_for_mileage = State()
    waiting_for_fuel_type = State()

class MileageUpdateStates(StatesGroup):
    waiting_for_car_choice = State()
    waiting_for_mileage = State()
