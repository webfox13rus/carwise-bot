from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

def get_main_menu():
    """Главное меню"""
    builder = ReplyKeyboardBuilder()
    
    builder.row(
        KeyboardButton(text="🚗 Мои автомобили"),
        KeyboardButton(text="➕ Добавить авто")
    )
    
    builder.row(
        KeyboardButton(text="⛽ Добавить заправку"),
        KeyboardButton(text="🔧 Обслуживание")
    )
    
    builder.row(
        KeyboardButton(text="📊 Отчеты"),
        KeyboardButton(text="🔔 Напоминания")
    )
    
    builder.row(
        KeyboardButton(text="⚙️ Настройки"),
        KeyboardButton(text="ℹ️ Помощь")
    )
    
    return builder.as_markup(resize_keyboard=True)

def get_cancel_keyboard():
    """Клавиатура отмены"""
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="❌ Отмена"))
    return builder.as_markup(resize_keyboard=True)

def get_yes_no_keyboard():
    """Клавиатура Да/Нет"""
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="✅ Да"),
        KeyboardButton(text="❌ Нет")
    )
    return builder.as_markup(resize_keyboard=True)

def get_fuel_types_keyboard():
    """Типы топлива"""
    from config import config
    
    builder = InlineKeyboardBuilder()
    for key, value in config.DEFAULT_FUEL_TYPES.items():
        builder.add(InlineKeyboardButton(text=value, callback_data=f"fuel_type_{key}"))
    builder.adjust(2)
    return builder.as_markup()

def get_event_categories_keyboard():
    """Категории событий"""
    from config import config
    
    builder = InlineKeyboardBuilder()
    for key, value in config.EVENT_CATEGORIES.items():
        builder.add(InlineKeyboardButton(text=value, callback_data=f"category_{key}"))
    builder.adjust(2)
    return builder.as_markup()

def get_maintenance_types_keyboard():
    """Типы обслуживания"""
    from config import config
    
    builder = InlineKeyboardBuilder()
    for key, value in config.MAINTENANCE_TYPES.items():
        builder.add(InlineKeyboardButton(text=value, callback_data=f"maintenance_{key}"))
    builder.adjust(2)
    return builder.as_markup()