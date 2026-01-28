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

def login_view(request):
    """Страница входа/регистрации"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'login.html')

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
    
    
    return JsonResponse({
        'success': True,
        'message': f'Документ "{file.name}" загружен',
        'document_id': knowledge.id
    })
