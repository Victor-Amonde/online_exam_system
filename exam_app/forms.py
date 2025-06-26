from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import authenticate, get_user_model # Import get_user_model
from django.core.exceptions import ValidationError # Import ValidationError directly
from .models import User, Course, Question, Exam, StudentAnswer, Result, QUESTION_TYPES

class CustomUserCreationForm(UserCreationForm):
    is_student = forms.BooleanField(label='Register as Student', required=False)
    is_teacher = forms.BooleanField(label='Register as Teacher', required=False)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = UserCreationForm.Meta.fields + ('first_name', 'last_name', 'email', 'is_student', 'is_teacher')

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

#class CourseForm(forms.ModelForm):
#    class Meta:
#        model = Course
#        # Only include fields that teachers/admins will directly input
#        fields = ['name', 'total_questions', 'total_marks']
#        labels = {
#            'name': 'Course Name',
#            'total_questions': 'Total Number of Questions',
#            'total_marks': 'Total Marks for Course',
#        }
#        widgets = {
#            'name': forms.TextInput(attrs={'class': 'form-control'}),
#            'total_questions': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
#            'total_marks': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
#        }

class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ['name', 'description', 'teacher', 'time_limit_minutes'] # <-- Ensure 'time_limit_minutes' is here
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
        }
        # Optional: Add help text or labels if desired for time_limit_minutes in the form
        labels = {
            'time_limit_minutes': 'Exam Duration (minutes)',
        }
        help_texts = {
            'time_limit_minutes': 'Set the maximum time students have to complete the exam for this course.',
        }

# Add/Update the QuestionForm below:
class QuestionForm(forms.ModelForm):
    # We define choice fields and correct_choice here as not strictly required initially
    # Their requirement will be handled in the clean method based on question_type.
    # Make them CharField to allow empty strings if not required, but keep max_length
    choice1 = forms.CharField(max_length=255, required=False, help_text="Required for MCQ questions.")
    choice2 = forms.CharField(max_length=255, required=False, help_text="Required for MCQ questions.")
    choice3 = forms.CharField(max_length=255, required=False, help_text="Required for MCQ questions.")
    choice4 = forms.CharField(max_length=255, required=False, help_text="Required for MCQ questions.")
    correct_choice = forms.CharField(max_length=255, required=False,
                                     help_text="For MCQ: Must match one of the choices. For True/False: Enter 'True' or 'False'.")

    class Meta:
        model = Question
        fields = [
            'course', 'question_text', 'question_type',
            'choice1', 'choice2', 'choice3', 'choice4',
            'correct_choice', 'marks'
        ]
        widgets = {
            'question_text': forms.Textarea(attrs={'rows': 4}),
            'question_type': forms.Select(choices=QUESTION_TYPES), # Ensure QUESTION_TYPES is available
            'course': forms.HiddenInput(), # Course will be set by the view, not chosen by teacher
        }
        labels = {
            'question_text': 'Question Text',
            'question_type': 'Question Type',
            'marks': 'Marks',
        }

    def __init__(self, *args, **kwargs):
        # The 'course' instance is often passed from the view when creating a question for a specific course
        # We don't remove it from fields, but hide it and set its initial value.
        # If the course is passed as an instance, pop it from kwargs
        self.course_instance = kwargs.pop('course_instance', None)
        super().__init__(*args, **kwargs)

        # If creating for a specific course, set initial and disable the field if it were visible
        if self.course_instance:
            self.fields['course'].initial = self.course_instance
            # self.fields['course'].widget = forms.HiddenInput() # Already set in widgets Meta class

    def clean(self):
        cleaned_data = super().clean()
        question_type = cleaned_data.get('question_type')
        choice1 = cleaned_data.get('choice1')
        choice2 = cleaned_data.get('choice2')
        choice3 = cleaned_data.get('choice3')
        choice4 = cleaned_data.get('choice4')
        correct_choice = cleaned_data.get('correct_choice')

        if question_type == 'MCQ':
            # For MCQ, at least two choices and a correct choice are required
            choices = [c for c in [choice1, choice2, choice3, choice4] if c]
            if len(choices) < 2:
                raise forms.ValidationError("MCQ questions require at least two choices.")

            if not correct_choice:
                raise forms.ValidationError({'correct_choice': "MCQ questions require a correct choice."})
            elif correct_choice not in choices:
                raise forms.ValidationError({'correct_choice': "The correct choice must be one of the provided options."})

        elif question_type == 'TF':
            # For True/False, correct_choice must be 'True' or 'False'
            if not correct_choice:
                raise forms.ValidationError({'correct_choice': "True/False questions require a correct choice (True or False)."})
            if correct_choice.lower() not in ['true', 'false']:
                raise forms.ValidationError({'correct_choice': "For True/False questions, the correct choice must be 'True' or 'False'."})

            # Ensure choice fields are empty for TF
            for choice_field_name in ['choice1', 'choice2', 'choice3', 'choice4']:
                if cleaned_data.get(choice_field_name):
                    self.add_error(choice_field_name, "Choice fields should be empty for True/False questions.")

        elif question_type in ['SA', 'Essay']:
            # For Short Answer and Essay, choice fields and correct_choice should be empty
            for choice_field_name in ['choice1', 'choice2', 'choice3', 'choice4']:
                if cleaned_data.get(choice_field_name):
                    self.add_error(choice_field_name, "Choice fields should be empty for Short Answer/Essay questions.")
            if correct_choice:
                self.add_error('correct_choice', "Correct choice field should be empty for Short Answer/Essay questions.")

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

class StudentExamForm(forms.Form): # It's a forms.Form, not forms.ModelForm
    """
    A dynamic form to display questions for an exam and capture student answers.
    """
    def __init__(self, *args, questions=None, initial_answers=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.questions = questions

        if self.initial is None:
            self.initial = {}

        if initial_answers:
            for initial_answer_data in initial_answers:
                question_id = initial_answer_data['question_id']
                field_name = f'question_{question_id}'
                self.initial[field_name] = initial_answer_data['chosen_answer']

        if self.questions:
            for i, question in enumerate(self.questions):
                field_name = f'question_{question.pk}'

                if question.question_type == 'MCQ':
                    # CRITICAL CHANGE HERE: Build choices from choice1, choice2 etc.
                    choices = []
                    if question.choice1:
                        choices.append((question.choice1, question.choice1))
                    if question.choice2:
                        choices.append((question.choice2, question.choice2))
                    if question.choice3:
                        choices.append((question.choice3, question.choice3))
                    if question.choice4:
                        choices.append((question.choice4, question.choice4))

                    self.fields[field_name] = forms.ChoiceField(
                        label=f"{i+1}. {question.question_text}", # <--- Use question.question_text
                        choices=choices,
                        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
                        required=True
                    )
                elif question.question_type == 'TF':
                    self.fields[field_name] = forms.ChoiceField(
                        label=f"{i+1}. {question.question_text}", # <--- Use question.question_text
                        choices=[('True', 'True'), ('False', 'False')],
                        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
                        required=True
                    )
                else: # For other types like Short Answer, Essay
                    self.fields[field_name] = forms.CharField(
                        label=f"{i+1}. {question.question_text}", # <--- Use question.question_text
                        widget=forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
                        required=True
                    )

                # Set initial value for the field if available
                if field_name in self.initial:
                    self.fields[field_name].initial = self.initial[field_name]

        # Removed the `else: raise ValueError(...)` block because `questions` will always be passed
        # and stored in `self.questions`. If `questions` is `None` (no questions for exam),
        # the form will simply have no fields, which is acceptable.


    def clean(self):
        cleaned_data = super().clean()
        if self.questions: # Only validate if questions were loaded
            for question in self.questions:
                field_name = f'question_{question.pk}'
                # Check if the field exists in the form and if it's required
                if field_name in self.fields and self.fields[field_name].required:
                    # Check if the field is missing from cleaned_data or is empty
                    if field_name not in cleaned_data or not cleaned_data[field_name]:
                        self.add_error(field_name, "Please provide an answer for this question.")
        return cleaned_data

    def get_answers(self):
        """
        Returns a list of dictionaries, each containing the question object and chosen_answer_text.
        """
        answers = []
        if self.questions: # Only process if questions were loaded
            for question in self.questions:
                field_name = f'question_{question.pk}'
                # Use .get(field_name) with None as default for fields that might not be present or filled
                chosen_answer = self.cleaned_data.get(field_name)
                # Only add if an answer was provided (can be empty string if blank=True is allowed for text fields)
                # Check if the field was actually in the form's fields to begin with
                if field_name in self.fields:
                    answers.append({
                        'question': question, # Pass the actual question object
                        'chosen_answer': chosen_answer if chosen_answer is not None else '', # Ensure it's never None, use empty string instead
                    })
        return answers
