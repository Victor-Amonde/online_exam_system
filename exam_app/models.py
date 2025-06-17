from django.db import models
from django.contrib.auth.models import AbstractUser

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

class Course(models.Model):
    name = models.CharField(max_length=100)
    total_questions = models.IntegerField(default=0)
    total_marks = models.IntegerField(default=0)
    # A teacher can create/manage courses, but an admin can also
    teacher = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='courses_taught')

    def __str__(self):
        return self.name

class Question(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    question_text = models.TextField()
    option1 = models.CharField(max_length=200)
    option2 = models.CharField(max_length=200)
    option3 = models.CharField(max_length=200)
    option4 = models.CharField(max_length=200)
    correct_answer = models.CharField(max_length=200) # Store the correct option text or index
    marks = models.IntegerField(default=1) # Marks for this specific question

    def __str__(self):
        return f"{self.course.name} - {self.question_text[:50]}..." # Display first 50 chars of question

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
