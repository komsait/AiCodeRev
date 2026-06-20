from django.shortcuts import render, redirect
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views import View
from django.contrib import messages
from .models import AIModelConfiguration
from .forms import AIConfigForm

class AdminDashboardView(LoginRequiredMixin, UserPassesTestMixin, View):
    
    def test_func(self):
        return self.request.user.is_staff
        
    def get(self, request):
        active_config = AIModelConfiguration.objects.filter(is_active=True).first()
        form = AIConfigForm(instance=active_config)
        return render(request, 'admin_dashboard.html', {'form': form, 'active_config': active_config})
        
    def post(self, request):
        active_config = AIModelConfiguration.objects.filter(is_active=True).first()
        form = AIConfigForm(request.POST, instance=active_config)
        if form.is_valid():
            config = form.save(commit=False)
            config.is_active = True
            config.updated_by = request.user
            config.save()
            messages.success(request, f"Successfully activated {config.get_provider_name_display()} as the AI Provider.")
            return redirect('admin-dashboard')
        return render(request, 'admin_dashboard.html', {'form': form, 'active_config': active_config})
