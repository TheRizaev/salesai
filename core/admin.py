from django.contrib import admin
from .models import BotAgent, KnowledgeBase, Conversation, Message, Analytics

@admin.register(BotAgent)
class BotAgentAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'platform', 'status', 'total_conversations', 'created_at']
    list_filter = ['platform', 'status', 'created_at']
    search_fields = ['name', 'user__email']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(KnowledgeBase)
class KnowledgeBaseAdmin(admin.ModelAdmin):
    list_display = ['title', 'bot', 'file_type', 'created_at']
    list_filter = ['file_type', 'created_at']
    search_fields = ['title', 'bot__name']

@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ['user_name', 'bot', 'is_lead', 'started_at', 'last_message_at']
    list_filter = ['is_lead', 'started_at']
    search_fields = ['user_name', 'user_id', 'lead_email']

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['conversation', 'role', 'content_preview', 'created_at']
    list_filter = ['role', 'created_at']
    
    def content_preview(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_preview.short_description = 'Содержание'

@admin.register(Analytics)
class AnalyticsAdmin(admin.ModelAdmin):
    list_display = ['bot', 'date', 'new_conversations', 'messages_sent', 'leads_captured']
    list_filter = ['date', 'bot']
    date_hierarchy = 'date'
