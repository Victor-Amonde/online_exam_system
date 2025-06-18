from django.shortcuts import render, redirect, get_object_or_404 # Import get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required, user_passes_test # Import user_passes_test
from django.contrib import messages
from .forms import CustomUserCreationForm, TeacherLoginForm, CourseForm, QuestionForm
from .models import User, Course, Question

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

# Helper functions for role-based access checks
def is_teacher(user):
    return user.is_authenticated and user.is_teacher and user.approved

def is_admin(user):
    return user.is_authenticated and (user.is_superuser or user.is_staff)

@login_required
@user_passes_test(lambda u: is_teacher(u) or is_admin(u)) # Only teachers or admins can manage courses
def course_list(request):
    if is_admin(request.user):
        courses = Course.objects.all().order_by('name')
    else: # Must be a teacher
        courses = Course.objects.filter(teacher=request.user).order_by('name')
    return render(request, 'courses/course_list.html', {'courses': courses})

@login_required
@user_passes_test(lambda u: is_teacher(u) or is_admin(u))
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

@login_required
@user_passes_test(lambda u: is_teacher(u) or is_admin(u))
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

@login_required
@user_passes_test(lambda u: is_teacher(u) or is_admin(u))
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

@login_required
@user_passes_test(lambda u: is_teacher(u) or is_admin(u))
def question_list(request, course_pk):
    course = get_object_or_404(Course, pk=course_pk)

    # Authorization check: Teacher can only see questions for their own courses
    if is_teacher(request.user) and course.teacher != request.user:
        messages.error(request, "You are not authorized to view questions for this course.")
        return redirect('exam_app:course_list')

    questions = Question.objects.filter(course=course).order_by('id')
    return render(request, 'questions/question_list.html', {'course': course, 'questions': questions})

@login_required
@user_passes_test(lambda u: is_teacher(u) or is_admin(u))
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

@login_required
@user_passes_test(lambda u: is_teacher(u) or is_admin(u))
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

@login_required
@user_passes_test(lambda u: is_teacher(u) or is_admin(u))
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
