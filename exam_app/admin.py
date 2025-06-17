from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin # Import BaseUserAdmin
from .models import User, Course, Question, Attempt, TeacherSalary

# Custom Admin for our User model
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'is_student', 'is_teacher', 'approved', 'is_staff')
    list_filter = ('is_student', 'is_teacher', 'approved', 'is_staff', 'is_superuser')
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (('Personal info'), {'fields': ('first_name', 'last_name', 'email')}),
        (('Roles and Approval'), {'fields': ('is_student', 'is_teacher', 'approved')}), # Custom fields here
        (('Permissions'), {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        (('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )
    # Add custom fields to add_fieldsets if you're creating users via admin
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        (None, {
            'classes': ('wide',),
            'fields': ('is_student', 'is_teacher', 'approved'),
        }),
    )
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering = ('username',)


# Register your models
admin.site.register(User, UserAdmin) # Register with custom admin class
admin.site.register(Course)
admin.site.register(Question)
admin.site.register(Attempt)
admin.site.register(TeacherSalary)
