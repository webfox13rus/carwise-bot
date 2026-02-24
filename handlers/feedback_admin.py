import logging
import re
from aiogram import Router, types, F

from config import config

router = Router()
logger = logging.getLogger(__name__)

# Фильтр только на вашу группу (ID из лога)
@router.message(F.chat.id == config.FEEDBACK_CHAT_ID)
async def handle_feedback_reply(message: types.Message):
    logger.info(f"Получено сообщение в группе {message.chat.id} от {message.from_user.id}: {message.text}")
    
    if not message.reply_to_message:
        logger.info("Не ответ, игнорируем")
        return

    original = message.reply_to_message
    logger.info(f"Оригинальное сообщение: {original.text or original.caption}")

    # Проверяем, что отвечаем на сообщение бота
    bot_info = await message.bot.get_me()
    if original.from_user.id != bot_info.id:
        logger.info("Ответ не на сообщение бота")
        return

    # Извлекаем ID пользователя
    original_text = original.text or original.caption or ""
    match = re.search(r'ID:\s*(\d+)', original_text)
    if not match:
        logger.warning("ID пользователя не найден")
        await message.reply("❌ Не удалось определить ID пользователя.")
        return

    user_id = int(match.group(1))
    answer_text = message.text or message.caption
    if not answer_text:
        await message.reply("❌ Ответ не может быть пустым.")
        return

    # Отправляем ответ пользователю
    try:
        await message.bot.send_message(
            user_id,
            f"📩 *Ответ от администратора:*\n\n{answer_text}",
            parse_mode="Markdown"
        )
        logger.info(f"✅ Ответ отправлен пользователю {user_id}")
        await message.reply("✅ Ответ отправлен пользователю.")
    except Exception as e:
        logger.error(f"❌ Ошибка отправки ответа пользователю {user_id}: {e}")
        await message.reply(f"❌ Не удалось отправить ответ: {e}")
