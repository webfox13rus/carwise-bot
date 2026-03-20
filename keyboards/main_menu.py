from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from config import config
from database import SessionLocal, Admin

def is_admin(user_id: int) -> bool:
    if user_id in config.ADMIN_IDS:
        return True
    with SessionLocal() as db:
        admin = db.query(Admin).filter(Admin.telegram_id == user_id).first()
        return admin is not None

def get_main_menu():
    return ReplyKeyboardMarkup(
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

def get_cars_submenu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🚗 Список авто")],
            [KeyboardButton(text="➕ Добавить авто")],
            [KeyboardButton(text="🔄 Обновить пробег")],
            [KeyboardButton(text="🗑 Удалить авто")],
            [KeyboardButton(text="◀️ Назад")]
        ],
        resize_keyboard=True
    )

def get_fuel_submenu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="⛽ Добавить заправку")],
            [KeyboardButton(text="📸 Мои чеки заправок")],
            [KeyboardButton(text="◀️ Назад")]
        ],
        resize_keyboard=True
    )

def get_maintenance_submenu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔧 Добавить событие")],
            [KeyboardButton(text="🔧 Плановые замены")],
            [KeyboardButton(text="⏰ Напоминания ТО")],
            [KeyboardButton(text="📸 Мои чеки обслуживания")],
            [KeyboardButton(text="◀️ Назад")]
        ],
        resize_keyboard=True
    )

def get_insurance_submenu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📄 Добавить страховку")],
            [KeyboardButton(text="📄 Список страховок")],
            [KeyboardButton(text="📸 Мои чеки страховок")],
            [KeyboardButton(text="◀️ Назад")]
        ],
        resize_keyboard=True
    )

def get_stats_submenu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 Статистика")],
            [KeyboardButton(text="📈 Сравнение расходов (Premium)")],
            [KeyboardButton(text="🤖 AI-совет (Premium)")],
            [KeyboardButton(text="📤 Экспорт данных (Premium)")],
            [KeyboardButton(text="◀️ Назад")]
        ],
        resize_keyboard=True
    )

def get_more_submenu(user_id: int = None):
    buttons = [
        [KeyboardButton(text="📸 Все чеки")],
        [KeyboardButton(text="💎 Купить Premium")],
        [KeyboardButton(text="📞 Помощь / О боте")],
        [KeyboardButton(text="✉️ Связаться с админом")],
        [KeyboardButton(text="◀️ Назад")]
    ]
    if user_id and is_admin(user_id):
        buttons.insert(0, [KeyboardButton(text="👑 Админ-панель")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_cancel_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True
    )

def get_skip_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="⏭ Пропустить")], [KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True
    )

def get_fuel_types_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="АИ-92", callback_data="fuel_type_92"),
             InlineKeyboardButton(text="АИ-95", callback_data="fuel_type_95")],
            [InlineKeyboardButton(text="АИ-98", callback_data="fuel_type_98"),
             InlineKeyboardButton(text="ДТ", callback_data="fuel_type_dt")],
            [InlineKeyboardButton(text="Газ", callback_data="fuel_type_gas"),
             InlineKeyboardButton(text="Электричество", callback_data="fuel_type_electric")]
        ]
    )
