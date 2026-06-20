import os
import re
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.conf import settings
from repository.models import Repository
from .models import Commit
from .services import GitService
from analysis.services import AIService



class CommitsView(LoginRequiredMixin, View):
    def get(self, request):
        repo_id = request.GET.get('repo')
        repos = Repository.objects.filter(user=request.user)
        
        if not repo_id and repos.exists():
            return render(request, 'commits.html', {'status': 'no_repo', 'repos': repos})
            
        if not repo_id:
            return render(request, 'commits.html', {'status': 'no_repo', 'repos': []})
            
        repo = get_object_or_404(Repository, repository_id=repo_id, user=request.user)
        repo_path = os.path.join(settings.MEDIA_ROOT, str(request.user.id), str(repo.repository_id))
        
        try:
            status = GitService.get_status(repo_path)
            staged = status['staged']
            unstaged = status['changed'] + status['untracked']
        except Exception:
            staged, unstaged = [], []
            
        context = {
            'status': 'loaded',
            'repo': repo,
            'repos': repos,
            'staged_files': staged,
            'unstaged_files': unstaged
        }
        return render(request, 'commits.html', context)

    def post(self, request):
        action = request.POST.get('action')
        repo_id = request.POST.get('repo_id')
        repo = get_object_or_404(Repository, repository_id=repo_id, user=request.user)
        repo_path = os.path.join(settings.MEDIA_ROOT, str(request.user.id), str(repo.repository_id))
        
        if action == 'generate_msg':
            diff = GitService.get_diff_summary(repo_path)
            if not diff:
                return JsonResponse({'message': 'Update: files changed.'})
            ai_msg = AIService.generate_commit_message(diff)
            return JsonResponse({'message': ai_msg})
            
        elif action == 'commit':
            message = request.POST.get('commit_message')
            if not message:
                message = "Automated commit via AiCodeRev"
                
            commit_hash = GitService.commit_all(repo_path, message)
            
            Commit.objects.create(
                repository=repo,
                commit_hash=commit_hash,
                commit_message=message
            )
            
            return redirect(f'/history/?repo={repo.repository_id}')

class HistoryView(LoginRequiredMixin, View):
    def get(self, request):
        repo_id = request.GET.get('repo')
        repos = Repository.objects.filter(user=request.user)
        
        if not repo_id:
            return render(request, 'history.html', {'status': 'no_repo', 'repos': repos})
            
        repo = get_object_or_404(Repository, repository_id=repo_id, user=request.user)
        repo_path = os.path.join(settings.MEDIA_ROOT, str(request.user.id), str(repo.repository_id))
        
        try:
            commits = GitService.get_log(repo_path)
        except Exception:
            commits = []
            
        selected_hash = request.GET.get('hash')
        diff_files = []
        if selected_hash:
            try:
                diff_files = GitService.get_commit_diff_files(repo_path, selected_hash)
                for file in diff_files:
                    file['old_lines'] = file['old_content'].splitlines() if file['old_content'] else []
                    file['new_lines'] = file['new_content'].splitlines() if file['new_content'] else []
            except Exception as e:
                print("History diff error:", e)
                diff_files = []
                
        context = {
            'status': 'loaded',
            'repo': repo,
            'repos': repos,
            'commits': commits,
            'selected_hash': selected_hash,
            'diff_files': diff_files
        }
        return render(request, 'history.html', context)
