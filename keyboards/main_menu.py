from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

def get_main_menu():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🚗 Мои автомобили"), KeyboardButton(text="➕ Добавить авто")],
            [KeyboardButton(text="⛽ Заправка"), KeyboardButton(text="🔧 Обслуживание")],
            [KeyboardButton(text="📊 Статистика"), KeyboardButton(text="🔄 Обновить пробег")]
        ],
        resize_keyboard=True
    )
    return keyboard

def get_cancel_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True
    )
    return keyboard

def get_fuel_types_keyboard():
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="АИ-92", callback_data="fuel_type_92"),
             InlineKeyboardButton(text="АИ-95", callback_data="fuel_type_95")],
            [InlineKeyboardButton(text="АИ-98", callback_data="fuel_type_98"),
             InlineKeyboardButton(text="ДТ", callback_data="fuel_type_dt")],
            [InlineKeyboardButton(text="Газ", callback_data="fuel_type_gas"),
             InlineKeyboardButton(text="Электричество", callback_data="fuel_type_electric")]
        ]
    )
    return keyboard
