from django.contrib.auth.views import LoginView
from django.shortcuts import redirect
from django.urls import reverse_lazy

class CustomLoginView(LoginView):
    """Custom login view to redirect based on user type"""
    template_name = 'registration/login.html'
    
    def get_success_url(self):
        user = self.request.user
        
        # Check if user is a guardian
        if hasattr(user, 'guardian_profile'):
            return reverse_lazy('parent:dashboard')
        
        # Check if user is staff
        elif user.is_staff or user.is_superuser or hasattr(user, 'staff'):
            return reverse_lazy('home')
        
        # Default redirect
        return reverse_lazy('home')