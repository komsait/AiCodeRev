import os
import shutil
import tempfile
from django.shortcuts import render, get_object_or_404
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import FileResponse
from django.conf import settings
from repository.models import Repository

class ExportView(LoginRequiredMixin, View):
    def get(self, request):
        repo_id = request.GET.get('repo')
        repos = Repository.objects.filter(user=request.user)
        
        if not repo_id and repos.exists():
            return render(request, 'export.html', {'status': 'no_repo', 'repos': repos})
            
        if not repo_id:
            return render(request, 'export.html', {'status': 'no_repo', 'repos': []})
            
        repo = get_object_or_404(Repository, repository_id=repo_id, user=request.user)
        context = {
            'status': 'loaded',
            'repo': repo,
            'repos': repos
        }
        return render(request, 'export.html', context)

    def post(self, request):
        repo_id = request.POST.get('repo_id')
        repo = get_object_or_404(Repository, repository_id=repo_id, user=request.user)
        repo_path = os.path.join(settings.MEDIA_ROOT, str(request.user.id), str(repo.repository_id))
        
        # Create a temporary file to hold the zip
        temp_file = tempfile.NamedTemporaryFile(suffix='.zip', delete=False)
        temp_zip_path = temp_file.name
        temp_file.close()
        
        # shutil.make_archive adds .zip to the base_name by default,
        # so we strip it when passing to make_archive to avoid .zip.zip
        base_name = temp_zip_path[:-4]
        shutil.make_archive(base_name, 'zip', repo_path)
        
        # Open and serve the file, then clean up
        zip_file = open(temp_zip_path, 'rb')
        response = FileResponse(zip_file, as_attachment=True, filename=f"{repo.repo_name}_export.zip")
        
        # Schedule cleanup after the response is sent
        response._resource_closers.append(lambda: _cleanup_temp_file(temp_zip_path))
        
        return response

def _cleanup_temp_file(path):
    """Remove temporary zip file after it has been served."""
    import time
    from django.conf import settings
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        time.sleep(1)
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError:
            try:
                log_path = os.path.join(settings.MEDIA_ROOT, 'temp_cleanup_pending.txt')
                with open(log_path, 'a', encoding='utf-8') as f:
                    f.write(path + '\n')
            except Exception:
                pass
