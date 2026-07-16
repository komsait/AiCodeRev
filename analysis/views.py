from django.shortcuts import render, get_object_or_404
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from repository.models import Repository
from .models import AnalysisReport, CodeSmell
from .services import AIService
from django.conf import settings
import os

class AnalysisReportView(LoginRequiredMixin, View):
    """
    Handles the display and generation of Code Smell analysis reports.
    Requires the user to be logged in.
    """

    def get(self, request):
        """
        Renders the Analysis Dashboard.
        If a repository ID is provided, it fetches the most recent analysis report
        for that repository, extracts the code smells, and dynamically loads code
        snippets from the disk to display in the UI.
        
        Args:
            request: The HTTP GET request.
        """
        repo_id = request.GET.get('repo')
        
        if not repo_id:
            repos = Repository.objects.filter(user=request.user)
            return render(request, 'analysis_report.html', {'status': 'no_repo', 'repos': repos})
            
        repo = get_object_or_404(Repository, repository_id=repo_id, user=request.user)
        report = AnalysisReport.objects.filter(repository=repo).order_by('-analysis_date').first()
        
        if not report:
            return render(request, 'analysis_report.html', {'status': 'no_report', 'repo': repo})
            
        raw_smells = report.code_smells.all()
        smells = list(raw_smells)
        
        for smell in smells:
            smell.snippet = "Code snippet parsing failed or file missing."
            try:
                repo_path = os.path.join(settings.MEDIA_ROOT, str(request.user.id), str(repo.repository_id))
                file_full = os.path.join(repo_path, smell.file_path)
                if os.path.exists(file_full):
                    import re
                    with open(file_full, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                    match = re.search(r'(\d+)', str(smell.line_range))
                    if match:
                        start = max(1, int(match.group(1)) - 2)
                        end = int(match.group(1)) + 5
                        smell.snippet = "".join(lines[start-1:end]).strip()
                    else:
                        smell.snippet = "".join(lines[:10]).strip()
            except Exception:
                pass
        
        major_count = raw_smells.filter(severity_level='Major').count()
        moderate_count = raw_smells.filter(severity_level='Moderate').count()
        minor_count = raw_smells.filter(severity_level='Minor').count()
        
        context = {
            'status': 'success',
            'repo': repo,
            'report': report,
            'smells': smells,
            'major_count': major_count,
            'moderate_count': moderate_count,
            'minor_count': minor_count,
            'total_count': raw_smells.count(),
        }
        
        return render(request, 'analysis_report.html', context)
        
    def post(self, request):
        """
        Triggers a new AI analysis session for a given repository.
        This reads the code from disk, sends it to the configured AI provider,
        and saves the resulting code smells to the database.

        Args:
            request: The HTTP POST request containing 'repo_id'.
            
        Returns:
            JsonResponse indicating success or failure.
        """
        repo_id = request.POST.get('repo_id')
        if not repo_id:
            return JsonResponse({'error': 'Repo not found'}, status=400)
            
        repo = get_object_or_404(Repository, repository_id=repo_id, user=request.user)
        repo_path = os.path.join(settings.MEDIA_ROOT, str(request.user.id), str(repo.repository_id))
        
        raw_response = AIService.extract_and_send(repo_path)
        report = AIService.classify_and_store(raw_response, repo)
        
        return JsonResponse({'success': True, 'report_id': str(report.report_id)})
