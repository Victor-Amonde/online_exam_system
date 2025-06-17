from django.shortcuts import render, redirect
from django.contrib.auth import login # Import login function
from django.contrib.auth.decorators import login_required # For future use
from django.contrib import messages # For displaying messages
from .forms import CustomUserCreationForm # Import our custom form
from .models import User # Make sure User model is imported

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


@login_required # Protect the dashboard view
def dashboard(request):
    # We'll further customize this view in later steps
    # For now, it just shows generic dashboard, but only to logged-in users
    return render(request, 'dashboard.html')
