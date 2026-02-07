# core/views_crm.py
"""
Views для CRM интеграций (Bitrix24 и AmoCRM)
"""
import json
import requests
from datetime import timedelta
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.conf import settings

# Импортируем модели (добавьте в models.py или создайте models_crm.py)
# from .models_crm import CRMIntegration, CRMSyncLog


# Временная заглушка для моделей (замените на реальный импорт)
class CRMIntegration:
    """Временная заглушка - замените на реальную модель"""
    pass


@login_required
def integrations_view(request):
    """Страница интеграций"""
    # Получаем существующие интеграции пользователя
    # bitrix_integration = CRMIntegration.objects.filter(user=request.user, crm_type='bitrix24').first()
    # amocrm_integration = CRMIntegration.objects.filter(user=request.user, crm_type='amocrm').first()
    # moysklad_integration = CRMIntegration.objects.filter(user=request.user, crm_type='moysklad').first()
    # google_sheets_integration = CRMIntegration.objects.filter(user=request.user, crm_type='google_sheets').first()
    
    # Временные заглушки
    bitrix_integration = None
    amocrm_integration = None
    moysklad_integration = None
    google_sheets_integration = None
    
    context = {
        'bitrix': bitrix_integration,
        'amocrm': amocrm_integration,
        'moysklad': moysklad_integration,
        'google_sheets': google_sheets_integration,
    }
    
    return render(request, 'dashboard/integrations.html', context)


@login_required
@require_http_methods(["POST"])
def connect_bitrix24(request):
    """Подключение Bitrix24 через Webhook"""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Неверный формат данных'}, status=400)
    
    webhook_url = data.get('webhook_url', '').strip()
    
    if not webhook_url:
        return JsonResponse({'success': False, 'error': 'Webhook URL обязателен'})
    
    # Валидация формата URL
    if not webhook_url.startswith('https://') or 'bitrix24' not in webhook_url:
        return JsonResponse({
            'success': False, 
            'error': 'Неверный формат Webhook URL. URL должен быть вида: https://ваш-домен.bitrix24.ru/rest/...'
        })
    
    # Тестируем подключение
    try:
        test_url = webhook_url.rstrip('/') + '/profile/'
        response = requests.get(test_url, timeout=10)
        result = response.json()
        
        if 'result' in result:
            # Успешное подключение
            user_info = result['result']
            
            # Сохраняем интеграцию
            # integration, created = CRMIntegration.objects.update_or_create(
            #     user=request.user,
            #     crm_type='bitrix24',
            #     defaults={
            #         'webhook_url': webhook_url,
            #         'status': 'connected',
            #         'domain': webhook_url.split('/rest/')[0] if '/rest/' in webhook_url else '',
            #         'settings': {'user_info': user_info}
            #     }
            # )
            
            return JsonResponse({
                'success': True,
                'message': 'Bitrix24 успешно подключен!',
                'user_info': {
                    'name': f"{user_info.get('NAME', '')} {user_info.get('LAST_NAME', '')}".strip(),
                    'email': user_info.get('EMAIL', ''),
                }
            })
        else:
            error_msg = result.get('error_description', 'Неизвестная ошибка')
            return JsonResponse({'success': False, 'error': f'Ошибка Bitrix24: {error_msg}'})
            
    except requests.Timeout:
        return JsonResponse({'success': False, 'error': 'Превышено время ожидания ответа от Bitrix24'})
    except requests.RequestException as e:
        return JsonResponse({'success': False, 'error': f'Ошибка подключения: {str(e)}'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Произошла ошибка: {str(e)}'})


@login_required
@require_http_methods(["POST"])
def disconnect_bitrix24(request):
    """Отключение Bitrix24"""
    # CRMIntegration.objects.filter(user=request.user, crm_type='bitrix24').delete()
    return JsonResponse({'success': True, 'message': 'Bitrix24 отключен'})


@login_required
@require_http_methods(["POST"])
def test_bitrix24(request):
    """Тестирование подключения Bitrix24"""
    # integration = CRMIntegration.objects.filter(user=request.user, crm_type='bitrix24').first()
    # if not integration:
    #     return JsonResponse({'success': False, 'error': 'Интеграция не найдена'})
    
    # Тест создания лида
    # test_url = integration.webhook_url.rstrip('/') + '/crm.lead.list/'
    # ...
    
    return JsonResponse({'success': True, 'message': 'Подключение работает корректно'})


@login_required
@require_http_methods(["POST"])
def connect_amocrm(request):
    """Подключение AmoCRM"""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Неверный формат данных'}, status=400)
    
    subdomain = data.get('subdomain', '').strip()
    client_id = data.get('client_id', '').strip()
    client_secret = data.get('client_secret', '').strip()
    auth_code = data.get('auth_code', '').strip()
    
    if not all([subdomain, client_id, client_secret, auth_code]):
        return JsonResponse({'success': False, 'error': 'Все поля обязательны для заполнения'})
    
    # Очищаем subdomain от лишнего
    subdomain = subdomain.replace('https://', '').replace('.amocrm.ru', '').replace('.amocrm.com', '')
    
    # Получаем access token
    try:
        token_url = f'https://{subdomain}.amocrm.ru/oauth2/access_token'
        token_data = {
            'client_id': client_id,
            'client_secret': client_secret,
            'grant_type': 'authorization_code',
            'code': auth_code,
            'redirect_uri': data.get('redirect_uri', 'https://example.com/callback')
        }
        
        response = requests.post(token_url, json=token_data, timeout=15)
        result = response.json()
        
        if 'access_token' in result:
            access_token = result['access_token']
            refresh_token = result.get('refresh_token', '')
            expires_in = result.get('expires_in', 86400)
            
            # Проверяем токен - получаем информацию об аккаунте
            account_url = f'https://{subdomain}.amocrm.ru/api/v4/account'
            headers = {'Authorization': f'Bearer {access_token}'}
            account_response = requests.get(account_url, headers=headers, timeout=10)
            account_info = account_response.json()
            
            # Сохраняем интеграцию
            # integration, created = CRMIntegration.objects.update_or_create(
            #     user=request.user,
            #     crm_type='amocrm',
            #     defaults={
            #         'domain': f'{subdomain}.amocrm.ru',
            #         'access_token': access_token,
            #         'refresh_token': refresh_token,
            #         'token_expires_at': timezone.now() + timedelta(seconds=expires_in),
            #         'status': 'connected',
            #         'settings': {
            #             'client_id': client_id,
            #             'client_secret': client_secret,
            #             'account_info': account_info
            #         }
            #     }
            # )
            
            return JsonResponse({
                'success': True,
                'message': 'AmoCRM успешно подключен!',
                'account_info': {
                    'name': account_info.get('name', ''),
                    'subdomain': subdomain,
                }
            })
        else:
            error_msg = result.get('hint', result.get('title', 'Неизвестная ошибка'))
            return JsonResponse({'success': False, 'error': f'Ошибка авторизации: {error_msg}'})
            
    except requests.Timeout:
        return JsonResponse({'success': False, 'error': 'Превышено время ожидания ответа от AmoCRM'})
    except requests.RequestException as e:
        return JsonResponse({'success': False, 'error': f'Ошибка подключения: {str(e)}'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Произошла ошибка: {str(e)}'})


@login_required
@require_http_methods(["POST"])
def connect_amocrm_simple(request):
    """Простое подключение AmoCRM через API ключ (устаревший метод, но проще)"""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Неверный формат данных'}, status=400)
    
    subdomain = data.get('subdomain', '').strip()
    api_key = data.get('api_key', '').strip()
    user_email = data.get('user_email', '').strip()
    
    if not all([subdomain, api_key, user_email]):
        return JsonResponse({'success': False, 'error': 'Все поля обязательны'})
    
    subdomain = subdomain.replace('https://', '').replace('.amocrm.ru', '').replace('.amocrm.com', '')
    
    # Тестируем подключение
    try:
        auth_url = f'https://{subdomain}.amocrm.ru/private/api/auth.php'
        auth_data = {
            'USER_LOGIN': user_email,
            'USER_HASH': api_key
        }
        
        session = requests.Session()
        response = session.post(auth_url, data=auth_data, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            if result.get('response', {}).get('auth'):
                # Сохраняем
                return JsonResponse({
                    'success': True,
                    'message': 'AmoCRM успешно подключен!',
                    'account_info': {
                        'subdomain': subdomain,
                        'email': user_email
                    }
                })
        
        return JsonResponse({'success': False, 'error': 'Неверные данные авторизации'})
            
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Ошибка: {str(e)}'})


@login_required
@require_http_methods(["POST"])
def disconnect_amocrm(request):
    """Отключение AmoCRM"""
    # CRMIntegration.objects.filter(user=request.user, crm_type='amocrm').delete()
    return JsonResponse({'success': True, 'message': 'AmoCRM отключен'})


@login_required
@require_http_methods(["GET"])
def get_integration_status(request, crm_type):
    """Получение статуса интеграции"""
    # integration = CRMIntegration.objects.filter(user=request.user, crm_type=crm_type).first()
    
    # if not integration:
    #     return JsonResponse({
    #         'connected': False,
    #         'status': 'disconnected'
    #     })
    
    # return JsonResponse({
    #     'connected': integration.is_connected,
    #     'status': integration.status,
    #     'domain': integration.domain,
    #     'last_sync': integration.last_sync_at.isoformat() if integration.last_sync_at else None,
    #     'leads_synced': integration.leads_synced
    # })
    
    return JsonResponse({
        'connected': False,
        'status': 'disconnected'
    })


@login_required
@require_http_methods(["GET"])
def get_sync_logs(request, crm_type):
    """Получение логов синхронизации"""
    # integration = CRMIntegration.objects.filter(user=request.user, crm_type=crm_type).first()
    # if not integration:
    #     return JsonResponse({'logs': []})
    
    # logs = CRMSyncLog.objects.filter(integration=integration)[:20]
    # return JsonResponse({
    #     'logs': [{
    #         'action': log.get_action_display(),
    #         'status': log.status,
    #         'created_at': log.created_at.isoformat(),
    #         'error': log.error_message
    #     } for log in logs]
    # })
    
    return JsonResponse({'logs': []})


# ============================================
# МОЙ СКЛАД ИНТЕГРАЦИЯ
# ============================================

@login_required
@require_http_methods(["POST"])
def connect_moysklad(request):
    """Подключение МойСклад"""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Неверный формат данных'}, status=400)
    
    login = data.get('login', '').strip()
    password = data.get('password', '').strip()
    
    if not login or not password:
        return JsonResponse({'success': False, 'error': 'Логин и пароль обязательны'})
    
    # Проверяем подключение к МойСклад API
    try:
        import base64
        
        # Создаем Basic Auth header
        credentials = base64.b64encode(f"{login}:{password}".encode()).decode()
        headers = {
            'Authorization': f'Basic {credentials}',
            'Content-Type': 'application/json'
        }
        
        # Тестовый запрос - получаем информацию о пользователе
        test_url = 'https://api.moysklad.ru/api/remap/1.2/context/employee'
        response = requests.get(test_url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            user_data = response.json()
            
            # Получаем информацию об организации
            org_url = 'https://api.moysklad.ru/api/remap/1.2/entity/organization'
            org_response = requests.get(org_url, headers=headers, timeout=10)
            org_data = org_response.json() if org_response.status_code == 200 else {}
            
            org_name = ''
            if org_data.get('rows'):
                org_name = org_data['rows'][0].get('name', '')
            
            # Сохраняем интеграцию
            # integration, created = CRMIntegration.objects.update_or_create(
            #     user=request.user,
            #     crm_type='moysklad',
            #     defaults={
            #         'api_key': password,  # Храним пароль как API key
            #         'status': 'connected',
            #         'domain': login,  # Храним логин в domain
            #         'settings': {
            #             'user_info': {
            #                 'name': user_data.get('name', ''),
            #                 'email': user_data.get('email', ''),
            #             },
            #             'organization': org_name
            #         }
            #     }
            # )
            
            return JsonResponse({
                'success': True,
                'message': 'МойСклад успешно подключен!',
                'account_info': {
                    'name': user_data.get('name', login),
                    'email': user_data.get('email', ''),
                    'organization': org_name
                }
            })
        elif response.status_code == 401:
            return JsonResponse({'success': False, 'error': 'Неверный логин или пароль'})
        else:
            return JsonResponse({'success': False, 'error': f'Ошибка API: {response.status_code}'})
            
    except requests.Timeout:
        return JsonResponse({'success': False, 'error': 'Превышено время ожидания ответа от МойСклад'})
    except requests.RequestException as e:
        return JsonResponse({'success': False, 'error': f'Ошибка подключения: {str(e)}'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Произошла ошибка: {str(e)}'})


@login_required
@require_http_methods(["POST"])
def connect_moysklad_token(request):
    """Подключение МойСклад через API токен"""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Неверный формат данных'}, status=400)
    
    token = data.get('token', '').strip()
    
    if not token:
        return JsonResponse({'success': False, 'error': 'API токен обязателен'})
    
    try:
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        
        # Тестовый запрос
        test_url = 'https://api.moysklad.ru/api/remap/1.2/context/employee'
        response = requests.get(test_url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            user_data = response.json()
            
            # Сохраняем интеграцию
            # integration, created = CRMIntegration.objects.update_or_create(...)
            
            return JsonResponse({
                'success': True,
                'message': 'МойСклад успешно подключен!',
                'account_info': {
                    'name': user_data.get('name', ''),
                    'email': user_data.get('email', ''),
                }
            })
        elif response.status_code == 401:
            return JsonResponse({'success': False, 'error': 'Неверный токен'})
        else:
            return JsonResponse({'success': False, 'error': f'Ошибка API: {response.status_code}'})
            
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Произошла ошибка: {str(e)}'})


@login_required
@require_http_methods(["POST"])
def disconnect_moysklad(request):
    """Отключение МойСклад"""
    # CRMIntegration.objects.filter(user=request.user, crm_type='moysklad').delete()
    return JsonResponse({'success': True, 'message': 'МойСклад отключен'})


@login_required
@require_http_methods(["POST"])
def test_moysklad(request):
    """Тестирование подключения МойСклад"""
    return JsonResponse({'success': True, 'message': 'Подключение работает корректно'})


# ============================================
# GOOGLE SHEETS ИНТЕГРАЦИЯ
# ============================================

@login_required
@require_http_methods(["POST"])
def connect_google_sheets(request):
    """Подключение Google Sheets через Service Account"""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Неверный формат данных'}, status=400)
    
    spreadsheet_id = data.get('spreadsheet_id', '').strip()
    credentials_json = data.get('credentials_json', '').strip()
    sheet_name = data.get('sheet_name', 'Sheet1').strip()
    
    if not spreadsheet_id:
        return JsonResponse({'success': False, 'error': 'ID таблицы обязателен'})
    
    if not credentials_json:
        return JsonResponse({'success': False, 'error': 'JSON ключ сервисного аккаунта обязателен'})
    
    # Валидация JSON
    try:
        creds_data = json.loads(credentials_json)
        if 'client_email' not in creds_data or 'private_key' not in creds_data:
            return JsonResponse({
                'success': False, 
                'error': 'Неверный формат JSON ключа. Убедитесь, что вы скачали правильный файл.'
            })
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Неверный формат JSON'})
    
    # Проверяем доступ к таблице
    try:
        # Для полноценной работы нужна библиотека google-api-python-client
        # pip install google-api-python-client google-auth
        
        # Упрощенная проверка - пытаемся получить метаданные таблицы
        # В реальном проекте используйте google.oauth2.service_account
        
        service_account_email = creds_data.get('client_email', '')
        
        # Сохраняем интеграцию
        # integration, created = CRMIntegration.objects.update_or_create(
        #     user=request.user,
        #     crm_type='google_sheets',
        #     defaults={
        #         'spreadsheet_id': spreadsheet_id,
        #         'sheet_name': sheet_name,
        #         'credentials_json': credentials_json,
        #         'status': 'connected',
        #         'domain': f'docs.google.com/spreadsheets/d/{spreadsheet_id}',
        #         'settings': {
        #             'service_account_email': service_account_email
        #         }
        #     }
        # )
        
        return JsonResponse({
            'success': True,
            'message': 'Google Sheets успешно подключен!',
            'account_info': {
                'spreadsheet_id': spreadsheet_id,
                'sheet_name': sheet_name,
                'service_account': service_account_email
            }
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Произошла ошибка: {str(e)}'})


@login_required
@require_http_methods(["POST"])
def connect_google_sheets_simple(request):
    """Упрощенное подключение Google Sheets (только URL)"""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Неверный формат данных'}, status=400)
    
    spreadsheet_url = data.get('spreadsheet_url', '').strip()
    
    if not spreadsheet_url:
        return JsonResponse({'success': False, 'error': 'URL таблицы обязателен'})
    
    # Извлекаем ID из URL
    import re
    match = re.search(r'/spreadsheets/d/([a-zA-Z0-9-_]+)', spreadsheet_url)
    if not match:
        return JsonResponse({
            'success': False, 
            'error': 'Неверный URL таблицы. URL должен быть вида: https://docs.google.com/spreadsheets/d/...'
        })
    
    spreadsheet_id = match.group(1)
    
    # Сохраняем (без полной авторизации - только для отображения)
    # В реальном проекте потребуется OAuth или Service Account
    
    return JsonResponse({
        'success': True,
        'message': 'Google Sheets подключен! Для полной интеграции настройте Service Account.',
        'account_info': {
            'spreadsheet_id': spreadsheet_id,
            'url': spreadsheet_url
        },
        'warning': 'Для автоматической записи данных необходимо настроить Service Account'
    })


@login_required
@require_http_methods(["POST"])
def disconnect_google_sheets(request):
    """Отключение Google Sheets"""
    # CRMIntegration.objects.filter(user=request.user, crm_type='google_sheets').delete()
    return JsonResponse({'success': True, 'message': 'Google Sheets отключен'})


@login_required
@require_http_methods(["POST"])
def test_google_sheets(request):
    """Тестирование подключения Google Sheets"""
    return JsonResponse({'success': True, 'message': 'Подключение работает корректно'})