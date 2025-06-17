from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import authenticate, get_user_model # Import get_user_model
from django.core.exceptions import ValidationError # Import ValidationError directly
from .models import User, Course # Ensure your custom User model is imported

class CustomUserCreationForm(UserCreationForm):
    is_student = forms.BooleanField(label='Register as Student', required=False)
    is_teacher = forms.BooleanField(label='Register as Teacher', required=False)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = UserCreationForm.Meta.fields + ('email', 'is_student', 'is_teacher')

    def clean(self):
        cleaned_data = super().clean()
        is_student = cleaned_data.get('is_student')
        is_teacher = cleaned_data.get('is_teacher')

        if not is_student and not is_teacher:
            raise forms.ValidationError("You must select at least one role: Student or Teacher.")
        if is_student and is_teacher:
            raise forms.ValidationError("You cannot register as both a Student and a Teacher simultaneously.")
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_student = self.cleaned_data['is_student']
        user.is_teacher = self.cleaned_data['is_teacher']
        user.approved = False # Teachers need admin approval
        if commit:
            user.save()
        return user

# Refined TeacherLoginForm
class TeacherLoginForm(AuthenticationForm):
    def clean(self):
        username = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')

        if username and password:
            # First, attempt to authenticate using Django's default method
            user = authenticate(self.request, username=username, password=password)

            if user is None:
                # If authentication fails, raise the default invalid login error
                # This covers incorrect username/password for any user type
                raise forms.ValidationError(
                    self.error_messages['invalid_login'],
                    code='invalid_login',
                    params={'username': self.username_field.verbose_name},
                )

            # If authentication succeeds, but the user is an unapproved teacher
            if user.is_teacher and not user.approved:
                # Raise our specific error
                raise forms.ValidationError(
                    "Your teacher account is awaiting admin approval. Please try again later.",
                    code='teacher_not_approved',
                )

            # If authentication succeeds and no specific teacher approval issues,
            # then set user_cache for the LoginView to process
            self.user_cache = user

        return self.cleaned_data

class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        # Only include fields that teachers/admins will directly input
        fields = ['name', 'total_questions', 'total_marks']
        labels = {
            'name': 'Course Name',
            'total_questions': 'Total Number of Questions',
            'total_marks': 'Total Marks for Course',
        }
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'total_questions': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'total_marks': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
        }
