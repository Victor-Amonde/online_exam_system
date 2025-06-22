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
     # --- NEW URLs for Admin User Approval ---
    path('approval/users/', views.admin_user_approval_list, name='admin_user_approval_list'),
    path('approval/users/approve/<int:user_pk>/', views.admin_approve_user, name='admin_approve_user'),
    #path('approve_users_test/', views.admin_user_approval_list, name='admin_user_approval_list'),
    #path('admin/users/approval/', views.admin_user_approval_list, name='admin_user_approval_list'),
    #path('admin/users/approve/<int:user_pk>/', views.admin_approve_user, name='admin_approve_user'),

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
    # --- NEW URLs for Student Exam Flow ---

    # Student Dashboard to see available courses and results
    path('student/dashboard/', views.student_dashboard, name='student_dashboard'),

    # Start an exam for a specific course
    path('exam/<int:course_pk>/start/', views.exam_start, name='exam_start'),

    # Take an exam (display questions and submit answers)
    path('exam/<int:exam_pk>/take/', views.exam_take, name='exam_take'),

    # View detailed results of a specific exam attempt
    path('exam/<int:exam_pk>/result/', views.exam_result_detail, name='exam_result_detail'),

    # View history of all exams taken by the student
    path('student/exam_history/', views.student_exam_history, name='student_exam_history'),
    # Dashboard for teachers to see all relevant student results
    path('teacher/dashboard/', views.teacher_dashboard, name='teacher_dashboard'),
    path('teacher/results/', views.teacher_results_dashboard, name='teacher_results_dashboard'),

    # Detailed view of a specific student's exam attempt for teachers
    path('teacher/results/<int:exam_pk>/detail/', views.teacher_exam_detail_results, name='teacher_exam_detail_results'), 
]
