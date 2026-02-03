from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout
from django.contrib import messages
from django.db.models import Sum, Count
from django.utils import timezone
from datetime import timedelta
from .models import BotAgent, KnowledgeBase, Conversation, Message, Analytics
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
import json
from .telegram_auth import send_code_request, verify_code
from .telegram_session import TelegramSessionManager
import asyncio


def run_async(coro):
    """Helper для запуска async функций в sync контексте"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(coro)

# ===== PUBLIC VIEWS =====

def home(request):
    """Главная страница"""
    return render(request, 'index.html')

def pricing(request):
    """Страница с тарифами"""
    return render(request, 'pricing.html')

def templates_view(request):
    """Страница с шаблонами"""
    return render(request, 'templates.html')

def docs(request):
    """Документация"""
    return render(request, 'docs.html')

# ===== DASHBOARD VIEWS =====

@login_required
def dashboard(request):
    """Главная панель управления"""
    user_bots = BotAgent.objects.filter(user=request.user)
    
    # Статистика за последние 7 дней
    week_ago = timezone.now().date() - timedelta(days=7)
    analytics = Analytics.objects.filter(
        bot__user=request.user,
        date__gte=week_ago
    ).aggregate(
        total_conversations=Sum('new_conversations'),
        total_messages=Sum('messages_sent'),
        total_leads=Sum('leads_captured')
    )
    
    # Последние диалоги
    recent_conversations = Conversation.objects.filter(
        bot__user=request.user
    ).order_by('-last_message_at')[:5]
    
    context = {
        'bots': user_bots,
        'total_bots': user_bots.count(),
        'active_bots': user_bots.filter(status='active').count(),
        'total_conversations': analytics['total_conversations'] or 0,
        'total_messages': analytics['total_messages'] or 0,
        'total_leads': analytics['total_leads'] or 0,
        'recent_conversations': recent_conversations,
    }
    
    return render(request, 'dashboard/index.html', context)


@login_required
def agents_list(request):
    """Список ботов пользователя"""
    bots = BotAgent.objects.filter(user=request.user)
    
    context = {
        'bots': bots,
    }
    
    return render(request, 'dashboard/agents.html', context)


@login_required
def agent_detail(request, agent_id):
    """Детальная информация о боте"""
    bot = get_object_or_404(BotAgent, id=agent_id, user=request.user)
    
    # Статистика за последние 30 дней
    thirty_days_ago = timezone.now().date() - timedelta(days=30)
    daily_stats = Analytics.objects.filter(
        bot=bot,
        date__gte=thirty_days_ago
    ).order_by('date')
    
    # База знаний
    knowledge_base = KnowledgeBase.objects.filter(bot=bot)
    
    # Последние диалоги
    recent_conversations = Conversation.objects.filter(bot=bot).order_by('-last_message_at')[:10]
    
    context = {
        'bot': bot,
        'daily_stats': daily_stats,
        'knowledge_base': knowledge_base,
        'recent_conversations': recent_conversations,
    }
    
    return render(request, 'dashboard/agent_detail.html', context)


@login_required
def create_agent(request):
    """Создание нового бота"""
    if request.method == 'POST':
        name = request.POST.get('name')
        platform = request.POST.get('platform')
        description = request.POST.get('description', '')
        
        bot = BotAgent.objects.create(
            user=request.user,
            name=name,
            platform=platform,
            description=description,
            status='inactive'
        )
        
        messages.success(request, f'Бот "{name}" успешно создан!')
        return redirect('agent_detail', agent_id=bot.id)
    
    return render(request, 'dashboard/create_agent.html')


@login_required
def conversations_list(request):
    """Список всех диалогов"""
    bot_id = request.GET.get('bot')
    
    conversations = Conversation.objects.filter(bot__user=request.user)
    
    if bot_id:
        conversations = conversations.filter(bot_id=bot_id)
    
    conversations = conversations.order_by('-last_message_at')
    
    user_bots = BotAgent.objects.filter(user=request.user)
    
    context = {
        'conversations': conversations,
        'bots': user_bots,
        'selected_bot': bot_id,
    }
    
    return render(request, 'dashboard/conversations.html', context)


@login_required
def conversation_detail(request, conversation_id):
    """Просмотр конкретного диалога"""
    conversation = get_object_or_404(
        Conversation,
        id=conversation_id,
        bot__user=request.user
    )
    
    messages_list = Message.objects.filter(conversation=conversation).order_by('created_at')
    
    context = {
        'conversation': conversation,
        'messages': messages_list,
    }
    
    return render(request, 'dashboard/conversation_detail.html', context)


@login_required
def knowledge_base_view(request):
    """Управление базой знаний"""
    bot_id = request.GET.get('bot')
    
    if bot_id:
        bot = get_object_or_404(BotAgent, id=bot_id, user=request.user)
        documents = KnowledgeBase.objects.filter(bot=bot)
    else:
        documents = KnowledgeBase.objects.filter(bot__user=request.user)
        bot = None
    
    user_bots = BotAgent.objects.filter(user=request.user)
    
    context = {
        'documents': documents,
        'bots': user_bots,
        'selected_bot': bot,
    }
    
    return render(request, 'dashboard/knowledge_base.html', context)


@login_required
def analytics_view(request):
    """Страница аналитики"""
    bot_id = request.GET.get('bot')
    
    user_bots = BotAgent.objects.filter(user=request.user)
    
    if bot_id:
        selected_bot = get_object_or_404(BotAgent, id=bot_id, user=request.user)
        bots_queryset = [selected_bot]
    else:
        selected_bot = None
        bots_queryset = user_bots
    
    # Статистика за последние 30 дней
    thirty_days_ago = timezone.now().date() - timedelta(days=30)
    
    analytics_data = Analytics.objects.filter(
        bot__in=bots_queryset,
        date__gte=thirty_days_ago
    ).values('date').annotate(
        conversations=Sum('new_conversations'),
        messages=Sum('messages_sent'),
        leads=Sum('leads_captured')
    ).order_by('date')
    
    # Общая статистика
    total_stats = Analytics.objects.filter(
        bot__in=bots_queryset
    ).aggregate(
        total_conversations=Sum('new_conversations'),
        total_messages=Sum('messages_sent'),
        total_leads=Sum('leads_captured')
    )
    
    context = {
        'bots': user_bots,
        'selected_bot': selected_bot,
        'analytics_data': list(analytics_data),
        'total_stats': total_stats,
    }
    
    return render(request, 'dashboard/analytics.html', context)


@login_required
def settings_view(request):
    """Настройки аккаунта"""
    if request.method == 'POST':
        user = request.user
        user.first_name = request.POST.get('first_name', '')
        user.last_name = request.POST.get('last_name', '')
        user.save()
        
        messages.success(request, 'Настройки сохранены!')
        return redirect('settings')
    
    context = {
        'user': request.user,
    }
    
    return render(request, 'dashboard/settings.html', context)


# ===== API ENDPOINTS =====

@login_required
@require_http_methods(["POST"])
def toggle_bot_status(request, agent_id):
    """Включение/выключение бота"""
    bot = get_object_or_404(BotAgent, id=agent_id, user=request.user)
    
    if bot.status == 'active':
        bot.status = 'inactive'
    else:
        bot.status = 'active'
    
    bot.save()
    
    return JsonResponse({
        'success': True,
        'status': bot.status,
        'message': f'Бот {"активирован" if bot.status == "active" else "остановлен"}'
    })


@login_required
@require_http_methods(["DELETE"])
def delete_bot(request, agent_id):
    """Удаление бота"""
    bot = get_object_or_404(BotAgent, id=agent_id, user=request.user)
    bot_name = bot.name
    bot.delete()
    
    return JsonResponse({
        'success': True,
        'message': f'Бот "{bot_name}" удален'
    })


@login_required
@require_http_methods(["POST"])
def upload_knowledge(request, agent_id):
    """Загрузка документа в базу знаний"""
    bot = get_object_or_404(BotAgent, id=agent_id, user=request.user)
    
    if 'file' not in request.FILES:
        return JsonResponse({'success': False, 'message': 'Файл не загружен'}, status=400)
    
    file = request.FILES['file']
    
    # Определяем тип файла
    file_extension = file.name.split('.')[-1].lower()
    
    knowledge = KnowledgeBase.objects.create(
        bot=bot,
        title=file.name,
        file=file,
        file_type=file_extension
    )
    
    # TODO: Здесь должна быть обработка файла и извлечение текста
    
    return JsonResponse({
        'success': True,
        'message': f'Документ "{file.name}" загружен',
        'document_id': knowledge.id
    })

@login_required
def telegram_connect_view(request, agent_id):
    """Страница подключения Telegram"""
    bot = get_object_or_404(BotAgent, id=agent_id, user=request.user)
    return render(request, 'dashboard/telegram_connect.html', {'bot': bot})


@login_required
@require_http_methods(["POST"])
def telegram_save_credentials(request, agent_id):
    """Шаг 1: Сохранение API ID и API Hash"""
    bot = get_object_or_404(BotAgent, id=agent_id, user=request.user)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Неверный формат JSON'})
    
    # Безопасное приведение к строке перед strip, на случай если пришло число
    api_id = str(data.get('api_id', '')).strip()
    api_hash = str(data.get('api_hash', '')).strip()
    
    if not api_id or not api_hash:
        return JsonResponse({
            'success': False, 
            'error': 'API ID и API Hash обязательны'
        })
    
    # Проверка, что API ID является числом
    if not api_id.isdigit():
         return JsonResponse({
            'success': False,
            'error': 'API ID должен содержать только цифры'
        })
    
    try:
        # Проверяем конвертацию
        int(api_id)
    except ValueError:
        return JsonResponse({
            'success': False,
            'error': 'API ID должен быть числом'
        })
    
    if len(api_hash) < 30: # Немного ослабил проверку длины
        return JsonResponse({
            'success': False,
            'error': 'API Hash слишком короткий'
        })
    
    bot.api_id = api_id
    bot.api_hash = api_hash
    bot.save()
    
    return JsonResponse({
        'success': True,
        'message': 'API ключи сохранены'
    })

@login_required
@require_http_methods(["POST"])
def telegram_send_code(request, agent_id):
    """Шаг 2: Отправка кода верификации"""
    bot = get_object_or_404(BotAgent, id=agent_id, user=request.user)
    data = json.loads(request.body)
    
    phone_number = data.get('phone_number', '').strip()
    
    if not phone_number:
        return JsonResponse({'success': False, 'error': 'Номер телефона обязателен'})
    
    if not bot.api_id or not bot.api_hash:
        return JsonResponse({'success': False, 'error': 'Сначала сохраните API ключи'})
    
    result = run_async(
        send_code_request(
            phone_number=phone_number,
            api_id=bot.api_id,
            api_hash=bot.api_hash
        )
    )

    if result['success']:
        request.session[f'bot_{agent_id}_phone'] = phone_number
        request.session[f'bot_{agent_id}_hash'] = result['phone_code_hash']
        request.session[f'bot_{agent_id}_session_name'] = result['session_name'] 
        request.session.modified = True
        
        bot.phone_number = phone_number
        bot.phone_code_hash = result['phone_code_hash']
        bot.status = 'waiting_code'
        bot.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Код отправлен на ваш Telegram'
        })
    else:
        return JsonResponse({
            'success': False,
            'error': result.get('error', 'Ошибка отправки кода')
        })


@login_required
@require_http_methods(["POST"])
def telegram_verify_code(request, agent_id):
    """Шаг 3: Верификация кода и создание session string"""
    bot = get_object_or_404(BotAgent, id=agent_id, user=request.user)
    data = json.loads(request.body)
    
    code = data.get('code', '').strip()
    password = data.get('password', '').strip() or None
    
    if not code:
        return JsonResponse({'success': False, 'error': 'Код обязателен'})
    
    # Получаем данные из сессии
    phone_number = request.session.get(f'bot_{agent_id}_phone')
    phone_code_hash = request.session.get(f'bot_{agent_id}_hash')
    session_name = request.session.get(f'bot_{agent_id}_session_name')
    
    if not all([phone_number, phone_code_hash, session_name]):
        return JsonResponse({
            'success': False,
            'error': 'Сессия истекла. Нажмите "Назад" и начните заново.'
        })
    
    if not bot.api_id or not bot.api_hash:
        return JsonResponse({'success': False, 'error': 'API ключи не найдены'})
    
    # Создаём session string
    result = run_async(
        verify_code( 
            phone_number=phone_number,
            phone_code_hash=phone_code_hash,
            code=code,
            api_id=bot.api_id,
            api_hash=bot.api_hash,
            password=password
        )
    )
    
    if result['success']:
        # Сохраняем session string
        bot.session_string = result['session_string']
        bot.status = 'active'
        bot.save()
        
        # Очищаем сессию
        try:
            del request.session[f'bot_{agent_id}_phone']
            del request.session[f'bot_{agent_id}_hash']
            del request.session[f'bot_{agent_id}_session_name']
            request.session.modified = True
        except KeyError:
            pass
        
        return JsonResponse({
            'success': True,
            'message': 'Бот успешно подключен!'
        })
    else:
        if result.get('requires_2fa'):
            return JsonResponse({
                'success': False,
                'error': result['error'],
                'requires_2fa': True
            })
        
        bot.status = 'invalid'
        bot.save()
        
        return JsonResponse({
            'success': False,
            'error': result.get('error', 'Ошибка верификации')
        })


@login_required
@require_http_methods(["POST"])
def telegram_validate_session(request, agent_id):
    """Проверка валидности session string"""
    bot = get_object_or_404(BotAgent, id=agent_id, user=request.user)
    
    if not bot.session_string:
        return JsonResponse({'success': False, 'error': 'Session string не найден'})
    
    is_valid = run_async(
        TelegramSessionManager.validate_session_string(
            session_string=bot.session_string,
            api_id=bot.api_id,
            api_hash=bot.api_hash
        )
    )
    
    if is_valid:
        bot.status = 'active'
        bot.save()
        return JsonResponse({'success': True, 'message': 'Сессия валидна'})
    else:
        bot.status = 'invalid'
        bot.save()
        return JsonResponse({'success': False, 'error': 'Сессия недействительна'})


@login_required
@require_http_methods(["GET"])
def telegram_get_account_info(request, agent_id):
    """Получение информации об аккаунте"""
    bot = get_object_or_404(BotAgent, id=agent_id, user=request.user)
    
    if not bot.session_string:
        return JsonResponse({'success': False, 'error': 'Бот не подключен'})
    
    result = run_async(
        TelegramSessionManager.get_account_info(
            session_string=bot.session_string,
            api_id=bot.api_id,
            api_hash=bot.api_hash
        )
    )
    
    return JsonResponse(result)


@login_required
@require_http_methods(["POST"])
def telegram_disconnect(request, agent_id):
    """Отключение Telegram"""
    bot = get_object_or_404(BotAgent, id=agent_id, user=request.user)
    
    bot.session_string = ''
    bot.phone_code_hash = ''
    bot.status = 'inactive'
    bot.save()
    
    return JsonResponse({'success': True, 'message': 'Telegram отключен'})


@login_required
@require_http_methods(["POST"])
def update_bot_prompt(request, agent_id):
    """Обновление промпта бота"""
    bot = get_object_or_404(BotAgent, id=agent_id, user=request.user)
    data = json.loads(request.body)
    
    bot.system_prompt = data.get('system_prompt', '')
    bot.save()
    
    return JsonResponse({
        'success': True,
        'message': 'Промпт обновлен'
    })


@login_required
@require_http_methods(["POST"])
def update_bot(request, agent_id):
    """Обновление настроек бота"""
    bot = get_object_or_404(BotAgent, id=agent_id, user=request.user)
    data = json.loads(request.body)
    
    bot.name = data.get('name', bot.name)
    bot.description = data.get('description', bot.description)
    bot.save()
    
    return JsonResponse({
        'success': True,
        'message': 'Настройки обновлены'
    })