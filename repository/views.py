import os
import shutil
import git
import zipfile
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from .models import Repository

class RepositoriesView(LoginRequiredMixin, View):
    """
    Manages the creation and listing of repositories.
    """
    
    def get(self, request):
        """
        Renders the list of repositories owned by the logged-in user.
        """
        repos = Repository.objects.filter(user=request.user)
        return render(request, 'repositories.html', {'repos': repos})

    def post(self, request):
        repo_name = request.POST.get('repo_name')
        upload_now = request.POST.get('upload_after') == 'on'

        if not repo_name:
            return JsonResponse({'error': 'Repository name is required'}, status=400)

        if Repository.objects.filter(user=request.user, repo_name=repo_name).exists():
            return JsonResponse({'error': 'Repository name already exists'}, status=400)

        repo = Repository.objects.create(
            user=request.user,
            repo_name=repo_name,
            upload_type='init'
        )

        repo_path = os.path.join(settings.MEDIA_ROOT, str(request.user.id), str(repo.repository_id))
        
        try:
            os.makedirs(repo_path, exist_ok=True)
            git.Repo.init(repo_path)
        except Exception as e:
            shutil.rmtree(repo_path, ignore_errors=True)
            repo.delete()
            return JsonResponse({'error': f'Failed to initialize git repository: {str(e)}'}, status=500)

        return JsonResponse({'success': True, 'redirect': '/upload/' if upload_now else '/repositories/'})

class RepositoryViewPage(LoginRequiredMixin, View):
    """
    Handles viewing the contents of a specific repository.
    Provides a file tree and allows viewing the raw content of individual files.
    """
    
    def get(self, request):
        """
        If 'file_path' is provided in the query string, returns the raw text content of that file.
        Otherwise, builds and returns a JSON-friendly nested tree structure of the repository directory.
        """
        repo_id = request.GET.get('id')
        file_path = request.GET.get('file_path')
        
        if not repo_id:
            return render(request, 'repository_view.html', {'repo': None, 'file_tree': []})
            
        repo = get_object_or_404(Repository, repository_id=repo_id, user=request.user)
        repo_path = os.path.join(settings.MEDIA_ROOT, str(request.user.id), str(repo.repository_id))
        
        if file_path:
            try:
                full_path = os.path.join(repo_path, file_path)
                # Security check to prevent path traversal
                if not os.path.normpath(full_path).startswith(os.path.normpath(repo_path)):
                    return JsonResponse({'error': 'Invalid path'}, status=400)
                    
                if os.path.exists(full_path) and os.path.isfile(full_path):
                    with open(full_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    return JsonResponse({'content': content})
                else:
                    return JsonResponse({'error': 'File not found'}, status=404)
            except Exception as e:
                return JsonResponse({'error': str(e)}, status=500)
                
        file_tree = []
        if os.path.exists(repo_path):
            def build_tree(dir_path, rel_dir=""):
                tree = []
                try:
                    items = sorted(os.listdir(dir_path))
                    dirs = [i for i in items if os.path.isdir(os.path.join(dir_path, i)) and i != '.git']
                    files = [i for i in items if os.path.isfile(os.path.join(dir_path, i))]
                    
                    for d in dirs:
                        tree.append({
                            'name': d,
                            'type': 'directory',
                            'path': os.path.join(rel_dir, d).replace('\\', '/'),
                            'children': build_tree(os.path.join(dir_path, d), os.path.join(rel_dir, d))
                        })
                    for f in files:
                        tree.append({
                            'name': f,
                            'type': 'file',
                            'path': os.path.join(rel_dir, f).replace('\\', '/')
                        })
                except Exception:
                    pass
                return tree
            
            file_tree = build_tree(repo_path)
            
        from analysis.models import AnalysisReport
        has_analysis = AnalysisReport.objects.filter(repository=repo).exists()
            
        return render(request, 'repository_view.html', {'repo': repo, 'file_tree': file_tree, 'has_analysis': has_analysis})

def get_dir_size(path):
    total = 0
    if not os.path.exists(path):
        return total
    for root, dirs, files in os.walk(path):
        for f in files:
            fp = os.path.join(root, f)
            if not os.path.islink(fp):
                total += os.path.getsize(fp)
    return total

class UploadView(LoginRequiredMixin, View):
    """
    Handles uploading local files or ZIP archives into a repository.
    """
    
    def get(self, request):
        """
        Renders the file upload interface.
        """
        repos = Repository.objects.filter(user=request.user)
        selected_repo_id = request.GET.get('repo')
        return render(request, 'upload.html', {'repos': repos, 'selected_repo_id': selected_repo_id})

    def post(self, request):
        repo_id = request.POST.get('repo_id')
        if not repo_id:
            return JsonResponse({'error': 'No repository selected.'}, status=400)
            
        repo = get_object_or_404(Repository, repository_id=repo_id, user=request.user)
        repo_path = os.path.join(settings.MEDIA_ROOT, str(request.user.id), str(repo.repository_id))
        
        files = request.FILES.getlist('files')
        if not files:
            return JsonResponse({'error': 'No files uploaded.'}, status=400)
            
        tree_preview = []
        warnings = []
        supported_exts = ['.py', '.java', '.js', '.php', '.rb', '.go', '.c', '.cs']
        max_size = 1 * 1024 * 1024 * 1024 # 1GB
        
        current_size = get_dir_size(repo_path)
        
        try:
            for f in files:
                safe_name = os.path.basename(f.name)
                ext = os.path.splitext(safe_name)[1].lower()
                
                if ext not in supported_exts and not safe_name.endswith('.zip'):
                    warnings.append(f"Skipped unsupported file type: {safe_name}")
                    continue
                    
                if current_size + f.size > max_size:
                    return JsonResponse({'error': f'Upload failed: Repository size limit of 1GB exceeded with file {safe_name}.'}, status=400)
                    
                dest_path = os.path.join(repo_path, safe_name)
                
                with open(dest_path, 'wb+') as destination:
                    for chunk in f.chunks():
                        destination.write(chunk)
                current_size += f.size
                
                if safe_name.endswith('.zip'):
                    with zipfile.ZipFile(dest_path, 'r') as zip_ref:
                        # Pre-compute total extraction size
                        total_uncompressed = 0
                        for zinfo in zip_ref.infolist():
                            z_ext = os.path.splitext(zinfo.filename)[1].lower()
                            if zinfo.is_dir() or z_ext in supported_exts:
                                total_uncompressed += zinfo.file_size
                        
                        if current_size + total_uncompressed > max_size:
                            os.remove(dest_path)  # cleanup the zip file
                            return JsonResponse({'error': 'Upload failed: Repository size limit of 1GB exceeded extracting zip.'}, status=400)
                            
                        # Safe to extract
                        for zinfo in zip_ref.infolist():
                            z_ext = os.path.splitext(zinfo.filename)[1].lower()
                            if zinfo.is_dir() or z_ext in supported_exts:
                                zip_ref.extract(zinfo, repo_path)
                                if not zinfo.is_dir():
                                    tree_preview.append(zinfo.filename)
                                    current_size += zinfo.file_size
                            else:
                                warnings.append(f"Skipped unsupported file in zip: {zinfo.filename}")
                    os.remove(dest_path) # remove zip
                    current_size -= f.size
                else:
                    tree_preview.append(safe_name)
            
            if not tree_preview:
                return JsonResponse({'error': 'No supported files were uploaded.'}, status=400)
                
            try:
                repo_git = git.Repo(repo_path)
                repo_git.git.add(A=True) 
            except git.exc.InvalidGitRepositoryError as e:
                for item in tree_preview:
                    fpath = os.path.join(repo_path, item)
                    if os.path.exists(fpath):
                        os.remove(fpath)
                return JsonResponse({'error': f'Invalid git repository state: {str(e)}'}, status=500)
            except git.exc.GitCommandError as e:
                for item in tree_preview:
                    fpath = os.path.join(repo_path, item)
                    if os.path.exists(fpath):
                        os.remove(fpath)
                return JsonResponse({'error': f'Git tracking mechanism failed: {str(e)}'}, status=500)
                
            return JsonResponse({'success': True, 'tree': tree_preview, 'warnings': warnings})
            
        except Exception as e:
            return JsonResponse({'error': f'Failed to process upload: {str(e)}'}, status=500)

@login_required
@require_http_methods(["POST"])
def delete_repository(request, repo_id):
    """Delete a repository and all associated data (analysis, commits, files)."""
    repo = get_object_or_404(Repository, repository_id=repo_id, user=request.user)
    
    # Remove the repository files from disk
    repo_path = os.path.join(settings.MEDIA_ROOT, str(request.user.id), str(repo.repository_id))
    if os.path.exists(repo_path):
        shutil.rmtree(repo_path, ignore_errors=True)
    
    repo_name = repo.repo_name
    # Django CASCADE will delete: AnalysisReport -> CodeSmell -> RefactoringSuggestion, and Commit
    repo.delete()
    
    return JsonResponse({'success': True, 'message': f'Repository "{repo_name}" deleted successfully.'})
