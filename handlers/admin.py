import logging
from datetime import datetime, timedelta
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from database import get_db, User, Car, FuelEvent, MaintenanceEvent, Insurance, Admin, BannedUser
from config import config
from keyboards.main_menu import get_main_menu, get_more_submenu

router = Router()
logger = logging.getLogger(__name__)

# ---------- Состояния для FSM ----------
class BroadcastStates(StatesGroup):
    waiting_for_message = State()
    confirm = State()

class FindUserStates(StatesGroup):
    waiting_for_id = State()

class AddAdminStates(StatesGroup):
    waiting_for_id = State()

# ---------- Вспомогательные функции ----------
def is_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь администратором (из БД или config)."""
    with next(get_db()) as db:
        if user_id in config.ADMIN_IDS:
            return True
        admin = db.query(Admin).filter(Admin.telegram_id == user_id).first()
        return admin is not None

def is_banned(user_id: int) -> bool:
    """Проверяет, заблокирован ли пользователь."""
    with next(get_db()) as db:
        banned = db.query(BannedUser).filter(BannedUser.telegram_id == user_id).first()
        return banned is not None

# ---------- Главное меню админки ----------
@router.message(F.text == "👑 Админ-панель")
async def admin_panel(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав доступа.")
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="👥 Поиск пользователя", callback_data="admin_find_user")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="👑 Управление админами", callback_data="admin_manage_admins")],
        [InlineKeyboardButton(text="🔨 Заблокированные", callback_data="admin_banned")],
        [InlineKeyboardButton(text="❌ Закрыть", callback_data="admin_close")]
    ])
    await message.answer(
        "👑 *Административная панель*\nВыберите действие:",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

# ---------- Статистика ----------
@router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    with next(get_db()) as db:
        total_users = db.query(User).count()
        total_cars = db.query(Car).count()
        total_fuel = db.query(FuelEvent).count()
        total_maintenance = db.query(MaintenanceEvent).count()
        total_insurance = db.query(Insurance).count()
        premium_users = db.query(User).filter(User.is_premium == True).count()
        banned_count = db.query(BannedUser).count()

    stats_text = (
        f"📊 *Статистика бота*\n\n"
        f"👥 Всего пользователей: {total_users}\n"
        f"🚗 Автомобилей: {total_cars}\n"
        f"⛽ Заправок: {total_fuel}\n"
        f"🔧 Обслуживаний: {total_maintenance}\n"
        f"📄 Страховок: {total_insurance}\n"
        f"💎 Премиум: {premium_users}\n"
        f"🔨 Заблокировано: {banned_count}"
    )
    await callback.message.edit_text(stats_text, parse_mode="Markdown")
    await callback.answer()

# ---------- Поиск пользователя по ID ----------
@router.callback_query(F.data == "admin_find_user")
async def find_user_start(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    await state.set_state(FindUserStates.waiting_for_id)
    await callback.message.edit_text(
        "Введите Telegram ID пользователя (число):\n"
        "Чтобы отменить, отправьте /cancel"
    )
    await callback.answer()

@router.message(FindUserStates.waiting_for_id)
async def find_user_by_id(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав.")
        await state.clear()
        return
    try:
        user_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Введите корректное число.")
        return

    with next(get_db()) as db:
        user = db.query(User).filter(User.telegram_id == user_id).first()
        if not user:
            await message.answer("❌ Пользователь с таким ID не найден.")
            await state.clear()
            return

        cars = db.query(Car).filter(Car.user_id == user.id).count()
        premium_status = "✅ Да" if user.is_premium else "❌ Нет"
        premium_until = user.premium_until.strftime('%d.%m.%Y') if user.premium_until else "—"
        banned = is_banned(user_id)
        banned_status = "🔨 Да" if banned else "✅ Нет"

        text = (
            f"👤 *Информация о пользователе*\n"
            f"ID: `{user.telegram_id}`\n"
            f"Имя: {user.first_name} {user.last_name or ''}\n"
            f"Username: @{user.username}\n"
            f"Автомобилей: {cars}\n"
            f"Премиум: {premium_status}\n"
            f"Действует до: {premium_until}\n"
            f"Заблокирован: {banned_status}\n"
            f"Дата регистрации: {user.created_at.strftime('%d.%m.%Y')}"
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="💎 Выдать премиум" if not user.is_premium else "💎 Отозвать премиум",
                callback_data=f"admin_toggle_premium_{user.telegram_id}"
            )],
            [InlineKeyboardButton(
                text="🔨 Заблокировать" if not banned else "✅ Разблокировать",
                callback_data=f"admin_toggle_ban_{user.telegram_id}"
            )],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel_back")]
        ])

        await message.answer(text, parse_mode="Markdown", reply_markup=keyboard)
    await state.clear()

# ---------- Переключение премиум-статуса ----------
@router.callback_query(F.data.startswith("admin_toggle_premium_"))
async def toggle_premium(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    target_id = int(callback.data.split("_")[-1])
    with next(get_db()) as db:
        user = db.query(User).filter(User.telegram_id == target_id).first()
        if user:
            user.is_premium = not user.is_premium
            if user.is_premium:
                user.premium_until = datetime.now() + timedelta(days=365)
            else:
                user.premium_until = None
            db.commit()
            await callback.answer(f"Статус премиума изменён: {'включён' if user.is_premium else 'отключён'}", show_alert=True)
        else:
            await callback.answer("❌ Пользователь не найден", show_alert=True)
    await callback.message.edit_text("✅ Статус обновлён. Вы можете продолжить поиск.")
    await callback.message.answer(
        "👑 Вернуться в админ-панель:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👑 Админка", callback_data="admin_panel_back")]
        ])
    )

# ---------- Блокировка/разблокировка ----------
@router.callback_query(F.data.startswith("admin_toggle_ban_"))
async def toggle_ban(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    target_id = int(callback.data.split("_")[-1])
    with next(get_db()) as db:
        banned = db.query(BannedUser).filter(BannedUser.telegram_id == target_id).first()
        if banned:
            db.delete(banned)
            db.commit()
            await callback.answer("✅ Пользователь разблокирован", show_alert=True)
        else:
            new_ban = BannedUser(
                telegram_id=target_id,
                banned_by=callback.from_user.id,
                reason="Заблокирован администратором"
            )
            db.add(new_ban)
            db.commit()
            await callback.answer("❌ Пользователь заблокирован", show_alert=True)
    await callback.message.edit_text("✅ Статус обновлён.")
    await callback.message.answer(
        "👑 Вернуться в админ-панель:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👑 Админка", callback_data="admin_panel_back")]
        ])
    )

# ---------- Управление администраторами ----------
@router.callback_query(F.data == "admin_manage_admins")
async def manage_admins(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    with next(get_db()) as db:
        admins = db.query(Admin).all()
        admin_list = "\n".join([f"• `{a.telegram_id}` (добавлен {a.added_at.strftime('%d.%m.%Y')})" for a in admins])

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить админа", callback_data="admin_add")],
        [InlineKeyboardButton(text="❌ Удалить админа", callback_data="admin_remove")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel_back")]
    ])
    await callback.message.edit_text(
        f"👑 *Текущие администраторы*\n{admin_list if admin_list else 'Нет администраторов'}\n\n"
        "Выберите действие:",
        parse_mode="Markdown",
        reply_markup=keyboard
    )
    await callback.answer()

@router.callback_query(F.data == "admin_add")
async def add_admin_start(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    await state.set_state(AddAdminStates.waiting_for_id)
    await callback.message.edit_text(
        "Введите Telegram ID пользователя, которого хотите сделать администратором:"
    )
    await callback.answer()

@router.message(AddAdminStates.waiting_for_id)
async def add_admin_by_id(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав.")
        await state.clear()
        return
    try:
        new_admin_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Введите корректное число.")
        return

    with next(get_db()) as db:
        user = db.query(User).filter(User.telegram_id == new_admin_id).first()
        if not user:
            await message.answer("❌ Пользователь с таким ID не найден в базе. Сначала он должен зарегистрироваться (отправить /start).")
            await state.clear()
            return
        existing = db.query(Admin).filter(Admin.telegram_id == new_admin_id).first()
        if existing:
            await message.answer("❌ Этот пользователь уже является администратором.")
            await state.clear()
            return
        new_admin = Admin(telegram_id=new_admin_id, added_by=message.from_user.id)
        db.add(new_admin)
        db.commit()
        await message.answer(f"✅ Пользователь `{new_admin_id}` теперь администратор.", parse_mode="Markdown")
    await state.clear()

@router.callback_query(F.data == "admin_remove")
async def remove_admin_start(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    await state.set_state(AddAdminStates.waiting_for_id)
    await callback.message.edit_text(
        "Введите Telegram ID администратора, которого хотите удалить:"
    )
    await callback.answer()

@router.message(AddAdminStates.waiting_for_id)
async def remove_admin_by_id(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав.")
        await state.clear()
        return
    try:
        admin_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Введите корректное число.")
        return

    with next(get_db()) as db:
        admin = db.query(Admin).filter(Admin.telegram_id == admin_id).first()
        if not admin:
            await message.answer("❌ Администратор с таким ID не найден.")
            await state.clear()
            return
        db.delete(admin)
        db.commit()
        await message.answer(f"✅ Администратор `{admin_id}` удалён.", parse_mode="Markdown")
    await state.clear()

# ---------- Рассылка ----------
@router.callback_query(F.data == "admin_broadcast")
async def broadcast_start(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    await state.set_state(BroadcastStates.waiting_for_message)
    await callback.message.edit_text(
        "📢 Введите сообщение для рассылки всем пользователям (можно использовать Markdown):\n\n"
        "Чтобы отменить, отправьте /cancel"
    )
    await callback.answer()

@router.message(BroadcastStates.waiting_for_message)
async def broadcast_receive(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав.")
        await state.clear()
        return
    await state.update_data(broadcast_text=message.text)
    await state.set_state(BroadcastStates.confirm)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Отправить", callback_data="broadcast_confirm")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="broadcast_cancel")]
    ])
    await message.answer(
        f"📢 *Предпросмотр сообщения:*\n\n{message.text}\n\nПодтвердите отправку.",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

@router.callback_query(F.data == "broadcast_confirm")
async def broadcast_confirm(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    data = await state.get_data()
    text = data.get("broadcast_text")
    if not text:
        await callback.message.edit_text("❌ Ошибка: текст не найден.")
        await state.clear()
        return

    await callback.message.edit_text("⏳ Начинаю рассылку...")
    sent = 0
    failed = 0
    with next(get_db()) as db:
        users = db.query(User).all()
        for user in users:
            if is_banned(user.telegram_id):
                continue  # не отправляем заблокированным
            try:
                await callback.bot.send_message(user.telegram_id, text, parse_mode="Markdown")
                sent += 1
            except Exception as e:
                logger.error(f"Ошибка отправки пользователю {user.telegram_id}: {e}")
                failed += 1
    await callback.message.edit_text(
        f"✅ Рассылка завершена.\nУспешно: {sent}\nОшибок: {failed}"
    )
    await state.clear()

@router.callback_query(F.data == "broadcast_cancel")
async def broadcast_cancel(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Рассылка отменена.")
    await callback.answer()

# ---------- Список заблокированных ----------
@router.callback_query(F.data == "admin_banned")
async def banned_list(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    with next(get_db()) as db:
        banned = db.query(BannedUser).all()
        if not banned:
            await callback.message.edit_text("✅ Заблокированных пользователей нет.")
            return
        text = "🔨 *Заблокированные пользователи*\n\n"
        for b in banned:
            text += f"• `{b.telegram_id}` — {b.banned_at.strftime('%d.%m.%Y')}\n"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel_back")]
        ])
        await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=keyboard)
    await callback.answer()

# ---------- Кнопка "Назад" в админ-панель ----------
@router.callback_query(F.data == "admin_panel_back")
async def back_to_admin_panel(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    await admin_panel(callback.message)

# ---------- Закрыть админку ----------
@router.callback_query(F.data == "admin_close")
async def admin_close(callback: types.CallbackQuery):
    await callback.message.delete()
    await callback.message.answer("Главное меню:", reply_markup=get_main_menu())
    await callback.answer()
