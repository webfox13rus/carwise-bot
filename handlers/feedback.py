import logging
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import config
from keyboards.main_menu import get_main_menu

router = Router()
logger = logging.getLogger(__name__)

class Feedback(StatesGroup):
    waiting_for_message = State()

@router.message(F.text == "✉️ Связаться с админом")
async def feedback_start(message: types.Message, state: FSMContext):
    await state.set_state(Feedback.waiting_for_message)
    await message.answer(
        "📝 Напишите ваше сообщение для администратора. "
        "Он получит его и ответит вам при необходимости.\n\n"
        "Чтобы отменить, отправьте /cancel или нажмите '❌ Отмена'.",
        reply_markup=types.ReplyKeyboardMarkup(
            keyboard=[[types.KeyboardButton(text="❌ Отмена")]],
            resize_keyboard=True
        )
    )

@router.message(Feedback.waiting_for_message)
async def process_feedback(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Сообщение отменено", reply_markup=get_main_menu())
        return

    # Получаем ID администратора из config.ADMIN_IDS (первый в списке)
    admin_id = config.ADMIN_IDS[0] if config.ADMIN_IDS else None
    if not admin_id:
        await message.answer("❌ Ошибка: администратор не настроен. Сообщение не отправлено.")
        await state.clear()
        return

    # Формируем текст для администратора
    user_info = f"Пользователь: {message.from_user.full_name}"
    if message.from_user.username:
        user_info += f" (@{message.from_user.username})"
    user_info += f"\nID: {message.from_user.id}"

    await message.bot.send_message(
        admin_id,
        f"📩 *Новое сообщение от пользователя*\n\n"
        f"{user_info}\n\n"
        f"*Текст:*\n{message.text}",
        parse_mode="Markdown"
    )

    await message.answer(
        "✅ Ваше сообщение отправлено администратору. Он ответит вам в ближайшее время.",
        reply_markup=get_main_menu()
    )
    await state.clear()
