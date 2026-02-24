import logging
import re
from aiogram import Router, types, F
from aiogram.filters import ChatMemberUpdatedFilter, IS_NOT_MEMBER, IS_MEMBER
from aiogram.types import ChatMemberUpdated

from config import config
from database import get_db, User
from keyboards.main_menu import get_main_menu

router = Router()
logger = logging.getLogger(__name__)

# Хендлер для сообщений в канале обратной связи
@router.message(F.chat.id == config.FEEDBACK_CHAT_ID)
async def handle_feedback_reply(message: types.Message):
    # Проверяем, является ли сообщение ответом на сообщение бота
    if not message.reply_to_message or message.reply_to_message.from_user.id != config.BOT_TOKEN.split(':')[0]:
        return

    # Извлекаем ID пользователя из текста оригинального сообщения
    original_text = message.reply_to_message.text or message.reply_to_message.caption
    if not original_text:
        return

    # Ожидаем формат: "От пользователя @username (ID: 123456789): ..."
    match = re.search(r'ID:\s*(\d+)', original_text)
    if not match:
        logger.warning("Не удалось найти ID пользователя в сообщении")
        return

    user_id = int(match.group(1))
    answer_text = message.text

    if not answer_text:
        return

    try:
        await message.bot.send_message(
            user_id,
            f"📩 *Ответ от администратора:*\n\n{answer_text}",
            parse_mode="Markdown"
        )
        # Отправляем подтверждение в канал
        await message.reply("✅ Ответ отправлен пользователю.")
    except Exception as e:
        logger.error(f"Ошибка отправки ответа пользователю {user_id}: {e}")
        await message.reply("❌ Не удалось отправить ответ.")
