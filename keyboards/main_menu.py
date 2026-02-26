from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

def get_main_menu():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🚗 Мои авто")],
            [KeyboardButton(text="⛽ Заправки")],
            [KeyboardButton(text="🔧 Обслуживание")],
            [KeyboardButton(text="📄 Страховки")],
            [KeyboardButton(text="📊 Статистика")],
            [KeyboardButton(text="⚙️ Ещё")]
        ],
        resize_keyboard=True
    )
    return keyboard

def get_cars_submenu():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🚗 Список авто")],
            [KeyboardButton(text="➕ Добавить авто")],
            [KeyboardButton(text="🔄 Обновить пробег")],
            [KeyboardButton(text="🗑 Удалить авто")],
            [KeyboardButton(text="◀️ Назад")]
        ],
        resize_keyboard=True
    )
    return keyboard

def get_fuel_submenu():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="⛽ Добавить заправку")],
            [KeyboardButton(text="📸 Мои чеки заправок")],
            [KeyboardButton(text="◀️ Назад")]
        ],
        resize_keyboard=True
    )
    return keyboard

def get_maintenance_submenu():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔧 Добавить событие")],
            [KeyboardButton(text="🔧 Плановые замены")],
            [KeyboardButton(text="⏰ Напоминания ТО")],
            [KeyboardButton(text="📸 Мои чеки обслуживания")],
            [KeyboardButton(text="◀️ Назад")]
        ],
        resize_keyboard=True
    )
    return keyboard

def get_insurance_submenu():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📄 Добавить страховку")],
            [KeyboardButton(text="📄 Список страховок")],
            [KeyboardButton(text="📸 Мои чеки страховок")],
            [KeyboardButton(text="◀️ Назад")]
        ],
        resize_keyboard=True
    )
    return keyboard

def get_stats_submenu():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 Краткая статистика")],
            [KeyboardButton(text="📈 Детальная статистика")],
            [KeyboardButton(text="📤 Экспорт данных")],
            [KeyboardButton(text="Расширенная статистика (Premium)")],
            [KeyboardButton(text="◀️ Назад")]
        ],
        resize_keyboard=True
    )
    return keyboard

def get_more_submenu():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📸 Все чеки")],
            [KeyboardButton(text="📞 Помощь / О боте")],
            [KeyboardButton(text="✉️ Связаться с админом")],
            [KeyboardButton(text="◀️ Назад")]
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
