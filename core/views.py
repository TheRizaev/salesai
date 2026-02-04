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
from django.core.paginator import Paginator
import json
import os

# Допустимые расширения файлов
ALLOWED_EXTENSIONS = {
    'pdf', 'doc', 'docx', 'txt', 'csv', 'xlsx', 'xls', 'json', 'md', 'rtf'
}

# Максимальный размер файла (50MB)
MAX_FILE_SIZE = 50 * 1024 * 1024


def get_file_type(filename):
    """Определяет тип файла по расширению"""
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    if ext in ALLOWED_EXTENSIONS:
        return ext
    return 'other'


def run_async(coro):
    """Helper для запуска async функций в sync контексте"""
    import asyncio
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
    
    # Количество документов в базе знаний
    knowledge_count = KnowledgeBase.objects.filter(user=request.user).count()
    
    context = {
        'bots': user_bots,
        'total_bots': user_bots.count(),
        'active_bots': user_bots.filter(status='active').count(),
        'total_conversations': analytics['total_conversations'] or 0,
        'total_messages': analytics['total_messages'] or 0,
        'total_leads': analytics['total_leads'] or 0,
        'recent_conversations': recent_conversations,
        'knowledge_count': knowledge_count,
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
    
    # База знаний бота
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


# ===== KNOWLEDGE BASE VIEWS =====

@login_required
def knowledge_base_view(request):
    """Управление базой знаний пользователя"""
    # Получаем параметры фильтрации
    bot_id = request.GET.get('bot')
    file_type = request.GET.get('type')
    search = request.GET.get('search', '').strip()
    
    # Базовый запрос - документы пользователя
    documents = KnowledgeBase.objects.filter(user=request.user)
    
    # Фильтрация по боту
    if bot_id:
        documents = documents.filter(bot_id=bot_id)
    
    # Фильтрация по типу файла
    if file_type:
        documents = documents.filter(file_type=file_type)
    
    # Поиск по названию
    if search:
        documents = documents.filter(title__icontains=search)
    
    # Пагинация
    paginator = Paginator(documents, 12)  # 12 документов на страницу
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Боты пользователя для фильтра
    user_bots = BotAgent.objects.filter(user=request.user)
    
    # Статистика
    total_documents = KnowledgeBase.objects.filter(user=request.user).count()
    total_size = KnowledgeBase.objects.filter(user=request.user).aggregate(
        total=Sum('file_size')
    )['total'] or 0
    
    # Форматирование размера
    def format_size(size):
        for unit in ['Б', 'КБ', 'МБ', 'ГБ']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} ТБ"
    
    # Типы файлов для фильтра
    file_types = KnowledgeBase.objects.filter(user=request.user).values_list(
        'file_type', flat=True
    ).distinct()
    
    context = {
        'documents': page_obj,
        'bots': user_bots,
        'selected_bot': bot_id,
        'selected_type': file_type,
        'search_query': search,
        'total_documents': total_documents,
        'total_size': format_size(total_size),
        'file_types': list(file_types),
        'allowed_extensions': ', '.join(ALLOWED_EXTENSIONS),
    }
    
    return render(request, 'dashboard/knowledge_base.html', context)


@login_required
@require_http_methods(["POST"])
def upload_knowledge_file(request):
    """Загрузка файла в базу знаний"""
    if 'file' not in request.FILES:
        return JsonResponse({
            'success': False, 
            'error': 'Файл не выбран'
        }, status=400)
    
    file = request.FILES['file']
    bot_id = request.POST.get('bot_id')
    description = request.POST.get('description', '')
    
    # Проверка размера файла
    if file.size > MAX_FILE_SIZE:
        return JsonResponse({
            'success': False,
            'error': f'Файл слишком большой. Максимум: {MAX_FILE_SIZE // (1024*1024)} МБ'
        }, status=400)
    
    # Проверка расширения
    file_extension = file.name.rsplit('.', 1)[-1].lower() if '.' in file.name else ''
    if file_extension not in ALLOWED_EXTENSIONS:
        return JsonResponse({
            'success': False,
            'error': f'Недопустимый тип файла. Разрешены: {", ".join(ALLOWED_EXTENSIONS)}'
        }, status=400)
    
    # Определяем тип файла
    file_type = get_file_type(file.name)
    
    # Получаем бота, если указан
    bot = None
    if bot_id:
        try:
            bot = BotAgent.objects.get(id=bot_id, user=request.user)
        except BotAgent.DoesNotExist:
            pass
    
    # Создаем запись
    knowledge = KnowledgeBase.objects.create(
        user=request.user,
        bot=bot,
        title=file.name,
        description=description,
        file=file,
        file_type=file_type,
        file_size=file.size
    )
    
    return JsonResponse({
        'success': True,
        'message': f'Файл "{file.name}" успешно загружен',
        'document': {
            'id': knowledge.id,
            'title': knowledge.title,
            'file_type': knowledge.file_type,
            'file_size': knowledge.file_size_display,
            'file_icon': knowledge.file_icon,
            'file_color': knowledge.file_color,
            'created_at': knowledge.created_at.strftime('%d.%m.%Y %H:%M'),
        }
    })


@login_required
@require_http_methods(["POST"])
def upload_multiple_files(request):
    """Загрузка нескольких файлов"""
    files = request.FILES.getlist('files')
    bot_id = request.POST.get('bot_id')
    
    if not files:
        return JsonResponse({
            'success': False,
            'error': 'Файлы не выбраны'
        }, status=400)
    
    # Получаем бота, если указан
    bot = None
    if bot_id:
        try:
            bot = BotAgent.objects.get(id=bot_id, user=request.user)
        except BotAgent.DoesNotExist:
            pass
    
    uploaded = []
    errors = []
    
    for file in files:
        # Проверка размера
        if file.size > MAX_FILE_SIZE:
            errors.append(f'{file.name}: файл слишком большой')
            continue
        
        # Проверка расширения
        file_extension = file.name.rsplit('.', 1)[-1].lower() if '.' in file.name else ''
        if file_extension not in ALLOWED_EXTENSIONS:
            errors.append(f'{file.name}: недопустимый тип файла')
            continue
        
        # Создаем запись
        file_type = get_file_type(file.name)
        knowledge = KnowledgeBase.objects.create(
            user=request.user,
            bot=bot,
            title=file.name,
            file=file,
            file_type=file_type,
            file_size=file.size
        )
        
        uploaded.append({
            'id': knowledge.id,
            'title': knowledge.title,
            'file_size': knowledge.file_size_display,
        })
    
    return JsonResponse({
        'success': True,
        'uploaded': uploaded,
        'uploaded_count': len(uploaded),
        'errors': errors,
        'error_count': len(errors),
    })


@login_required
@require_http_methods(["GET"])
def get_knowledge_document(request, document_id):
    """Получение информации о документе"""
    document = get_object_or_404(KnowledgeBase, id=document_id, user=request.user)
    
    return JsonResponse({
        'success': True,
        'document': {
            'id': document.id,
            'title': document.title,
            'description': document.description,
            'file_type': document.file_type,
            'file_size': document.file_size_display,
            'file_url': document.file.url,
            'file_icon': document.file_icon,
            'file_color': document.file_color,
            'bot_id': document.bot_id,
            'bot_name': document.bot.name if document.bot else None,
            'created_at': document.created_at.strftime('%d.%m.%Y %H:%M'),
            'updated_at': document.updated_at.strftime('%d.%m.%Y %H:%M'),
        }
    })


@login_required
@require_http_methods(["POST"])
def update_knowledge_document(request, document_id):
    """Обновление информации о документе"""
    document = get_object_or_404(KnowledgeBase, id=document_id, user=request.user)
    
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Неверный формат данных'}, status=400)
    
    # Обновляем поля
    if 'title' in data:
        document.title = data['title']
    if 'description' in data:
        document.description = data['description']
    if 'bot_id' in data:
        if data['bot_id']:
            try:
                bot = BotAgent.objects.get(id=data['bot_id'], user=request.user)
                document.bot = bot
            except BotAgent.DoesNotExist:
                pass
        else:
            document.bot = None
    
    document.save()
    
    return JsonResponse({
        'success': True,
        'message': 'Документ обновлен'
    })


@login_required
@require_http_methods(["DELETE"])
def delete_knowledge_document(request, document_id):
    """Удаление документа"""
    document = get_object_or_404(KnowledgeBase, id=document_id, user=request.user)
    
    # Удаляем файл с диска
    if document.file:
        try:
            if os.path.isfile(document.file.path):
                os.remove(document.file.path)
        except Exception:
            pass  # Игнорируем ошибки удаления файла
    
    document_title = document.title
    document.delete()
    
    return JsonResponse({
        'success': True,
        'message': f'Документ "{document_title}" удален'
    })


@login_required
@require_http_methods(["POST"])
def delete_multiple_documents(request):
    """Удаление нескольких документов"""
    try:
        data = json.loads(request.body)
        document_ids = data.get('ids', [])
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Неверный формат данных'}, status=400)
    
    if not document_ids:
        return JsonResponse({'success': False, 'error': 'Не выбраны документы'}, status=400)
    
    documents = KnowledgeBase.objects.filter(id__in=document_ids, user=request.user)
    deleted_count = 0
    
    for doc in documents:
        # Удаляем файл с диска
        if doc.file:
            try:
                if os.path.isfile(doc.file.path):
                    os.remove(doc.file.path)
            except Exception:
                pass
        doc.delete()
        deleted_count += 1
    
    return JsonResponse({
        'success': True,
        'message': f'Удалено документов: {deleted_count}'
    })


# ===== ANALYTICS VIEW =====

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
    """Загрузка документа в базу знаний бота"""
    bot = get_object_or_404(BotAgent, id=agent_id, user=request.user)
    
    if 'file' not in request.FILES:
        return JsonResponse({'success': False, 'message': 'Файл не загружен'}, status=400)
    
    file = request.FILES['file']
    
    # Проверка размера
    if file.size > MAX_FILE_SIZE:
        return JsonResponse({
            'success': False,
            'message': f'Файл слишком большой. Максимум: {MAX_FILE_SIZE // (1024*1024)} МБ'
        }, status=400)
    
    # Определяем тип файла
    file_type = get_file_type(file.name)
    
    knowledge = KnowledgeBase.objects.create(
        user=request.user,
        bot=bot,
        title=file.name,
        file=file,
        file_type=file_type,
        file_size=file.size
    )
    
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
    
    api_id = str(data.get('api_id', '')).strip()
    api_hash = str(data.get('api_hash', '')).strip()
    
    if not api_id or not api_hash:
        return JsonResponse({
            'success': False, 
            'error': 'API ID и API Hash обязательны'
        })
    
    if not api_id.isdigit():
        return JsonResponse({
            'success': False,
            'error': 'API ID должен содержать только цифры'
        })
    
    if len(api_hash) < 30:
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
    
    # Здесь была бы интеграция с Telethon
    # Для демонстрации возвращаем успех
    
    bot.phone_number = phone_number
    bot.status = 'waiting_code'
    bot.save()
    
    return JsonResponse({
        'success': True,
        'message': 'Код отправлен на ваш Telegram'
    })


@login_required
@require_http_methods(["POST"])
def telegram_verify_code(request, agent_id):
    """Шаг 3: Верификация кода"""
    bot = get_object_or_404(BotAgent, id=agent_id, user=request.user)
    data = json.loads(request.body)
    
    code = data.get('code', '').strip()
    
    if not code:
        return JsonResponse({'success': False, 'error': 'Код обязателен'})
    
    # Здесь была бы верификация через Telethon
    # Для демонстрации возвращаем успех
    
    bot.status = 'active'
    bot.save()
    
    return JsonResponse({
        'success': True,
        'message': 'Бот успешно подключен!'
    })


@login_required
@require_http_methods(["POST"])
def telegram_validate_session(request, agent_id):
    """Проверка валидности session string"""
    bot = get_object_or_404(BotAgent, id=agent_id, user=request.user)
    
    if not bot.session_string:
        return JsonResponse({'success': False, 'error': 'Session string не найден'})
    
    # Здесь была бы проверка через Telethon
    return JsonResponse({'success': True, 'message': 'Сессия валидна'})


@login_required
@require_http_methods(["GET"])
def telegram_get_account_info(request, agent_id):
    """Получение информации об аккаунте"""
    bot = get_object_or_404(BotAgent, id=agent_id, user=request.user)
    
    if not bot.session_string:
        return JsonResponse({'success': False, 'error': 'Бот не подключен'})
    
    # Здесь была бы интеграция с Telethon
    return JsonResponse({
        'success': True,
        'user': {
            'id': 123456789,
            'first_name': 'Test',
            'last_name': 'User',
            'username': 'testuser',
            'phone': bot.phone_number
        }
    })


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