from django.db import models
from django.contrib.auth.models import AbstractUser
#from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator # Import these
from django.utils import timezone # Import timezone

# Extend Django's built-in User model
class User(AbstractUser):
    is_student = models.BooleanField(default=False)
    is_teacher = models.BooleanField(default=False)
    # Add a field for teacher approval by admin
    approved = models.BooleanField(default=False)

    # Add unique related_name arguments to avoid clashes
    groups = models.ManyToManyField(
        'auth.Group',
        related_name='exam_app_users_groups', # Unique related_name for groups
        blank=True,
        help_text='The groups this user belongs to. A user will get all permissions granted to each of their groups.',
        related_query_name='user',
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        related_name='exam_app_users_permissions', # Unique related_name for user_permissions
        blank=True,
        help_text='Specific permissions for this user.',
        related_query_name='user',
    )

#class Course(models.Model):
#    name = models.CharField(max_length=100)
#    total_questions = models.IntegerField(default=0)
#    total_marks = models.IntegerField(default=0)
#    # A teacher can create/manage courses, but an admin can also
#    teacher = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='courses_taught')
#
#    def __str__(self):
#        return self.name
class Course(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, limit_choices_to={'is_teacher': True})
    # --- NEW FIELD ---
    time_limit_minutes = models.PositiveIntegerField(
        default=60, # Default to 60 minutes (1 hour)
        validators=[MinValueValidator(5), MaxValueValidator(240)], # Min 5 mins, Max 4 hours
        help_text="Time limit for the exam in minutes (e.g., 60 for 1 hour)."
    )
    # --- END NEW FIELD ---
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        unique_together = ('name', 'teacher') # Ensure a teacher cannot have two courses with the same name
        ordering = ['name']

# Define choices for question types at the top of the file or within the model
QUESTION_TYPES = (
    ('MCQ', 'Multiple Choice Question'),
    ('TF', 'True/False'),
    ('SA', 'Short Answer'), # Added Short Answer for flexibility
    ('ESSAY', 'Essay'),      # Added Essay for flexibility
)

class Question(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    question_text = models.TextField()
    # Add the question_type field:
    question_type = models.CharField(
        max_length=10,
        choices=QUESTION_TYPES,
        default='MCQ' # Set a default type, e.g., 'MCQ'
    )
    # For MCQ and TF, we need choices and a correct choice
    # For SA/ESSAY, choice1-4 are not used, but kept for consistency if needed.
    # It's better to have separate models or make these fields nullable based on type if many types.
    # But for now, we'll assume they exist for MCQs.
    choice1 = models.CharField(max_length=255, blank=True, null=True) # Make optional
    choice2 = models.CharField(max_length=255, blank=True, null=True) # Make optional
    choice3 = models.CharField(max_length=255, blank=True, null=True) # Make optional
    choice4 = models.CharField(max_length=255, blank=True, null=True) # Make optional
    correct_choice = models.CharField(max_length=255, blank=True, null=True) # Make optional

    marks = models.IntegerField(default=1)

    def __str__(self):
        return f"Q: {self.question_text[:50]}... (Type: {self.get_question_type_display()})" # Updated __str__

class Attempt(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='exam_attempts')
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    score = models.IntegerField(default=0)
    attempt_number = models.IntegerField(default=1)
    date_attempted = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('student', 'course', 'attempt_number',) # Ensure unique attempts for a student per course

    def __str__(self):
        return f"{self.student.username} - {self.course.name} - Attempt {self.attempt_number} - Score: {self.score}"

class TeacherSalary(models.Model):
    teacher = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True, related_name='salary_info')
    salary = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Salary for {self.teacher.username}: ${self.salary}"

#class Exam(models.Model):
#    student = models.ForeignKey(User, on_delete=models.CASCADE, limit_choices_to={'is_student': True})
#    course = models.ForeignKey(Course, on_delete=models.CASCADE)
#    score = models.IntegerField(default=0)
#    total_questions = models.IntegerField(default=0) # Store actual questions count for this attempt
#    total_possible_marks = models.IntegerField(default=0) # Store max marks for this attempt
#    date_taken = models.DateTimeField(auto_now_add=True)
#    is_completed = models.BooleanField(default=False) # To track if the exam was finished
#
#    class Meta:
#        unique_together = ('student', 'course', 'date_taken') # A student can take the same course multiple times
#
#    def __str__(self):
#        return f"{self.student.username}'s exam for {self.course.name} on {self.date_taken.strftime('%Y-%m-%d %H:%M')}"

class Exam(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE, limit_choices_to={'is_student': True})
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    date_taken = models.DateTimeField(auto_now_add=True)
    # --- NEW FIELD ---
    start_time = models.DateTimeField(null=True, blank=True) # To record when student actually starts
    # --- END NEW FIELD ---
    is_completed = models.BooleanField(default=False)
    # score will be calculated and saved to Result model

    def __str__(self):
        return f"{self.student.username}'s Exam for {self.course.name}"

    class Meta:
        ordering = ['-date_taken']
        # Optional: Add unique_together if a student can only take an exam for a course once
        # unique_together = ('student', 'course')

class StudentAnswer(models.Model):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='student_answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    chosen_answer = models.CharField(max_length=255) # Stores the text of the chosen option
    is_correct = models.BooleanField(default=False)

    class Meta:
        unique_together = ('exam', 'question') # A student answers each question once per exam

    def __str__(self):
        return f"Exam {self.exam.id} | Q{self.question.id}: {self.chosen_answer} ({'Correct' if self.is_correct else 'Incorrect'})"

class Result(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE, limit_choices_to={'is_student': True})
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    exam = models.OneToOneField(Exam, on_delete=models.CASCADE, primary_key=True) # One result per exam attempt
    score = models.IntegerField()
    total_marks = models.IntegerField()
    percentage = models.FloatField()
    date_achieved = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date_achieved'] # Order results by most recent first

    def __str__(self):
        return f"{self.student.username}'s Result in {self.course.name}: {self.score}/{self.total_marks} ({self.percentage:.2f}%)"

class Salary(models.Model):
    """
    Stores salary information for teachers.
    """
    teacher = models.OneToOneField(
        'User',
        on_delete=models.CASCADE,
        limit_choices_to={'is_teacher': True, 'approved': True},
        related_name='teacher_salary' # This allows fetching salary from user object: user.salary_info
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    date_set = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'Salaries'
        ordering = ['-date_set'] # Order by most recent entry first

    def __str__(self):
        return f"{self.teacher.username}'s Salary: {self.amount}"
