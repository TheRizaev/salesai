# SalesAI Bot/core/telegram_auth.py
from pyrogram import Client
from pyrogram.errors import SessionPasswordNeeded, PhoneCodeInvalid, PhoneCodeExpired

async def send_code_request(phone_number, api_id, api_hash):
    """Отправка кода (Шаг 1) - In-Memory"""
    # Создаем клиент в памяти, без привязки к файлам
    client = Client(
        name="temp_auth_session",
        api_id=int(api_id),
        api_hash=api_hash,
        in_memory=True
    )
    
    try:
        await client.connect()
        sent_code = await client.send_code(phone_number)
        
        # ВАЖНО: Экспортируем строку сессии ПРЯМО СЕЙЧАС.
        # В ней содержится Auth Key, который нужен для валидации кода.
        temp_session_string = await client.export_session_string()
        
        phone_code_hash = sent_code.phone_code_hash
        
        await client.disconnect()
        
        return {
            'success': True, 
            'phone_code_hash': phone_code_hash,
            'temp_session_string': temp_session_string # Возвращаем строку, чтобы сохранить её в Django Session
        }
    except Exception as e:
        try:
            await client.disconnect()
        except:
            pass
        return {'success': False, 'error': str(e)}


async def verify_code(phone_number, phone_code_hash, code, api_id, api_hash, temp_session_string, password=None):
    """Проверка кода (Шаг 2) - In-Memory"""
    
    # Восстанавливаем ту же самую сессию из строки!
    client = Client(
        name="temp_auth_session",
        api_id=int(api_id),
        api_hash=api_hash,
        session_string=temp_session_string, # Используем сохраненную строку
        in_memory=True
    )
    
    try:
        await client.connect()
        
        try:
            await client.sign_in(phone_number, phone_code_hash, code)
        except SessionPasswordNeeded:
            if password:
                await client.check_password(password)
            else:
                await client.disconnect()
                return {'success': False, 'error': 'Нужен 2FA пароль', 'requires_2fa': True}

        # Если успешно — получаем финальную строку (она уже авторизована)
        final_session_string = await client.export_session_string()
        await client.disconnect()
        
        return {'success': True, 'session_string': final_session_string}
    
    except PhoneCodeInvalid:
        await client.disconnect()
        return {'success': False, 'error': '❌ Неверный код.'}
    except PhoneCodeExpired:
        await client.disconnect()
        return {'success': False, 'error': '⏰ Код истёк. Попробуйте снова.'}
    except Exception as e:
        await client.disconnect()
        return {'success': False, 'error': f'Ошибка: {str(e)}'}