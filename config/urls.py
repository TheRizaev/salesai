from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from core import views

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Allauth URLs
    path('accounts/', include('allauth.urls')),
    
    # Public pages
    path('', views.home, name='home'),
    path('pricing/', views.pricing, name='pricing'),
    path('templates/', views.templates_view, name='templates'),
    path('docs/', views.docs, name='docs'),
    
    # Dashboard
    path('dashboard/', views.dashboard, name='dashboard'),
    path('dashboard/agents/', views.agents_list, name='agents_list'),
    path('dashboard/agents/create/', views.create_agent, name='create_agent'),
    path('dashboard/agents/<int:agent_id>/', views.agent_detail, name='agent_detail'),
    path('dashboard/conversations/', views.conversations_list, name='conversations_list'),
    path('dashboard/conversations/<int:conversation_id>/', views.conversation_detail, name='conversation_detail'),
    path('dashboard/knowledge/', views.knowledge_base_view, name='knowledge_base'),
    path('dashboard/analytics/', views.analytics_view, name='analytics'),
    path('dashboard/settings/', views.settings_view, name='settings'),
    
    # API endpoints
    path('api/agents/<int:agent_id>/toggle/', views.toggle_bot_status, name='toggle_bot_status'),
    path('api/agents/<int:agent_id>/delete/', views.delete_bot, name='delete_bot'),
    path('api/agents/<int:agent_id>/upload/', views.upload_knowledge, name='upload_knowledge'),

    # Telegram Authentication
    path('dashboard/agents/<int:agent_id>/telegram-connect/', views.telegram_connect_view, name='telegram_connect'),
    
    # Telegram API endpoints
    path('api/agents/<int:agent_id>/telegram/save-credentials/', views.telegram_save_credentials, name='telegram_save_credentials'),
    path('api/agents/<int:agent_id>/telegram/send-code/', views.telegram_send_code, name='telegram_send_code'),
    path('api/agents/<int:agent_id>/telegram/verify-code/', views.telegram_verify_code, name='telegram_verify_code'),
    path('api/agents/<int:agent_id>/telegram/validate-session/', views.telegram_validate_session, name='telegram_validate_session'),
    path('api/agents/<int:agent_id>/telegram/account-info/', views.telegram_get_account_info, name='telegram_account_info'),
    path('api/agents/<int:agent_id>/telegram/disconnect/', views.telegram_disconnect, name='telegram_disconnect'),
    path('api/agents/<int:agent_id>/update-prompt/', views.update_bot_prompt, name='update_bot_prompt'),
    path('api/agents/<int:agent_id>/update/', views.update_bot, name='update_bot'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
