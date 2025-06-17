from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User

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
