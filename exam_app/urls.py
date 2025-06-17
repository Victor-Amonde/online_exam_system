from django.urls import path
from . import views
from django.contrib.auth import views as auth_views # Import Django's auth views

app_name = 'exam_app'

urlpatterns = [
    path('', views.home, name='home'),
    path('register/', views.register, name='register'),
    path('dashboard/', views.dashboard, name='dashboard'),
    # Authentication URLs
    path('login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'), # Simplest, relies on settings.LOGOUT_REDIRECT_URL
]
