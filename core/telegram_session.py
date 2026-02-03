# core/telegram_session.py
"""
Утилиты для работы с Telegram Session Strings
"""
from pyrogram import Client
from pyrogram.errors import (
    SessionPasswordNeeded, 
    PhoneCodeInvalid, 
    PhoneCodeExpired,
    PhoneNumberInvalid,
    ApiIdInvalid,
    BadRequest
)
import logging
import time

logger = logging.getLogger(__name__)


class TelegramSessionManager:
    """Менеджер для создания и управления Telegram сессиями"""
    
    # Словарь для хранения временных данных (не клиентов!)
    _session_data = {}
    
    @staticmethod
    async def send_verification_code(phone_number: str, api_id: str, api_hash: str) -> dict:
        """
        Отправка кода верификации на телефон
        """
        session_name = f"temp_{phone_number.replace('+', '').replace(' ', '')}"
        
        client = Client(
            name=session_name,
            api_id=int(api_id),
            api_hash=api_hash,
            in_memory=True
        )
        
        try:
            await client.connect()
            
            # Отправляем код
            sent_code = await client.send_code(phone_number)
            phone_code_hash = sent_code.phone_code_hash
            
            # Сохраняем данные для повторного использования
            TelegramSessionManager._session_data[session_name] = {
                'api_id': api_id,
                'api_hash': api_hash,
                'phone_number': phone_number,
                'phone_code_hash': phone_code_hash,
                'timestamp': time.time()
            }
            
            logger.info(f"Code sent successfully to {phone_number}")
            
            return {
                'success': True,
                'phone_code_hash': phone_code_hash,
                'session_name': session_name
            }
            
        except PhoneNumberInvalid:
            return {
                'success': False,
                'error': '❌ Неверный формат номера телефона. Используйте формат: +998901234567'
            }
        except ApiIdInvalid:
            return {
                'success': False,
                'error': '❌ Неверный API ID. Проверьте данные с my.telegram.org'
            }
        except BadRequest as e:
            return {
                'success': False,
                'error': f'❌ Ошибка Telegram: {str(e)}'
            }
        except Exception as e:
            logger.error(f"Error sending code: {e}")
            return {
                'success': False,
                'error': f'Ошибка отправки кода: {str(e)}'
            }
        finally:
            try:
                await client.disconnect()
            except:
                pass
    
    
    @staticmethod
    async def create_session_string(
        session_name: str,
        phone_number: str, 
        phone_code_hash: str, 
        code: str,
        api_id: str,
        api_hash: str,
        password: str = None
    ) -> dict:
        """
        Создание session string из кода верификации
        """
        
        # Создаём НОВЫЙ клиент для верификации
        client = Client(
            name=session_name,
            api_id=int(api_id),
            api_hash=api_hash,
            in_memory=True
        )
        
        try:
            await client.connect()
            
            # Пытаемся войти с кодом
            if password:
                # Сначала входим с кодом, потом с паролем
                await client.sign_in(phone_number, phone_code_hash, code)
                await client.check_password(password)
            else:
                # Обычный вход
                await client.sign_in(phone_number, phone_code_hash, code)
            
            # Экспортируем session string
            session_string = await client.export_session_string()
            
            logger.info(f"Session string created successfully for {phone_number}")
            
            # Очищаем временные данные
            if session_name in TelegramSessionManager._session_data:
                del TelegramSessionManager._session_data[session_name]
            
            return {
                'success': True,
                'session_string': session_string
            }
            
        except SessionPasswordNeeded:
            logger.warning(f"2FA required for {phone_number}")
            return {
                'success': False,
                'error': '🔐 Требуется пароль двухфакторной аутентификации',
                'requires_2fa': True
            }
        except PhoneCodeInvalid:
            return {
                'success': False,
                'error': '❌ Неверный код. Проверьте код из Telegram',
                'requires_2fa': False
            }
        except PhoneCodeExpired:
            return {
                'success': False,
                'error': '⏰ Код истёк. Нажмите "Назад" и запросите новый код',
                'requires_2fa': False
            }
        except Exception as e:
            logger.error(f"Error creating session: {e}")
            return {
                'success': False,
                'error': f'Ошибка: {str(e)}',
                'requires_2fa': False
            }
        finally:
            try:
                await client.disconnect()
            except Exception as e:
                logger.error(f"Error disconnecting client: {e}")
    
    
    @staticmethod
    async def validate_session_string(session_string: str, api_id: str, api_hash: str) -> bool:
        """
        Проверка валидности session string
        """
        client = Client(
            name="validator",
            api_id=int(api_id),
            api_hash=api_hash,
            session_string=session_string,
            in_memory=True
        )
        
        try:
            await client.connect()
            me = await client.get_me()
            logger.info(f"Session valid for user: {me.first_name} (@{me.username})")
            return True
        except Exception as e:
            logger.error(f"Invalid session: {e}")
            return False
        finally:
            try:
                await client.disconnect()
            except:
                pass
    
    
    @staticmethod
    async def get_account_info(session_string: str, api_id: str, api_hash: str) -> dict:
        """
        Получение информации об аккаунте
        """
        client = Client(
            name="info_getter",
            api_id=int(api_id),
            api_hash=api_hash,
            session_string=session_string,
            in_memory=True
        )
        
        try:
            await client.connect()
            me = await client.get_me()
            
            return {
                'success': True,
                'user': {
                    'id': me.id,
                    'first_name': me.first_name,
                    'last_name': me.last_name,
                    'username': me.username,
                    'phone': me.phone_number
                }
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
        finally:
            try:
                await client.disconnect()
            except:
                pass
    
    
    @staticmethod
    def cleanup_expired_sessions():
        """Очистка истекших сессий (старше 5 минут)"""
        current_time = time.time()
        expired = [
            name for name, data in TelegramSessionManager._session_data.items()
            if current_time - data['timestamp'] > 300  
        ]
        for name in expired:
            del TelegramSessionManager._session_data[name]
            logger.info(f"Cleaned up expired session: {name}")