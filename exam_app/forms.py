from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import authenticate, get_user_model # Import get_user_model
from django.core.exceptions import ValidationError # Import ValidationError directly
from .models import User, Course, Question

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

class QuestionForm(forms.ModelForm):
    correct_choice = forms.ChoiceField(
        choices=[
            ('choice1', 'Choice 1'),
            ('choice2', 'Choice 2'),
            ('choice3', 'Choice 3'),
            ('choice4', 'Choice 4'),
        ],
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'})
    )

    class Meta:
        model = Question
        fields = ['course', 'question_text', 'choice1', 'choice2', 'choice3', 'choice4', 'correct_choice']
        widgets = {
            'question_text': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'choice1': forms.TextInput(attrs={'class': 'form-control'}),
            'choice2': forms.TextInput(attrs={'class': 'form-control'}),
            'choice3': forms.TextInput(attrs={'class': 'form-control'}),
            'choice4': forms.TextInput(attrs={'class': 'form-control'}),
            'course': forms.Select(attrs={'class': 'form-select'}), # Add styling for course dropdown
        }
        labels = {
            'question_text': 'Question',
            'choice1': 'Option A',
            'choice2': 'Option B',
            'choice3': 'Option C',
            'choice4': 'Option D',
            'correct_choice': 'Correct Answer',
        }

    def __init__(self, *args, **kwargs):
        teacher_user = kwargs.pop('teacher_user', None)
        # --- IMPORTANT: THIS LINE MUST BE PRESENT AND CORRECT ---
        self.request = kwargs.pop('request', None)
        # --------------------------------------------------------
        super().__init__(*args, **kwargs)

        # Filter courses for teachers
        if teacher_user and not teacher_user.is_superuser and not teacher_user.is_staff:
            self.fields['course'].queryset = Course.objects.filter(teacher=teacher_user)
        else:
            self.fields['course'].queryset = Course.objects.all()

        # Set initial value for correct_choice radio buttons when editing
        if self.instance and self.instance.pk:
            if self.instance.correct_choice == self.instance.choice1:
                self.initial['correct_choice'] = 'choice1'
            elif self.instance.correct_choice == self.instance.choice2:
                self.initial['correct_choice'] = 'choice2'
            elif self.instance.correct_choice == self.instance.choice3:
                self.initial['correct_choice'] = 'choice3'
            elif self.instance.correct_choice == self.instance.choice4:
                self.initial['correct_choice'] = 'choice4' 
    def clean(self):
        #print("\n--- DEBUG: QuestionForm.clean() started ---")
        cleaned_data = super().clean()

        selected_choice_key = cleaned_data.get('correct_choice') # This is the key from the radio button ('choice1', etc.)
        #print(f"DEBUG: selected_choice_key from form data: '{selected_choice_key}'")

        # Check the raw values of the choices from the submitted form data
        choice_values = {
            'choice1': cleaned_data.get('choice1'),
            'choice2': cleaned_data.get('choice2'),
            'choice3': cleaned_data.get('choice3'),
            'choice4': cleaned_data.get('choice4'),
        }
        #print(f"DEBUG: Submitted choice values: {choice_values}")

        if not selected_choice_key:
            #print("DEBUG: No correct_choice key selected. Raising ValidationError.")
            raise forms.ValidationError("Please select the correct answer.")

        # This is the critical step: get the actual text value of the selected choice
        correct_answer_text = cleaned_data.get(selected_choice_key)
        #print(f"DEBUG: Text for selected correct_choice ('{selected_choice_key}'): '{correct_answer_text}'")

        if correct_answer_text is None or correct_answer_text == '': # Explicitly check for None or empty string
            #print("DEBUG: The text for the selected correct answer option is empty or None. Raising ValidationError.")
            raise forms.ValidationError("The selected correct answer option cannot be empty.")

        # Set the cleaned_data['correct_choice'] to the actual text value
        cleaned_data['correct_choice'] = correct_answer_text
        #print(f"DEBUG: cleaned_data['correct_choice'] after mapping to text: '{cleaned_data['correct_choice']}'")

        # Optional: Course authorization check within the form's clean method (requires self.request)
        if self.request and self.request.user:
            course = cleaned_data.get('course')
            if course and self.request.user.is_teacher and not self.request.user.is_superuser and course.teacher != self.request.user:
                #print("DEBUG: Teacher attempting to add/edit question for unauthorized course.")
                raise forms.ValidationError("You are not authorized to add questions to this course.")
        #else:
            #print("DEBUG: self.request or self.request.user is None in QuestionForm.clean().")

        #print("--- DEBUG: QuestionForm.clean() finished successfully ---")
        return cleaned_data

    def save(self, commit=True):
        #print("\n--- DEBUG: QuestionForm.save() started ---")
        instance = super().save(commit=False)
        #print(f"DEBUG: instance.question_text (from form): '{instance.question_text}'")
        #print(f"DEBUG: instance.correct_choice (from cleaned_data via form.save): '{instance.correct_choice}'")

        if commit:
            instance.save()
            #print("DEBUG: Instance saved to database.")
        #print("--- DEBUG: QuestionForm.save() finished ---")
        return instance

class StudentExamForm(forms.Form):
    """
    A dynamic form to display questions for an exam and capture student answers.
    """
    def __init__(self, *args, **kwargs):
        self.questions = kwargs.pop('questions', None)
        super().__init__(*args, **kwargs)

        if self.questions is not None:
            for i, question in enumerate(self.questions):
                choices = [
                    (question.choice1, question.choice1),
                    (question.choice2, question.choice2),
                    (question.choice3, question.choice3),
                    (question.choice4, question.choice4),
                ]
                # We use a field name like 'question_<id>' to link the answer back to the question
                field_name = f'question_{question.pk}'
                self.fields[field_name] = forms.ChoiceField(
                    label=f"{i+1}. {question.question_text}",
                    choices=choices,
                    widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
                    required=True # All questions must be answered
                )
        else:
            # This should ideally not happen if the view passes questions
            raise ValueError("StudentExamForm requires a 'questions' queryset.")

    def clean(self):
        cleaned_data = super().clean()
        # Basic validation: ensure all questions have been answered.
        # More sophisticated validation (e.g., ensuring a valid choice) is handled by ChoiceField itself.
        for question in self.questions:
            field_name = f'question_{question.pk}'
            if field_name not in cleaned_data:
                # This check might be redundant if ChoiceField is required=True,
                # but good for clarity in a dynamic form.
                self.add_error(field_name, "Please select an answer for this question.")
        return cleaned_data

    def get_answers(self):
        """
        Returns a list of dictionaries, each containing question_id and chosen_answer_text.
        """
        answers = []
        for question in self.questions:
            field_name = f'question_{question.pk}'
            chosen_answer = self.cleaned_data.get(field_name)
            if chosen_answer:
                answers.append({
                    'question_id': question.pk,
                    'chosen_answer': chosen_answer,
                    'correct_answer': question.correct_choice # For scoring later
                })
        return answers
