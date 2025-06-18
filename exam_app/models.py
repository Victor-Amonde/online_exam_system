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
    # Add the missing choice fields here:
    choice1 = models.CharField(max_length=255)
    choice2 = models.CharField(max_length=255)
    choice3 = models.CharField(max_length=255)
    choice4 = models.CharField(max_length=255)
    correct_choice = models.CharField(max_length=255) # This stores the text of the correct answer

    def __str__(self):
        return f"Q: {self.question_text[:50]}... (Course: {self.course.name})"

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

class Exam(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE, limit_choices_to={'is_student': True})
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    score = models.IntegerField(default=0)
    total_questions = models.IntegerField(default=0) # Store actual questions count for this attempt
    total_possible_marks = models.IntegerField(default=0) # Store max marks for this attempt
    date_taken = models.DateTimeField(auto_now_add=True)
    is_completed = models.BooleanField(default=False) # To track if the exam was finished

    class Meta:
        unique_together = ('student', 'course', 'date_taken') # A student can take the same course multiple times

    def __str__(self):
        return f"{self.student.username}'s exam for {self.course.name} on {self.date_taken.strftime('%Y-%m-%d %H:%M')}"

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

