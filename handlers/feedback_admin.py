import logging
import re
from aiogram import Router, types, F

from config import config

router = Router()
logger = logging.getLogger(__name__)

@router.message(F.chat.id == config.FEEDBACK_CHAT_ID)
async def handle_feedback_reply(message: types.Message):
    # Логируем все входящие сообщения в канале
    logger.info(f"Сообщение в канале от {message.from_user.id}: {message.text or '[не текст]'}")
    
    # Проверяем, является ли сообщение ответом на сообщение бота
    if not message.reply_to_message:
        logger.info("Не ответ, игнорируем")
        return
    
    original = message.reply_to_message
    bot_info = await message.bot.me()
    if original.from_user.id != bot_info.id:
        logger.info("Ответ не на сообщение бота, игнорируем")
        return

    # Извлекаем текст оригинального сообщения
    original_text = original.text or original.caption
    if not original_text:
        logger.warning("Оригинальное сообщение не содержит текста")
        await message.reply("❌ Не удалось обработать: оригинальное сообщение пустое.")
        return

    # Извлекаем ID пользователя
    match = re.search(r'ID:\s*(\d+)', original_text)
    if not match:
        logger.warning(f"ID не найден в тексте: {original_text}")
        await message.reply("❌ Не удалось определить ID пользователя. Убедитесь, что вы отвечаете на сообщение от бота.")
        return

    user_id = int(match.group(1))
    answer_text = message.text or message.caption

    if not answer_text:
        logger.warning("Ответ не содержит текста")
        await message.reply("❌ Ответ не может быть пустым.")
        return

    # Пытаемся отправить ответ пользователю
    try:
        await message.bot.send_message(
            user_id,
            f"📩 *Ответ от администратора:*\n\n{answer_text}",
            parse_mode="Markdown"
        )
        logger.info(f"Ответ успешно отправлен пользователю {user_id}")
        await message.reply("✅ Ответ отправлен пользователю.")
    except Exception as e:
        logger.error(f"Ошибка отправки пользователю {user_id}: {e}")
        await message.reply(f"❌ Не удалось отправить ответ: {e}")

        # Если ошибка связана с блокировкой бота, предложим альтернативу
        if "bot was blocked" in str(e).lower():
            await message.reply("❗ Пользователь заблокировал бота. Сообщение не доставлено.")
