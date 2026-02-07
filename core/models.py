from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class BotAgent(models.Model):
    """Модель чат-бота"""
    STATUS_CHOICES = [
        ('waiting_code', 'Ожидание кода'),
        ('active', 'Активен'),
        ('inactive', 'Неактивен'),
        ('paused', 'Приостановлен'),
        ('invalid', 'Ошибка авторизации'),
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
    
    # Telegram auth data
    phone_number = models.CharField(max_length=20, blank=True, verbose_name='Номер телефона')
    phone_code_hash = models.CharField(max_length=500, blank=True, verbose_name='Хеш кода')
    session_string = models.TextField(blank=True, null=True, verbose_name='Session String')
    api_id = models.CharField(max_length=50, null=True, blank=True, verbose_name='API ID')
    api_hash = models.CharField(max_length=100, blank=True, verbose_name='API Hash')
    
    # Промпт для AI
    system_prompt = models.TextField(blank=True, verbose_name='Системный промпт', 
                                     default='Ты - профессиональный sales-ассистент.')
    
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


def knowledge_base_upload_path(instance, filename):
    """Генерирует путь для загрузки: knowledge_base/username/filename"""
    # Получаем email пользователя
    if instance.user and instance.user.email:
        # Берем часть до @
        username = instance.user.email.split('@')[0]
    elif instance.user and instance.user.username:
        username = instance.user.username
    else:
        username = 'anonymous'
    
    # Очищаем username от недопустимых символов
    import re
    username = re.sub(r'[^\w\-.]', '_', username)
    
    return f'knowledge_base/{username}/{filename}'


class KnowledgeBase(models.Model):
    """База знаний для RAG"""
    FILE_TYPE_CHOICES = [
        ('pdf', 'PDF'),
        ('doc', 'Word (DOC)'),
        ('docx', 'Word (DOCX)'),
        ('txt', 'Text'),
        ('csv', 'CSV'),
        ('xlsx', 'Excel (XLSX)'),
        ('xls', 'Excel (XLS)'),
        ('json', 'JSON'),
        ('md', 'Markdown'),
        ('other', 'Другой'),
    ]
    
    # Связь может быть с ботом ИЛИ напрямую с пользователем
    bot = models.ForeignKey(BotAgent, on_delete=models.CASCADE, related_name='knowledge_base', null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='knowledge_base', null=True, blank=True)
    
    title = models.CharField(max_length=300, verbose_name='Название документа')
    description = models.TextField(blank=True, verbose_name='Описание')
    file = models.FileField(upload_to=knowledge_base_upload_path, verbose_name='Файл')
    file_type = models.CharField(max_length=10, choices=FILE_TYPE_CHOICES, verbose_name='Тип файла')
    file_size = models.BigIntegerField(default=0, verbose_name='Размер файла (байт)')
    content_extracted = models.TextField(blank=True, verbose_name='Извлеченный текст')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Загружен')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Обновлен')
    
    class Meta:
        verbose_name = 'Документ базы знаний'
        verbose_name_plural = 'База знаний'
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title
    
    @property
    def file_size_display(self):
        """Возвращает размер файла в человекочитаемом формате"""
        size = self.file_size
        for unit in ['Б', 'КБ', 'МБ', 'ГБ']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} ТБ"
    
    @property
    def file_icon(self):
        """Возвращает иконку FontAwesome для типа файла"""
        icons = {
            'pdf': 'fa-file-pdf',
            'doc': 'fa-file-word',
            'docx': 'fa-file-word',
            'txt': 'fa-file-lines',
            'csv': 'fa-file-csv',
            'xlsx': 'fa-file-excel',
            'xls': 'fa-file-excel',
            'json': 'fa-file-code',
            'md': 'fa-file-lines',
        }
        return icons.get(self.file_type, 'fa-file')
    
    @property
    def file_color(self):
        """Возвращает цвет для типа файла"""
        colors = {
            'pdf': '#ef4444',
            'doc': '#3b82f6',
            'docx': '#3b82f6',
            'txt': '#6b7280',
            'csv': '#22c55e',
            'xlsx': '#22c55e',
            'xls': '#22c55e',
            'json': '#f59e0b',
            'md': '#8b5cf6',
        }
        return colors.get(self.file_type, '#6b7280')


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
    
class CRMIntegration(models.Model):
    """Базовая модель CRM интеграции"""
    CRM_CHOICES = [
        ('bitrix24', 'Bitrix24'),
        ('amocrm', 'AmoCRM'),
        ('moysklad', 'МойСклад'),
        ('google_sheets', 'Google Sheets'),
    ]
    
    STATUS_CHOICES = [
        ('disconnected', 'Отключено'),
        ('connecting', 'Подключение...'),
        ('connected', 'Подключено'),
        ('error', 'Ошибка'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='crm_integrations')
    crm_type = models.CharField(max_length=20, choices=CRM_CHOICES, verbose_name='Тип CRM')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='disconnected', verbose_name='Статус')
    
    # Общие поля
    domain = models.CharField(max_length=255, blank=True, verbose_name='Домен/URL')
    
    # OAuth токены
    access_token = models.TextField(blank=True, verbose_name='Access Token')
    refresh_token = models.TextField(blank=True, verbose_name='Refresh Token')
    token_expires_at = models.DateTimeField(null=True, blank=True, verbose_name='Срок действия токена')
    
    # Webhook (для Bitrix24)
    webhook_url = models.CharField(max_length=500, blank=True, verbose_name='Webhook URL')
    
    # API Key (для AmoCRM)
    api_key = models.CharField(max_length=255, blank=True, verbose_name='API Key')
    
    # Google Sheets специфичные поля
    spreadsheet_id = models.CharField(max_length=255, blank=True, verbose_name='ID таблицы')
    sheet_name = models.CharField(max_length=100, blank=True, default='Sheet1', verbose_name='Название листа')
    credentials_json = models.TextField(blank=True, verbose_name='Google Credentials JSON')
    
    # Дополнительные настройки (JSON)
    settings = models.JSONField(default=dict, blank=True, verbose_name='Настройки')
    
    # Статистика
    last_sync_at = models.DateTimeField(null=True, blank=True, verbose_name='Последняя синхронизация')
    leads_synced = models.IntegerField(default=0, verbose_name='Синхронизировано лидов')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создано')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Обновлено')
    
    class Meta:
        verbose_name = 'CRM Интеграция'
        verbose_name_plural = 'CRM Интеграции'
        unique_together = ['user', 'crm_type']
    
    def __str__(self):
        return f"{self.user.email} - {self.get_crm_type_display()}"
    
    @property
    def is_connected(self):
        return self.status == 'connected'
    
    @property
    def is_token_expired(self):
        if not self.token_expires_at:
            return True
        return timezone.now() >= self.token_expires_at


class CRMSyncLog(models.Model):
    """Лог синхронизации с CRM"""
    ACTION_CHOICES = [
        ('create_lead', 'Создание лида'),
        ('update_lead', 'Обновление лида'),
        ('create_contact', 'Создание контакта'),
        ('create_order', 'Создание заказа'),
        ('sync_products', 'Синхронизация товаров'),
        ('append_row', 'Добавление строки'),
        ('sync_all', 'Полная синхронизация'),
    ]
    
    STATUS_CHOICES = [
        ('success', 'Успешно'),
        ('error', 'Ошибка'),
        ('pending', 'В процессе'),
    ]
    
    integration = models.ForeignKey(CRMIntegration, on_delete=models.CASCADE, related_name='sync_logs')
    action = models.CharField(max_length=50, choices=ACTION_CHOICES, verbose_name='Действие')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='Статус')
    
    request_data = models.JSONField(default=dict, blank=True, verbose_name='Данные запроса')
    response_data = models.JSONField(default=dict, blank=True, verbose_name='Ответ')
    error_message = models.TextField(blank=True, verbose_name='Сообщение об ошибке')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создано')
    
    class Meta:
        verbose_name = 'Лог синхронизации'
        verbose_name_plural = 'Логи синхронизации'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.integration} - {self.get_action_display()} - {self.created_at}"