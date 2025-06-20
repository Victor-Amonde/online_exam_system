from django.urls import path
from . import views
from django.contrib.auth import views as auth_views
from .forms import TeacherLoginForm # Import the new form

app_name = 'exam_app'

urlpatterns = [
    path('', views.home, name='home'),
    path('register/', views.register, name='register'),
    path('dashboard/', views.dashboard, name='dashboard'),
    # Authentication URLs
    path('login/', auth_views.LoginView.as_view(template_name='login.html', authentication_form=TeacherLoginForm), name='login'), # Use the custom form
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
     # Course Management URLs
    path('courses/', views.course_list, name='course_list'),
    path('courses/add/', views.course_create, name='course_create'),
    path('courses/<int:pk>/edit/', views.course_edit, name='course_edit'),
    path('courses/<int:pk>/delete/', views.course_delete, name='course_delete'),
    # Question Management URLs (nested under courses)
    path('courses/<int:course_pk>/questions/', views.question_list, name='question_list'),
    path('courses/<int:course_pk>/questions/add/', views.question_create, name='question_create'),
    path('courses/<int:course_pk>/questions/<int:pk>/edit/', views.question_edit, name='question_edit'),
    path('courses/<int:course_pk>/questions/<int:pk>/delete/', views.question_delete, name='question_delete'),
]
