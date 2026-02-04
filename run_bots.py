#!/usr/bin/env python
"""
The Closer Worker - Запускатор Telegram ботов с эмуляцией живого общения
Адаптировано для OpenAI >= 1.0.0
"""
import asyncio
import os
import sys
import django
import logging
import random
from asgiref.sync import sync_to_async

# ===== Django Setup =====
# Убедитесь, что путь к settings правильный
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.utils import timezone
from core.models import BotAgent, Conversation, Message as MessageModel

# ===== Telethon & OpenAI =====
from telethon import TelegramClient, events, functions
from telethon.sessions import StringSession

# Импорт OpenAI с проверкой версии
try:
    from openai import OpenAI, OpenAIError
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    print("⚠️ Библиотека openai не установлена. Выполните: pip install openai")

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("BotWorker")

# Инициализация клиента OpenAI (если ключ есть в переменных среды)
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
ai_client = None

if OPENAI_AVAILABLE and OPENAI_API_KEY:
    try:
        ai_client = OpenAI(api_key=OPENAI_API_KEY)
        logger.info("✅ OpenAI client initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize OpenAI: {e}")
elif not OPENAI_API_KEY:
    logger.warning("⚠️ OPENAI_API_KEY не найден в переменных среды (.env)")

# Хранилище активных клиентов: {bot_id: {'client': client, 'tasks': [asyncio.Task]}}
active_clients = {}


# ==========================================
# 1. Database Async Wrappers
# ==========================================

@sync_to_async
def get_active_bots_from_db():
    """Получает список всех ботов, которые должны работать"""
    return list(BotAgent.objects.filter(
        platform='telegram',
        status='active'
    ).exclude(session_string='').exclude(session_string__isnull=True))

@sync_to_async
def get_bot_by_id(bot_id):
    """Получает свежие данные бота"""
    try:
        return BotAgent.objects.get(id=bot_id)
    except BotAgent.DoesNotExist:
        return None

@sync_to_async
def get_or_create_conversation(bot_instance, user_id, user_name):
    """Создает или возвращает существующий диалог"""
    conversation, created = Conversation.objects.get_or_create(
        bot=bot_instance,
        user_id=user_id,
        defaults={
            'user_name': user_name,
            'started_at': timezone.now()
        }
    )
    conversation.last_message_at = timezone.now()
    conversation.save(update_fields=['last_message_at'])
    return conversation

@sync_to_async
def save_message_to_db(conversation, role, content):
    """Сохраняет сообщение в историю"""
    return MessageModel.objects.create(
        conversation=conversation,
        role=role,
        content=content
    )

@sync_to_async
def increment_bot_stats(bot_id):
    """Обновляет счетчик сообщений"""
    BotAgent.objects.filter(id=bot_id).update(total_messages=django.db.models.F('total_messages') + 1)

@sync_to_async
def mark_bot_invalid(bot_id):
    """Ставит статус invalid при ошибке авторизации"""
    BotAgent.objects.filter(id=bot_id).update(status='invalid')


# ==========================================
# 2. AI Logic (UPDATED for v1.0.0+)
# ==========================================

async def get_chatgpt_response(message_text, system_prompt):
    """Запрос к OpenAI ChatCompletion (новый синтаксис)"""
    if not ai_client:
        return "⚠️ Ошибка: AI клиент не инициализирован (проверьте API ключ)."

    try:
        # OpenAI v1.0+ метод run_in_executor для асинхронности
        loop = asyncio.get_event_loop()
        
        response = await loop.run_in_executor(
            None,
            lambda: ai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message_text}
                ],
                temperature=0.7,
                max_tokens=1000
            )
        )
        # Новый способ получения контента (через атрибуты)
        return response.choices[0].message.content.strip()
        
    except Exception as e:
        logger.error(f"OpenAI Error: {e}")
        return "Извините, я сейчас не могу ответить. Попробуйте позже."


# ==========================================
# 3. Bot Behavior Logic
# ==========================================

async def keep_online_loop(client, bot_name):
    """Фоновая задача: обновляет статус 'Online' каждые 5 минут"""
    while True:
        try:
            # Отправляем статус "Я здесь / В сети"
            await client(functions.account.UpdateStatusRequest(offline=False))
        except Exception as e:
            logger.error(f"[{bot_name}] Failed to update online status: {e}")
        
        # Ждем 5 минут + случайный разброс
        await asyncio.sleep(300 + random.randint(0, 10))


async def handle_message(event, bot_id):
    """Основной обработчик входящих сообщений"""
    
    bot_record = await get_bot_by_id(bot_id)
    if not bot_record or bot_record.status != 'active':
        return

    sender = await event.get_sender()
    user_id = str(sender.id)
    user_name = f"{sender.first_name or ''} {sender.last_name or ''}".strip() or "Unknown"
    text = event.message.text

    if not text:
        return

    logger.info(f"📨 [{bot_record.name}] New msg from {user_name}: {text[:30]}...")

    # Сохраняем входящее
    conversation = await get_or_create_conversation(bot_record, user_id, user_name)
    await save_message_to_db(conversation, 'user', text)

    # --- ЭМУЛЯЦИЯ ЧЕЛОВЕКА ---
    
    # 1. Задержка чтения (10-15 сек)
    read_delay = 10 + random.randint(0, 5)
    await asyncio.sleep(read_delay)

    # 2. Помечаем прочитанным
    await event.message.mark_read()
    
    # 3. Генерируем ответ
    system_prompt = bot_record.system_prompt or "Ты полезный ассистент."
    response_text = await get_chatgpt_response(text, system_prompt)

    # 4. Расчет времени печати
    typing_speed = random.randint(5, 8) # символов в секунду
    typing_duration = len(response_text) / typing_speed
    typing_duration = max(3.0, min(20.0, typing_duration)) # от 3 до 20 сек

    # 5. Статус "Печатает..."
    async with event.client.action(event.chat_id, 'typing'):
        await asyncio.sleep(typing_duration)

    # 6. Отправка ответа
    await event.reply(response_text)
    
    # 7. Сохранение ответа
    await save_message_to_db(conversation, 'bot', response_text)
    await increment_bot_stats(bot_id)
    
    logger.info(f"✅ [{bot_record.name}] Replied to {user_name}")


# ==========================================
# 4. Process Management
# ==========================================

async def start_single_bot(bot_record):
    """Запуск одного клиента Telethon"""
    try:
        api_id = int(bot_record.api_id)
        api_hash = bot_record.api_hash
        session_str = bot_record.session_string

        client = TelegramClient(StringSession(session_str), api_id, api_hash)
        
        await client.connect()
        
        if not await client.is_user_authorized():
            logger.error(f"❌ Bot [{bot_record.name}] session is invalid.")
            await mark_bot_invalid(bot_record.id)
            return

        @client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
        async def wrapper(event, b_id=bot_record.id):
            await handle_message(event, b_id)

        # Запускаем задачу "В сети"
        online_task = asyncio.create_task(keep_online_loop(client, bot_record.name))
        
        active_clients[bot_record.id] = {
            'client': client,
            'tasks': [online_task]
        }
        
        me = await client.get_me()
        logger.info(f"🚀 Bot started: {bot_record.name} (@{me.username})")

    except Exception as e:
        logger.error(f"❌ Error starting bot {bot_record.name}: {e}")


async def stop_single_bot(bot_id):
    """Остановка бота"""
    if bot_id in active_clients:
        data = active_clients[bot_id]
        
        for task in data.get('tasks', []):
            task.cancel()
        
        client = data['client']
        await client.disconnect()
        
        del active_clients[bot_id]
        logger.info(f"🛑 Bot ID {bot_id} stopped")


async def monitor_manager():
    """Мониторинг БД для запуска/остановки ботов"""
    logger.info("👀 Monitor Manager started...")
    
    while True:
        try:
            db_bots = await get_active_bots_from_db()
            db_bot_ids = set(b.id for b in db_bots)
            running_ids = set(active_clients.keys())

            # Запуск новых
            for bot_id in (db_bot_ids - running_ids):
                bot_obj = next(b for b in db_bots if b.id == bot_id)
                asyncio.create_task(start_single_bot(bot_obj))

            # Остановка старых
            for bot_id in (running_ids - db_bot_ids):
                asyncio.create_task(stop_single_bot(bot_id))

        except Exception as e:
            logger.error(f"Monitor error: {e}")
        
        await asyncio.sleep(10)


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        loop.run_until_complete(monitor_manager())
    except KeyboardInterrupt:
        logger.info("👋 Shutting down...")
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()
        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))