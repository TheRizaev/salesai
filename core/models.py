from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class BotAgent(models.Model):
    """Модель чат-бота"""
    STATUS_CHOICES = [
        ('active', 'Активен'),
        ('inactive', 'Неактивен'),
        ('paused', 'Приостановлен'),
    ]
    
    PLATFORM_CHOICES = [
        ('telegram', 'Telegram'),
        ('whatsapp', 'WhatsApp'),
        ('vk', 'VK'),
        ('instagram', 'Instagram'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bots')
    name = models.CharField(max_length=200, verbose_name='Название бота')
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES, verbose_name='Платформа')
    bot_token = models.CharField(max_length=500, blank=True, verbose_name='Токен бота')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='inactive', verbose_name='Статус')
    
    avatar = models.ImageField(upload_to='bot_avatars/', blank=True, null=True, verbose_name='Аватар')
    description = models.TextField(blank=True, verbose_name='Описание')
    
    # Статистика
    total_conversations = models.IntegerField(default=0, verbose_name='Всего диалогов')
    total_messages = models.IntegerField(default=0, verbose_name='Всего сообщений')
    conversion_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='Конверсия %')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создан')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Обновлен')
    
    class Meta:
        verbose_name = 'Бот'
        verbose_name_plural = 'Боты'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.platform})"


class KnowledgeBase(models.Model):
    """База знаний для RAG"""
    bot = models.ForeignKey(BotAgent, on_delete=models.CASCADE, related_name='knowledge_base')
    title = models.CharField(max_length=300, verbose_name='Название документа')
    file = models.FileField(upload_to='knowledge_base/', verbose_name='Файл')
    file_type = models.CharField(max_length=10, verbose_name='Тип файла')
    content_extracted = models.TextField(blank=True, verbose_name='Извлеченный текст')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Загружен')
    
    class Meta:
        verbose_name = 'Документ базы знаний'
        verbose_name_plural = 'База знаний'
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title


class Conversation(models.Model):
    """Диалог с пользователем"""
    bot = models.ForeignKey(BotAgent, on_delete=models.CASCADE, related_name='conversations')
    user_id = models.CharField(max_length=200, verbose_name='ID пользователя')
    user_name = models.CharField(max_length=200, blank=True, verbose_name='Имя пользователя')
    
    started_at = models.DateTimeField(auto_now_add=True, verbose_name='Начат')
    last_message_at = models.DateTimeField(auto_now=True, verbose_name='Последнее сообщение')
    
    is_lead = models.BooleanField(default=False, verbose_name='Является лидом')
    lead_email = models.EmailField(blank=True, verbose_name='Email лида')
    lead_phone = models.CharField(max_length=50, blank=True, verbose_name='Телефон лида')
    
    class Meta:
        verbose_name = 'Диалог'
        verbose_name_plural = 'Диалоги'
        ordering = ['-last_message_at']
    
    def __str__(self):
        return f"Диалог с {self.user_name or self.user_id}"


class Message(models.Model):
    """Сообщение в диалоге"""
    ROLE_CHOICES = [
        ('user', 'Пользователь'),
        ('bot', 'Бот'),
        ('system', 'Система'),
    ]
    
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, verbose_name='Роль')
    content = models.TextField(verbose_name='Содержание')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Отправлено')
    
    class Meta:
        verbose_name = 'Сообщение'
        verbose_name_plural = 'Сообщения'
        ordering = ['created_at']
    
    def __str__(self):
        return f"{self.role}: {self.content[:50]}"


class Analytics(models.Model):
    """Аналитика по дням"""
    bot = models.ForeignKey(BotAgent, on_delete=models.CASCADE, related_name='analytics')
    date = models.DateField(verbose_name='Дата')
    
    new_conversations = models.IntegerField(default=0, verbose_name='Новых диалогов')
    messages_sent = models.IntegerField(default=0, verbose_name='Отправлено сообщений')
    leads_captured = models.IntegerField(default=0, verbose_name='Захвачено лидов')
    
    class Meta:
        verbose_name = 'Аналитика'
        verbose_name_plural = 'Аналитика'
        ordering = ['-date']
        unique_together = ['bot', 'date']
    
    def __str__(self):
        return f"{self.bot.name} - {self.date}"
