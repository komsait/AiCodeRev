from django.views.generic import TemplateView
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, redirect
from repository.models import Repository
from analysis.models import AnalysisReport, CodeSmell
from version_control.models import Commit
from refactoring.models import RefactoringSuggestion


class LandingView(TemplateView):
    template_name = "landing.html"

class DashboardView(LoginRequiredMixin, View):
    def get(self, request):
        user = request.user
        repos = Repository.objects.filter(user=user)
        repo_count = repos.count()
        
        # Get smells from latest reports of each repo
        critical_smells_count = 0
        latest_reports = []
        for repo in repos:
            latest_report = repo.analysis_reports.order_by('-analysis_date').first()
            if latest_report:
                latest_reports.append(latest_report)
                critical_smells_count += latest_report.code_smells.filter(severity_level='Major').count()

        # Calculate a mock health score based on critical smells
        base_score = 100
        health_score = max(0, base_score - (critical_smells_count * 5)) if repo_count > 0 else 100

        # Build activity feed
        recent_reports = AnalysisReport.objects.filter(repository__user=user).order_by('-analysis_date')[:5]
        recent_commits = Commit.objects.filter(repository__user=user).order_by('-commit_date')[:5]
        recent_refactorings = list(RefactoringSuggestion.objects.filter(smell__report__repository__user=user, status='Accepted').order_by('-smell__report__analysis_date')[:5]) # Approx 

        activities = []
        for r in recent_reports:
            activities.append({'type': 'analysis', 'date': r.analysis_date, 'repo': r.repository.repo_name, 'message': f'Code Analysis completed (Found {r.code_smells.count()} issues)'})
        for c in recent_commits:
            activities.append({'type': 'commit', 'date': c.commit_date, 'repo': c.repository.repo_name, 'message': f'Commit generated: {c.commit_message[:30]}...'})
        for ref in recent_refactorings: # Since suggestion doesn't have an easily accessible date without touching report date
            activities.append({'type': 'refactoring', 'date': ref.smell.report.analysis_date, 'repo': ref.smell.report.repository.repo_name, 'message': f'AI Refactoring applied to {ref.smell.file_path}'})

        # Sort by date
        sorted_activities = sorted(activities, key=lambda x: x['date'], reverse=True)[:5]

        context = {
            'repo_count': repo_count,
            'critical_smells_count': critical_smells_count,
            'health_score': health_score,
            'activities': sorted_activities
        }
        return render(request, 'dashboard.html', context)

class SettingsView(LoginRequiredMixin, View):
    def get(self, request):
        return render(request, 'settings.html', {'user': request.user})

    def post(self, request):
        email = request.POST.get('email')
        if email:
            request.user.email = email
            request.user.save()
        return redirect('settings')

