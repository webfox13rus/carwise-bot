import logging
import asyncio
from datetime import datetime, timedelta
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from database import SessionLocal, User, Car, FuelEvent, MaintenanceEvent, Insurance, Admin, BannedUser
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
    with SessionLocal() as db:
        if user_id in config.ADMIN_IDS:
            return True
        admin = db.query(Admin).filter(Admin.telegram_id == user_id).first()
        return admin is not None

def is_banned(user_id: int) -> bool:
    with SessionLocal() as db:
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

# ... (остальные обработчики без изменений, кроме функций с сессиями) ...

# В функции toggle_ban используем SessionLocal
@router.callback_query(F.data.startswith("admin_toggle_ban_"))
async def toggle_ban(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    target_id = int(callback.data.split("_")[-1])
    with SessionLocal() as db:
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

# В функции broadcast_confirm добавим задержку
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
    with SessionLocal() as db:
        users = db.query(User).all()
        for user in users:
            if is_banned(user.telegram_id):
                continue
            try:
                await callback.bot.send_message(user.telegram_id, text, parse_mode="Markdown")
                sent += 1
                await asyncio.sleep(0.05)  # задержка 50 мс
            except Exception as e:
                logger.error(f"Ошибка отправки пользователю {user.telegram_id}: {e}")
                failed += 1
    await callback.message.edit_text(
        f"✅ Рассылка завершена.\nУспешно: {sent}\nОшибок: {failed}"
    )
    await state.clear()

# Добавим защиту от самоудаления в remove_admin_by_id
@router.message(AddAdminStates.waiting_for_id)  # это для удаления
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

    # Запрет на самоудаление
    if admin_id == message.from_user.id:
        await message.answer("❌ Нельзя удалить самого себя.")
        await state.clear()
        return

    with SessionLocal() as db:
        admin = db.query(Admin).filter(Admin.telegram_id == admin_id).first()
        if not admin:
            await message.answer("❌ Администратор с таким ID не найден.")
            await state.clear()
            return
        db.delete(admin)
        db.commit()
        await message.answer(f"✅ Администратор `{admin_id}` удалён.", parse_mode="Markdown")
    await state.clear()
