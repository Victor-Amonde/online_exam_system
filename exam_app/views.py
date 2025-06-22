from django.shortcuts import render, redirect, get_object_or_404 # Import get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test # Import user_passes_test
from django.contrib import messages
from .forms import CustomUserCreationForm, TeacherLoginForm, CourseForm, QuestionForm, StudentExamForm
from django.db import transaction # Will use this for atomic saves
from .models import User, Course, Question, Exam, StudentAnswer, Result
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.forms import AuthenticationForm # Ensure this is imported

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

# Helper functions for role-based access checks
def is_student(user):
    return user.is_authenticated and user.is_student

def is_teacher(user):
    return user.is_authenticated and user.is_teacher and user.approved

def is_admin(user):
    return user.is_authenticated and (user.is_superuser or user.is_staff)

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

def question_list(request, course_pk):
    course = get_object_or_404(Course, pk=course_pk)

    # Authorization check: Teacher can only see questions for their own courses
    if is_teacher(request.user) and course.teacher != request.user:
        messages.error(request, "You are not authorized to view questions for this course.")
        return redirect('exam_app:course_list')

    questions = Question.objects.filter(course=course).order_by('id')
    return render(request, 'questions/question_list.html', {'course': course, 'questions': questions})

def question_create(request, course_pk):
    course = get_object_or_404(Course, pk=course_pk)

    # Authorization check: Teacher can only add questions to their own courses
    if is_teacher(request.user) and course.teacher != request.user:
        messages.error(request, "You are not authorized to add questions to this course.")
        return redirect('exam_app:course_list')

    if request.method == 'POST':
        form = QuestionForm(request.POST, teacher_user=request.user, request=request) # Pass current user for form filtering
        if form.is_valid():
            question = form.save(commit=False)
            # Ensure the question is linked to the correct course and not overridden by form's course dropdown
            question.course = course
            question.save()
            messages.success(request, 'Question added successfully!')
            return redirect('exam_app:question_list', course_pk=course.pk)
        else:
            messages.error(request, 'Error adding question. Please check the form.')
    else:
        # Pre-select the course in the form for creation
        form = QuestionForm(initial={'course': course}, teacher_user=request.user, request=request)
        # Disable the course field for teachers if they can only add to their course
        if is_teacher(request.user) and course.teacher == request.user:
            form.fields['course'].widget.attrs['readonly'] = True
            form.fields['course'].widget.attrs['disabled'] = True
            # A hidden input might be needed if disabled breaks POST submission for the field
            # For now, let's rely on the view setting question.course = course
    return render(request, 'questions/question_form.html', {'form': form, 'form_title': f'Add Question to {course.name}', 'course': course})

def question_edit(request, course_pk, pk):
    course = get_object_or_404(Course, pk=course_pk)
    question = get_object_or_404(Question, pk=pk, course=course) # Ensure question belongs to this course

    # Authorization check: Teacher can only edit questions in their own courses
    if is_teacher(request.user) and course.teacher != request.user:
        messages.error(request, "You are not authorized to edit questions in this course.")
        return redirect('exam_app:course_list')

    if request.method == 'POST':
        form = QuestionForm(request.POST, instance=question, teacher_user=request.user, request=request)
        if form.is_valid():
            form.save()
            messages.success(request, 'Question updated successfully!')
            return redirect('exam_app:question_list', course_pk=course.pk)
        else:
            messages.error(request, 'Error updating question. Please check the form.')
    else:
        form = QuestionForm(instance=question, teacher_user=request.user, request=request)
        # Disable course field on edit too
        if is_teacher(request.user) and course.teacher == request.user:
            form.fields['course'].widget.attrs['readonly'] = True
            form.fields['course'].widget.attrs['disabled'] = True
    return render(request, 'questions/question_form.html', {'form': form, 'form_title': f'Edit Question for {course.name}', 'course': course})

def question_delete(request, course_pk, pk):
    course = get_object_or_404(Course, pk=course_pk)
    question = get_object_or_404(Question, pk=pk, course=course)

    # Authorization check: Teacher can only delete questions from their own courses
    if is_teacher(request.user) and course.teacher != request.user:
        messages.error(request, "You are not authorized to delete questions from this course.")
        return redirect('exam_app:course_list')

    if request.method == 'POST':
        question.delete()
        messages.success(request, 'Question deleted successfully!')
        return redirect('exam_app:question_list', course_pk=course.pk)
    return render(request, 'questions/question_confirm_delete.html', {'question': question, 'course': course})

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

    # Get all questions for the course
    questions = Question.objects.filter(course=course).order_by('?') # Randomize questions

    if not questions.exists():
        messages.warning(request, f"No questions available for '{course.name}' yet.")
        return redirect('exam_app:student_dashboard') # Or wherever appropriate

    # Create a new Exam instance
    exam = Exam.objects.create(
        student=request.user,
        course=course,
        total_questions=questions.count(),
        total_possible_marks=questions.count() # Assuming 1 mark per question for now
    )
    messages.info(request, f"Exam for '{course.name}' started.")
    return redirect('exam_app:exam_take', exam_pk=exam.pk)

def exam_take(request, exam_pk):
    exam = get_object_or_404(Exam, pk=exam_pk, student=request.user, is_completed=False)
    questions = Question.objects.filter(course=exam.course).order_by('id') # Order consistently

    if request.method == 'POST':
        form = StudentExamForm(request.POST, questions=questions)
        if form.is_valid():
            score = 0
            total_questions_answered = 0
            student_answers_to_create = []

            # Use a transaction to ensure all answers and results are saved or none are
            with transaction.atomic():
                for answer_data in form.get_answers():
                    question = get_object_or_404(Question, pk=answer_data['question_id'])
                    chosen_answer = answer_data['chosen_answer']
                    is_correct = (chosen_answer == question.correct_choice)

                    if is_correct:
                        score += 1

                    student_answers_to_create.append(
                        StudentAnswer(
                            exam=exam,
                            question=question,
                            chosen_answer=chosen_answer,
                            is_correct=is_correct
                        )
                    )
                    total_questions_answered += 1

                # Bulk create all student answers
                StudentAnswer.objects.bulk_create(student_answers_to_create)

                # Update the Exam instance
                exam.score = score
                exam.total_questions = total_questions_answered # Ensure consistency with form
                exam.total_possible_marks = total_questions_answered # Assuming 1 mark per question
                exam.is_completed = True
                exam.save()

                # Create or update the Result
                percentage = (score / total_questions_answered) * 100 if total_questions_answered > 0 else 0
                Result.objects.create(
                    student=request.user,
                    course=exam.course,
                    exam=exam, # Link to the specific exam attempt
                    score=score,
                    total_marks=total_questions_answered, # Max marks for this exam
                    percentage=percentage
                )

            messages.success(request, f"Exam completed! You scored {score} out of {total_questions_answered}.")
            return redirect('exam_app:exam_result_detail', exam_pk=exam.pk)
        else:
            messages.error(request, "Please answer all questions before submitting.")
    else:
        form = StudentExamForm(questions=questions)

    context = {
        'exam': exam,
        'form': form,
        'questions': questions, # Pass questions for display (e.g., question numbers)
        'page_title': f'Take Exam: {exam.course.name}'
    }
    return render(request, 'students/exam_take.html', context)

def exam_result_detail(request, exam_pk):
    exam = get_object_or_404(Exam, pk=exam_pk, student=request.user)
    result = get_object_or_404(Result, exam=exam) # Get the associated result
    student_answers = StudentAnswer.objects.filter(exam=exam).select_related('question').order_by('question__id')

    context = {
        'exam': exam,
        'result': result,
        'student_answers': student_answers,
        'page_title': f'Exam Result: {exam.course.name}'
    }
    return render(request, 'students/exam_result_detail.html', context)

def exam_result_detail(request, exam_pk):
    exam = get_object_or_404(Exam, pk=exam_pk, student=request.user)
    result = get_object_or_404(Result, exam=exam) # Get the associated result
    student_answers = StudentAnswer.objects.filter(exam=exam).select_related('question').order_by('question__id')

    context = {
        'exam': exam,
        'result': result,
        'student_answers': student_answers,
        'page_title': f'Exam Result: {exam.course.name}'
    }
    return render(request, 'students/exam_result_detail.html', context)

def student_exam_history(request):
    results = Result.objects.filter(student=request.user).select_related('course', 'exam').order_by('-date_achieved')
    context = {
        'results': results,
        'page_title': 'My Exam History'
    }
    return render(request, 'students/student_exam_history.html', context)
