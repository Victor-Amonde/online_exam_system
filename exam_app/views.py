from django.shortcuts import render, redirect, get_object_or_404 # Import get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test # Import user_passes_test
from django.contrib import messages
from .forms import CustomUserCreationForm, TeacherLoginForm, CourseForm, QuestionForm, StudentExamForm
from django.db import transaction # Will use this for atomic saves
from .models import User, Course, Question, Exam, StudentAnswer, Result, QUESTION_TYPES, Salary
from django.db.models import Prefetch # <--- ENSURE THIS IS THE LINE (from django.db.models)
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.forms import AuthenticationForm # Ensure this is imported
from django.contrib.auth import views as auth_views
from django.http import HttpResponse # Import HttpResponse for manual response if needed
from django.utils import timezone # <--- ADD THIS IMPORT
from django.forms import formset_factory # <--- ADD THIS IMPORT for formsets
import math # <--- ADD THIS IMPORT for ceil function


# Helper functions for role-based access checks
def is_student(user):
    return user.is_authenticated and user.is_student

def is_teacher(user):
    return user.is_authenticated and user.is_teacher and user.approved

def is_admin(user):
    return user.is_authenticated and (user.is_superuser or user.is_staff)


def home(request):
    return render(request, 'home.html')

def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            if user.is_student:
                # Log in student immediately after registration
                login(request, user)
                messages.success(request, 'Registration successful! You are now logged in as a Student.')
                return redirect('exam_app:dashboard')
            elif user.is_teacher:
                messages.info(request, 'Registration successful! Your teacher account is awaiting admin approval.')
                return redirect('exam_app:login') # Redirect teachers to login after registration
        else:
            messages.error(request, 'Registration failed. Please correct the errors below.')
    else:
        form = CustomUserCreationForm()
    return render(request, 'register.html', {'form': form})

def register_view(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            # --- IMPORTANT: Set user as unapproved by default ---
            if user.is_teacher: # Or for all new users, depending on your policy
                user.approved = False
                messages.info(request, "Your teacher account is awaiting approval by an administrator.")
            else: # Students might be approved automatically, or also require approval
                user.approved = True # For now, let's assume students are auto-approved unless specified
                messages.success(request, 'Student account created successfully! You can now log in.')

            user.save()

            # If you want to automatically log in the user after registration (only for auto-approved users)
            if user.approved:
                login(request, user)
                return redirect('exam_app:student_dashboard') # Or appropriate dashboard
            else:
                return redirect('exam_app:login') # Redirect to login page with message

        else:
            messages.error(request, 'Error creating account. Please correct the errors below.')
    else:
        form = CustomUserCreationForm()
    return render(request, 'registration/register.html', {'form': form, 'form_title': 'Register'})

@login_required
def dashboard(request):
    user = request.user
    if user.is_authenticated:
        if user.is_student:
            return render(request, 'dashboard_student.html')
        elif user.is_teacher:
            if user.approved: # Only approved teachers get their dashboard
                return render(request, 'dashboard_teacher.html')
            else: # Unapproved teachers
                messages.warning(request, 'Your teacher account is awaiting admin approval. You cannot access the teacher dashboard yet.')
                return redirect('exam_app:login') # Or maybe redirect to home, depending on UX choice
        elif user.is_superuser or user.is_staff: # Admins are superusers or staff users
            return render(request, 'dashboard_admin.html')
    # Fallback if somehow none of the above (shouldn't happen with @login_required)
    messages.error(request, 'Could not determine your role or access is denied.')
    return redirect('exam_app:home')

def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                # --- IMPORTANT: Check user approval status ---
                if user.approved:
                    login(request, user)
                    messages.success(request, f"Welcome back, {username}!")
                    if user.is_student:
                        return redirect('exam_app:student_dashboard')
                    elif user.is_teacher:
                        return redirect('exam_app:teacher_dashboard') # Assuming we're using the one in exam_app now
                    else: # e.g., admin/superuser not explicitly student or teacher
                        return redirect('admin:index') # Or a generic dashboard
                else:
                    messages.warning(request, "Your account is awaiting approval by an administrator.")
                    return redirect('exam_app:login') # Redirect back to login with message
            else:
                messages.error(request, "Invalid username or password.")
        else:
            messages.error(request, "Invalid username or password.")
    else:
        form = AuthenticationForm()
    return render(request, 'registration/login.html', {'form': form, 'form_title': 'Login'})

# --- NEW ADMIN APPROVAL VIEWS ---

@login_required
@user_passes_test(is_admin) # Only staff/superusers can access this
def admin_user_approval_list(request):
    # Fetch users who are not approved and are either teachers or students
    # (Exclude superusers/staff as they are implicitly approved and manage others)
    unapproved_users = User.objects.filter(approved=False).exclude(is_superuser=True).exclude(is_staff=True).order_by('date_joined')

    context = {
        'unapproved_users': unapproved_users,
        'page_title': 'Approve User Accounts'
    }
    return render(request, 'admin_features/user_approval_list.html', context)

def admin_approve_user(request, user_pk):
    user_to_approve = get_object_or_404(User, pk=user_pk)

    # Prevent approving/disapproving self or other admins unless explicitly allowed
    if user_to_approve == request.user:
        messages.error(request, "You cannot approve/disapprove your own account.")
        return redirect('exam_app:admin_user_approval_list')
    if user_to_approve.is_superuser or user_to_approve.is_staff:
        messages.error(request, "Cannot approve/disapprove an administrator account through this interface.")
        return redirect('exam_app:admin_user_approval_list')

    # This view will handle both approve and disapprove actions based on a POST parameter
    if request.method == 'POST':
        action = request.POST.get('action') # 'approve' or 'disapprove'

        if action == 'approve':
            user_to_approve.approved = True
            user_to_approve.save()
            messages.success(request, f"User '{user_to_approve.username}' has been approved.")
        elif action == 'disapprove':
            user_to_approve.approved = False # Set back to false, or keep as is
            user_to_approve.save() # Save the change
            messages.warning(request, f"User '{user_to_approve.username}' has been disapproved (account remains unapproved).")
        else:
            messages.error(request, "Invalid action.")

        return redirect('exam_app:admin_user_approval_list')

    # If it's a GET request, just redirect back or show a message, as this is a POST-only action
    messages.error(request, "Invalid request method for user approval.")
    return redirect('exam_app:admin_user_approval_list')

@login_required
@user_passes_test(lambda u: is_teacher(u) or is_admin(u)) # Only teachers or admins can manage courses
def course_list(request):
    if is_admin(request.user):
        courses = Course.objects.all().order_by('name')
    else: # Must be a teacher
        courses = Course.objects.filter(teacher=request.user).order_by('name')
    return render(request, 'courses/course_list.html', {'courses': courses})

def course_create(request):
    if request.method == 'POST':
        form = CourseForm(request.POST)
        if form.is_valid():
            course = form.save(commit=False)
            if is_teacher(request.user):
                course.teacher = request.user # Assign the current teacher to the course
            # Admin can also assign teachers to courses later if needed, but for now,
            # if an admin creates it, the teacher field might be null or set via admin panel
            course.save()
            messages.success(request, 'Course created successfully!')
            return redirect('exam_app:course_list')
        else:
            messages.error(request, 'Error creating course. Please check the form.')
    else:
        form = CourseForm()
    return render(request, 'courses/course_form.html', {'form': form, 'form_title': 'Add New Course'})

def course_edit(request, pk):
    course = get_object_or_404(Course, pk=pk)

    # Authorization check: Teacher can only edit their own courses
    if is_teacher(request.user) and course.teacher != request.user:
        messages.error(request, "You are not authorized to edit this course.")
        return redirect('exam_app:course_list')

    if request.method == 'POST':
        form = CourseForm(request.POST, instance=course)
        if form.is_valid():
            form.save()
            messages.success(request, 'Course updated successfully!')
            return redirect('exam_app:course_list')
        else:
            messages.error(request, 'Error updating course. Please check the form.')
    else:
        form = CourseForm(instance=course)
    return render(request, 'courses/course_form.html', {'form': form, 'form_title': f'Edit Course: {course.name}'})

def course_delete(request, pk):
    course = get_object_or_404(Course, pk=pk)

    # Authorization check: Teacher can only delete their own courses
    if is_teacher(request.user) and course.teacher != request.user:
        messages.error(request, "You are not authorized to delete this course.")
        return redirect('exam_app:course_list')

    if request.method == 'POST':
        course.delete()
        messages.success(request, 'Course deleted successfully!')
        return redirect('exam_app:course_list')
    return render(request, 'courses/course_confirm_delete.html', {'course': course})

#def question_list(request, course_pk):
#    course = get_object_or_404(Course, pk=course_pk)
#
#    # Authorization check: Teacher can only see questions for their own courses
#    if is_teacher(request.user) and course.teacher != request.user:
#        messages.error(request, "You are not authorized to view questions for this course.")
#        return redirect('exam_app:course_list')
#
#    questions = Question.objects.filter(course=course).order_by('id')
#    return render(request, 'questions/question_list.html', {'course': course, 'questions': questions})
#
#def question_create(request, course_pk):
#    course = get_object_or_404(Course, pk=course_pk)
#
#    # Authorization check: Teacher can only add questions to their own courses
#    if is_teacher(request.user) and course.teacher != request.user:
#        messages.error(request, "You are not authorized to add questions to this course.")
#        return redirect('exam_app:course_list')
#
#    if request.method == 'POST':
#        form = QuestionForm(request.POST, teacher_user=request.user, request=request) # Pass current user for form filtering
#        if form.is_valid():
#            question = form.save(commit=False)
#            # Ensure the question is linked to the correct course and not overridden by form's course dropdown
#            question.course = course
#            question.save()
#            messages.success(request, 'Question added successfully!')
#            return redirect('exam_app:question_list', course_pk=course.pk)
#        else:
#            messages.error(request, 'Error adding question. Please check the form.')
#    else:
#        # Pre-select the course in the form for creation
#        form = QuestionForm(initial={'course': course}, teacher_user=request.user, request=request)
#        # Disable the course field for teachers if they can only add to their course
#        if is_teacher(request.user) and course.teacher == request.user:
#            form.fields['course'].widget.attrs['readonly'] = True
#            form.fields['course'].widget.attrs['disabled'] = True
#            # A hidden input might be needed if disabled breaks POST submission for the field
#            # For now, let's rely on the view setting question.course = course
#    return render(request, 'questions/question_form.html', {'form': form, 'form_title': f'Add Question to {course.name}', 'course': course})
#
#def question_edit(request, course_pk, pk):
#    course = get_object_or_404(Course, pk=course_pk)
#    question = get_object_or_404(Question, pk=pk, course=course) # Ensure question belongs to this course
#
#    # Authorization check: Teacher can only edit questions in their own courses
#    if is_teacher(request.user) and course.teacher != request.user:
#        messages.error(request, "You are not authorized to edit questions in this course.")
#        return redirect('exam_app:course_list')
#
#    if request.method == 'POST':
#        form = QuestionForm(request.POST, instance=question, teacher_user=request.user, request=request)
#        if form.is_valid():
#            form.save()
#            messages.success(request, 'Question updated successfully!')
#            return redirect('exam_app:question_list', course_pk=course.pk)
#        else:
#            messages.error(request, 'Error updating question. Please check the form.')
#    else:
#        form = QuestionForm(instance=question, teacher_user=request.user, request=request)
#        # Disable course field on edit too
#        if is_teacher(request.user) and course.teacher == request.user:
#            form.fields['course'].widget.attrs['readonly'] = True
#            form.fields['course'].widget.attrs['disabled'] = True
#    return render(request, 'questions/question_form.html', {'form': form, 'form_title': f'Edit Question for {course.name}', 'course': course})
#
#def question_delete(request, course_pk, pk):
#    course = get_object_or_404(Course, pk=course_pk)
#    question = get_object_or_404(Question, pk=pk, course=course)
#
#    # Authorization check: Teacher can only delete questions from their own courses
#    if is_teacher(request.user) and course.teacher != request.user:
#        messages.error(request, "You are not authorized to delete questions from this course.")
#        return redirect('exam_app:course_list')
#
#    if request.method == 'POST':
#        question.delete()
#        messages.success(request, 'Question deleted successfully!')
#        return redirect('exam_app:question_list', course_pk=course.pk)
#    return render(request, 'questions/question_confirm_delete.html', {'question': question, 'course': course})

# --- NEW TEACHER RESULT MANAGEMENT VIEWS ---
def teacher_dashboard(request):
    # You can add context here later, e.g., count of courses, recent activities
    courses = Course.objects.filter(teacher=request.user).count()
    recent_results = Result.objects.filter(course__teacher=request.user).order_by('-date_achieved')[:5]

    context = {
        'page_title': 'Teacher Dashboard',
        'courses_count': courses,
        'recent_results': recent_results,
    }
    return render(request, 'teachers/teacher_dashboard.html', context) # Render the new template

def teacher_results_dashboard(request):
    # Filter results based on courses taught by the current teacher
    if request.user.is_superuser or request.user.is_staff: # Admin/Staff can see all results
        results = Result.objects.all().select_related('student', 'course', 'exam').order_by('course__name', 'student__username', '-date_achieved')
        page_title = 'All Exam Results (Admin View)'
    else: # Regular Teacher sees only their courses
        teacher_courses = Course.objects.filter(teacher=request.user)
        results = Result.objects.filter(course__in=teacher_courses).select_related('student', 'course', 'exam').order_by('course__name', 'student__username', '-date_achieved')
        page_title = 'My Course Exam Results'

    context = {
        'results': results,
        'page_title': page_title
    }
    return render(request, 'teachers/teacher_results_dashboard.html', context)

def teacher_exam_detail_results(request, exam_pk):
    # Get the exam instance
    exam = get_object_or_404(Exam, pk=exam_pk)
    result = get_object_or_404(Result, exam=exam)
    student_answers = StudentAnswer.objects.filter(exam=exam).select_related('question').order_by('question__id')

    # Authorization check: Teacher can only view results for their own courses (unless admin)
    if not (request.user.is_superuser or request.user.is_staff):
        if exam.course.teacher != request.user:
            messages.error(request, "You are not authorized to view this exam result.")
            return redirect('exam_app:teacher_results_dashboard') # Redirect back to their results page

    context = {
        'exam': exam,
        'result': result,
        'student_answers': student_answers,
        'page_title': f"Result for {exam.student.username} in {exam.course.name}"
    }
    return render(request, 'teachers/teacher_exam_detail_results.html', context)

@login_required
@user_passes_test(is_student)
def student_dashboard(request):
    available_courses = Course.objects.all().order_by('name')
    # Get latest result for each course for the current student
    student_results = Result.objects.filter(student=request.user).select_related('course').order_by('course__name', '-date_achieved')

    # Create a dictionary to hold the latest result for each course
    latest_results = {}
    for result in student_results:
        if result.course.id not in latest_results:
            latest_results[result.course.id] = result

    context = {
        'available_courses': available_courses,
        'latest_results': latest_results, # Pass the dictionary of latest results
        'page_title': 'Student Dashboard'
    }
    return render(request, 'students/student_dashboard.html', context)

def exam_start(request, course_pk):
    course = get_object_or_404(Course, pk=course_pk)
    questions = Question.objects.filter(course=course)

    if not questions.exists():
        messages.warning(request, "This course currently has no questions. You cannot start an exam.")
        return redirect('exam_app:student_dashboard')

    # Check if student already has a pending or completed exam for this course
    existing_exam = Exam.objects.filter(student=request.user, course=course).first()
    if existing_exam:
        # If student has a previous attempt, offer to retake or view results
        # For simplicity, let's just create a new one for now if they haven't completed it
        # Or you might want to redirect them to their existing incomplete exam
        if not existing_exam.is_completed:
            messages.info(request, "You have an uncompleted attempt for this exam. Resuming...")
            # Redirect to resume existing exam rather than starting a new one
            return redirect('exam_app:exam_take', exam_pk=existing_exam.pk)
        else:
            messages.info(request, "You have already completed an exam for this course. You can view your results or start a new attempt.")
            # You might want to provide an option to start a new attempt here too,
            # or prevent multiple attempts if that's your policy.
            # For now, let's allow a new attempt by just creating one below.

    # Create a new Exam instance
    exam = Exam.objects.create(
        student=request.user,
        course=course,
        start_time=timezone.now() # <--- SET THE START TIME HERE
    )

    messages.success(request, f"Exam for {course.name} has started. Good luck!")
    return redirect('exam_app:exam_take', exam_pk=exam.pk)

# Define the StudentAnswerFormSet outside the view, or dynamically
StudentAnswerFormSet = formset_factory(StudentExamForm, extra=0) # extra=0 means no empty forms by default

@login_required
@user_passes_test(is_student)
def exam_take(request, exam_pk):
    exam = get_object_or_404(Exam, pk=exam_pk, student=request.user)

    # Prevent taking completed exams
    if exam.is_completed:
        messages.info(request, "This exam has already been completed.")
        return redirect('exam_app:exam_result_detail', exam_pk=exam.pk)

    exam_questions = Question.objects.filter(course=exam.course).order_by('id')

    if not exam_questions.exists():
        messages.warning(request, "This course currently has no questions. You cannot take an exam.")
        exam.is_completed = True # Mark exam as completed if no questions
        exam.save()
        return redirect('exam_app:student_dashboard')

    # Prepare initial data for pre-populating the form (from existing answers)
    initial_answers_data = []
    for question in exam_questions:
        student_answer = StudentAnswer.objects.filter(exam=exam, question=question).first()
        if student_answer:
            initial_answers_data.append({
                'question_id': question.pk,
                'chosen_answer': student_answer.chosen_answer,
            })

    # Initialize 'form' here, outside of the if/else for request.method
    # This ensures 'form' is always defined before rendering the template.
    form = StudentExamForm(questions=exam_questions, initial_answers=initial_answers_data) # <--- Initialized for GET/default

    if request.method == 'POST':
        form = StudentExamForm(request.POST, questions=exam_questions, initial_answers=initial_answers_data)
        if form.is_valid():
            with transaction.atomic():
                elapsed_time_seconds = (timezone.now() - exam.start_time).total_seconds()
                time_limit_seconds = exam.course.time_limit_minutes * 60

                if elapsed_time_seconds > time_limit_seconds:
                    messages.warning(request, "Time's up! Your exam has been automatically submitted.")
                    exam.is_completed = True
                    exam.save()
                    calculate_exam_score(request, exam) # <--- PASS 'request' HERE
                    return redirect('exam_app:exam_result_detail', exam_pk=exam.pk)

                # ... (save answers logic) ...

                exam.is_completed = True
                exam.save()
                calculate_exam_score(request, exam) # <--- PASS 'request' HERE

                messages.success(request, "Exam submitted successfully!")
                return redirect('exam_app:exam_result_detail', exam_pk=exam.pk)
        else:
            messages.error(request, "Please correct the errors below.")
            print(form.errors)    
    context = {
        'exam': exam,
        'form': form, # This 'form' will always be defined now
    }
    return render(request, 'students/exam_take.html', context)

def calculate_exam_score(request, exam): # <--- ADD 'request' here
    total_score = 0
    total_possible_score = 0

    student_answers = StudentAnswer.objects.filter(exam=exam)

    for student_answer in student_answers:
        question = student_answer.question
        total_possible_score += question.marks

        correct_answer = question.correct_choice.strip().lower() if question.correct_choice else ''
        submitted_answer = student_answer.chosen_answer.strip().lower() if student_answer.chosen_answer else ''

        if question.question_type in ['MCQ', 'TF']:
            if submitted_answer == correct_answer:
                total_score += question.marks

    percentage = (total_score / total_possible_score * 100) if total_possible_score > 0 else 0

    result, created = Result.objects.get_or_create(
        exam=exam,
        defaults={
            'student': exam.student,
            'course': exam.course,
            'score': total_score,
            'total_marks': total_possible_score,
            'percentage': percentage,
        }
    )
    if not created:
        result.score = total_score
        result.total_marks = total_possible_score
        result.percentage = percentage
        result.save()

    # Pass the 'request' object to messages.info()
    messages.info(request, f"Your exam for {exam.course.name} has been graded. Score: {total_score}/{total_possible_score} ({percentage:.2f}%)") # <--- Use 'request' here
    return result

def exam_result_detail(request, exam_pk):
    # Get the exam instance
    exam = get_object_or_404(Exam, pk=exam_pk, student=request.user)

    # Get the result associated with this exam (using OneToOneField primary_key)
    # Result will be available if calculate_exam_score was successful
    result = get_object_or_404(Result, exam=exam)

    # Get all questions for the course associated with this exam
    # Order by ID to ensure consistent display
    exam_questions = Question.objects.filter(course=exam.course).order_by('id')

    # Get all student answers for this specific exam
    # Use Prefetch to optimize fetching related questions if you iterate a lot
    student_answers = StudentAnswer.objects.filter(exam=exam).select_related('question')

    # Create a dictionary for quick lookup of student answers by question ID
    student_answers_dict = {sa.question_id: sa for sa in student_answers}

    # Prepare a list of structured data for the template
    # Each item in this list will represent a question with its details and result
    question_results = []
    for question in exam_questions:
        student_answer_obj = student_answers_dict.get(question.pk)
        chosen_answer = student_answer_obj.chosen_answer if student_answer_obj else "Not Answered"
        is_correct = False
        marks_awarded = 0

        # Determine correctness based on question type
        if question.question_type in ['MCQ', 'TF']:
            if chosen_answer.strip().lower() == (question.correct_choice.strip().lower() if question.correct_choice else ''):
                is_correct = True
                marks_awarded = question.marks
        # For 'SA' or 'Essay', manual review is typically needed,
        # so `is_correct` here defaults to False unless explicitly marked otherwise in `StudentAnswer` later.
        # For now, it's false, and marks_awarded is 0 for those types.

        question_results.append({
            'question_number': question.pk, # Using PK for unique ID, or forloop.counter in template
            'question_text': question.question_text,
            'question_type': question.get_question_type_display(),
            'choice1': question.choice1,
            'choice2': question.choice2,
            'choice3': question.choice3,
            'choice4': question.choice4,
            'student_answer': chosen_answer,
            'correct_answer': question.correct_choice, # Will be None for SA/Essay but useful for MCQ/TF
            'is_correct': is_correct,
            'marks_awarded': marks_awarded,
            'total_question_marks': question.marks,
        })

    context = {
        'exam': exam,
        'result': result,
        'question_results': question_results, # New data to pass
    }
    return render(request, 'students/exam_result_detail.html', context)

def student_exam_history(request):
    results = Result.objects.filter(student=request.user).select_related('course', 'exam').order_by('-date_achieved')
    context = {
        'results': results,
        'page_title': 'My Exam History'
    }
    return render(request, 'students/student_exam_history.html', context)
@login_required
@user_passes_test(is_student)
def student_exam_list(request):
    """
    Lists all courses that a student can take as an exam.
    """
    # For simplicity, we list all active courses. You could filter by enrolled courses if you have an enrollment model.
    available_exams = Course.objects.filter(is_active=True).order_by('name')

    context = {
        'courses': available_exams
    }
    return render(request, 'students/exam_list.html', context) # Renders the list of exams
@login_required
@user_passes_test(is_student)
def student_exam_result_list(request):
    """
    Lists all the results of exams the student has taken.
    """
    # Fetch all results for the logged-in user
    # We use select_related to efficiently fetch the related Exam and Course data in one query
    student_results = Result.objects.filter(student=request.user).select_related('exam__course').order_by('-date_achieved')

    context = {
        'results': student_results
    }
    # Note the template path uses the 'students' plural directory
    return render(request, 'students/exam_result_list.html', context)

# --- Teacher Question Management Views ---

@login_required
@user_passes_test(is_teacher)
def teacher_question_list(request, course_pk):
    course = get_object_or_404(Course, pk=course_pk, teacher=request.user)
    questions = Question.objects.filter(course=course).order_by('id')
    context = {
        'course': course,
        'questions': questions
    }
    return render(request, 'teachers/question_list.html', context)


@login_required
@user_passes_test(is_teacher)
def teacher_question_create(request, course_pk):
    course = get_object_or_404(Course, pk=course_pk, teacher=request.user)

    if request.method == 'POST':
        # Pass the course_instance to the form's __init__
        form = QuestionForm(request.POST, course_instance=course)
        if form.is_valid():
            question = form.save(commit=False)
            question.course = course # Ensure the question is linked to the correct course
            question.save()
            messages.success(request, 'Question added successfully!')
            return redirect('exam_app:teacher_question_list', course_pk=course.pk)
        else:
            messages.error(request, 'Error adding question. Please correct the errors.')
    else:
        # Pass the course_instance to the form for initial setup
        form = QuestionForm(course_instance=course)

    context = {
        'form': form,
        'course': course,
        'form_title': 'Add New Question'
    }
    return render(request, 'teachers/question_form.html', context)


@login_required
@user_passes_test(is_teacher)
def teacher_question_update(request, pk):
    question = get_object_or_404(Question, pk=pk)
    course = question.course # Get the course related to this question

    # Ensure the logged-in teacher owns this course
    if course.teacher != request.user:
        messages.error(request, "You do not have permission to edit this question.")
        return redirect('exam_app:teacher_dashboard') # Or appropriate redirect

    if request.method == 'POST':
        # Pass the course_instance for consistency, though it won't change for update
        form = QuestionForm(request.POST, instance=question, course_instance=course)
        if form.is_valid():
            form.save()
            messages.success(request, 'Question updated successfully!')
            return redirect('exam_app:teacher_question_list', course_pk=course.pk)
        else:
            messages.error(request, 'Error updating question. Please correct the errors.')
    else:
        form = QuestionForm(instance=question, course_instance=course)

    context = {
        'form': form,
        'course': course,
        'question': question,
        'form_title': 'Update Question'
    }
    return render(request, 'teachers/question_form.html', context)


@login_required
@user_passes_test(is_teacher)
def teacher_question_delete(request, pk):
    question = get_object_or_404(Question, pk=pk)
    course = question.course

    # Ensure the logged-in teacher owns this course
    if course.teacher != request.user:
        messages.error(request, "You do not have permission to delete this question.")
        return redirect('exam_app:teacher_dashboard') # Or appropriate redirect

    if request.method == 'POST':
        question.delete()
        messages.success(request, 'Question deleted successfully!')
        return redirect('exam_app:teacher_question_list', course_pk=course.pk)

    context = {
        'question': question,
        'course': course
    }
    return render(request, 'teachers/question_confirm_delete.html', context)


# --- Teacher Course Management List (if not already existing) ---
@login_required
@user_passes_test(is_teacher)
def teacher_course_list(request):
    courses = Course.objects.filter(teacher=request.user).order_by('name')
    context = {
        'courses': courses
    }
    return render(request, 'teachers/course_list.html', context) # You will create this template next

@login_required
@user_passes_test(is_teacher)
def teacher_student_list(request):
    # Get all courses taught by the logged-in teacher
    teachers_courses = Course.objects.filter(teacher=request.user)

    # Get all exams taken for these courses
    # Use values_list('student', flat=True) to get a list of student IDs
    # Use distinct() to get only unique student IDs
    student_ids_from_exams = Exam.objects.filter(course__in=teachers_courses).values_list('student', flat=True).distinct()

    # Fetch the actual User objects for these unique student IDs
    # Filter for users who are students (assuming your User model has is_student flag)
    # Order them for consistent display
    students = User.objects.filter(pk__in=student_ids_from_exams, is_student=True).order_by('first_name', 'last_name')

    context = {
        'students': students,
        'courses': teachers_courses # Optionally pass courses if you want to show which courses they teach
    }
    return render(request, 'teachers/student_list.html', context) # Will render a new template

@login_required
@user_passes_test(is_teacher)
def teacher_salary_view(request):
    try:
        # Get the salary information for the logged-in teacher
        # Use the related_name we defined: teacher_salary
        salary = Salary.objects.get(teacher=request.user)
    except Salary.DoesNotExist:
        # If no salary is set for this teacher, create a message
        messages.info(request, "No salary information has been set for you yet.")
        salary = None # Set salary to None so the template can handle it

    context = {
        'salary': salary,
    }
    return render(request, 'teachers/teacher_salary.html', context) # Will render a new template
