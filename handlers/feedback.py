import logging
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import config
from keyboards.main_menu import get_more_submenu

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
    logger.info(f"Feedback message received from {message.from_user.id}: text={message.text!r}, has_photo={bool(message.photo)}")
    
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Сообщение отменено", reply_markup=get_more_submenu())
        return

    # Если сообщение содержит не только текст (например, фото), берём текст из caption
    text = message.text or message.caption
    if not text:
        await message.answer("❌ Пожалуйста, отправьте текстовое сообщение.")
        return

    user_info = f"От пользователя: {message.from_user.full_name}"
    if message.from_user.username:
        user_info += f" (@{message.from_user.username})"
    user_info += f"\nID: {message.from_user.id}"
    user_info += f"\n\n*Текст:*\n{text}"

    # Если есть фото, можно отправить его вместе с текстом (в канал)
    if config.FEEDBACK_CHAT_ID:
        try:
            if message.photo:
                # Отправляем фото с подписью
                await message.bot.send_photo(
                    chat_id=config.FEEDBACK_CHAT_ID,
                    photo=message.photo[-1].file_id,
                    caption=user_info,
                    parse_mode="Markdown"
                )
            else:
                await message.bot.send_message(
                    config.FEEDBACK_CHAT_ID,
                    user_info,
                    parse_mode="Markdown"
                )
            logger.info(f"Feedback sent to channel {config.FEEDBACK_CHAT_ID}")
            await message.answer(
                "✅ Ваше сообщение отправлено администратору. Ответ придёт в этот чат.",
                reply_markup=get_more_submenu()
            )
        except Exception as e:
            logger.error(f"Error sending to channel: {e}")
            await message.answer("❌ Произошла ошибка при отправке. Попробуйте позже.")
    else:
        # Старая логика – отправка в ЛС админу
        if not config.ADMIN_IDS:
            await message.answer("❌ Администратор не настроен.")
            await state.clear()
            return
        admin_id = config.ADMIN_IDS[0]
        try:
            if message.photo:
                await message.bot.send_photo(
                    chat_id=admin_id,
                    photo=message.photo[-1].file_id,
                    caption=f"📩 *Новое сообщение от пользователя*\n\n{user_info}",
                    parse_mode="Markdown"
                )
            else:
                await message.bot.send_message(
                    admin_id,
                    f"📩 *Новое сообщение от пользователя*\n\n{user_info}",
                    parse_mode="Markdown"
                )
            logger.info(f"Feedback sent to admin {admin_id}")
            await message.answer(
                "✅ Ваше сообщение отправлено администратору.",
                reply_markup=get_more_submenu()
            )
        except Exception as e:
            logger.error(f"Error sending to admin: {e}")
            await message.answer("❌ Ошибка отправки.")

    await state.clear()

@router.message(Command("cancel"))
async def cancel_feedback(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is not None:
        await state.clear()
        await message.answer("❌ Действие отменено", reply_markup=get_more_submenu())
    else:
        await message.answer("Нет активного действия для отмены.")
