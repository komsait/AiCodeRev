from django.contrib import admin
from django.urls import path
from core.views import (
    LandingView, DashboardView,
    SettingsView
)
from authentication.views import RegisterView, LoginView, custom_logout
from repository.views import RepositoriesView, RepositoryViewPage, UploadView, delete_repository
from analysis.views import AnalysisReportView
from refactoring.views import RefactoringView
from version_control.views import CommitsView, HistoryView
from export_app.views import ExportView
from ai_config.views import AdminDashboardView

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Public Routes
    path('', LandingView.as_view(), name='landing'),
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', custom_logout, name='logout'),
    
    # Private Routes
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
    path('repositories/', RepositoriesView.as_view(), name='repositories'),
    path('repository-view/', RepositoryViewPage.as_view(), name='repository-view'),
    path('upload/', UploadView.as_view(), name='upload'),
    path('repository/delete/<uuid:repo_id>/', delete_repository, name='delete-repository'),
    path('analysis-report/', AnalysisReportView.as_view(), name='analysis-report'),
    path('refactoring/', RefactoringView.as_view(), name='refactoring'),
    path('commits/', CommitsView.as_view(), name='commits'),
    path('history/', HistoryView.as_view(), name='history'),
    path('export/', ExportView.as_view(), name='export'),
    path('settings/', SettingsView.as_view(), name='settings'),

    path('admin-dashboard/', AdminDashboardView.as_view(), name='admin-dashboard'),
]
