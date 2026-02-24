import logging
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import config
from keyboards.main_menu import get_main_menu, get_more_submenu

router = Router()
logger = logging.getLogger(__name__)

class Feedback(StatesGroup):
    waiting_for_message = State()

@router.message(F.text == "✉️ Связаться с админом")
async def feedback_start(message: types.Message, state: FSMContext):
    logger.info(f"Feedback started by user {message.from_user.id}")
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
        await message.answer("❌ Сообщение отменено", reply_markup=get_more_submenu())
        return

    # Формируем информацию о пользователе
    user_info = f"От пользователя: {message.from_user.full_name}"
    if message.from_user.username:
        user_info += f" (@{message.from_user.username})"
    user_info += f"\nID: {message.from_user.id}"
    user_info += f"\n\n*Текст:*\n{message.text}"

    # Если задан канал обратной связи, отправляем туда
    if config.FEEDBACK_CHAT_ID:
        try:
            await message.bot.send_message(
                config.FEEDBACK_CHAT_ID,
                user_info,
                parse_mode="Markdown"
            )
            await message.answer(
                "✅ Ваше сообщение отправлено администратору. Ответ придёт в этот чат.",
                reply_markup=get_more_submenu()
            )
        except Exception as e:
            logger.error(f"Ошибка отправки в канал: {e}")
            await message.answer("❌ Произошла ошибка при отправке. Попробуйте позже.")
    else:
        # Если канал не задан, отправляем первому администратору в ЛС (старый вариант)
        if not config.ADMIN_IDS:
            await message.answer("❌ Ошибка: администратор не настроен. Сообщение не отправлено.")
            await state.clear()
            return

        admin_id = config.ADMIN_IDS[0]
        try:
            await message.bot.send_message(
                admin_id,
                f"📩 *Новое сообщение от пользователя*\n\n{user_info}",
                parse_mode="Markdown"
            )
            await message.answer(
                "✅ Ваше сообщение отправлено администратору. Он ответит вам в ближайшее время.",
                reply_markup=get_more_submenu()
            )
        except Exception as e:
            logger.error(f"Ошибка отправки администратору: {e}")
            await message.answer("❌ Произошла ошибка при отправке. Попробуйте позже.")

    await state.clear()

# Обработчик отмены через команду /cancel
@router.message(Command("cancel"))
async def cancel_feedback(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is not None:
        await state.clear()
        await message.answer("❌ Действие отменено", reply_markup=get_more_submenu())
    else:
        await message.answer("Нет активного действия для отмены.")
