from django.contrib import admin
from django.urls import path
from core import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),
    path('pricing/', views.pricing, name='pricing'),
    path('templates/', views.templates_view, name='templates'),
    path('docs/', views.docs, name='docs'),
    path('login/', views.login_view, name='login'),
]