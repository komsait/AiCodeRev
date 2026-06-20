import os
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.conf import settings
from django.http import JsonResponse
from .models import RefactoringSuggestion
from analysis.models import CodeSmell
from analysis.services import AIService

def parse_line_range(line_range_str):
    if not line_range_str:
        return set()
    import re
    numbers = [int(n) for n in re.findall(r'\d+', line_range_str)]
    if len(numbers) == 1:
        return {numbers[0]}
    elif len(numbers) >= 2:
        return set(range(numbers[0], numbers[1] + 1))
    return set()

def get_refactored_file_content(original_code, suggestion_text):
    original_lines = original_code.splitlines(keepends=True)
    try:
        import json
        parsed = json.loads(suggestion_text)
        if isinstance(parsed, list) and len(parsed) > 0:
            patch = parsed[0]
            start = max(0, int(patch.get('START_LINE', 1)) - 1)
            end = min(len(original_lines), int(patch.get('END_LINE', len(original_lines))))
            replacement = patch.get('NEW_CODE', '')
            
            if replacement:
                if not replacement.endswith('\n'):
                    replacement += '\n'
                patched_lines = list(original_lines)
                patched_lines[start:end] = [replacement]
                return "".join(patched_lines)
    except Exception:
        pass
    return suggestion_text

def generate_side_by_side_diff(original_code, refactored_code, smell_line_range_str):
    import difflib
    
    original_lines = original_code.splitlines()
    refactored_lines = refactored_code.splitlines()
    
    diff = difflib.ndiff(original_lines, refactored_lines)
    
    left_side = []
    right_side = []
    
    left_num = 0
    right_num = 0
    
    smell_lines = parse_line_range(smell_line_range_str)
    
    for line in diff:
        if line.startswith('? '):
            continue
            
        prefix = line[:2]
        content = line[2:]
        
        if prefix == '  ': # Unchanged
            left_num += 1
            right_num += 1
            is_smell = left_num in smell_lines
            left_side.append({
                'number': left_num,
                'content': content,
                'type': 'smell' if is_smell else 'normal',
                'class': 'line-smell' if is_smell else 'line-normal'
            })
            right_side.append({
                'number': right_num,
                'content': content,
                'type': 'normal',
                'class': 'line-normal'
            })
        elif prefix == '- ': # Deleted
            left_num += 1
            is_smell = left_num in smell_lines
            left_side.append({
                'number': left_num,
                'content': content,
                'type': 'deleted-smell' if is_smell else 'deleted',
                'class': 'line-deleted-smell' if is_smell else 'line-deleted'
            })
            right_side.append({
                'number': '',
                'content': '',
                'type': 'placeholder',
                'class': 'line-placeholder'
            })
        elif prefix == '+ ': # Added
            right_num += 1
            left_side.append({
                'number': '',
                'content': '',
                'type': 'placeholder',
                'class': 'line-placeholder'
            })
            right_side.append({
                'number': right_num,
                'content': content,
                'type': 'added',
                'class': 'line-added'
            })
            
    return left_side, right_side

class RefactoringView(LoginRequiredMixin, View):
    def get(self, request):
        smell_id = request.GET.get('smell')
        if not smell_id:
            recent_smells = CodeSmell.objects.filter(
                report__repository__user=request.user,
                is_resolved=False
            ).order_by('-report__analysis_date')[:15]
            return render(request, 'refactoring.html', {'status': 'no_smell', 'recent_smells': recent_smells})
            
        smell = get_object_or_404(CodeSmell, smell_id=smell_id, report__repository__user=request.user)
        
        # Check if suggestion already exists
        suggestion = smell.suggestions.filter(status='Pending').first()
        
        # Try to read original file context
        repo_path = os.path.join(settings.MEDIA_ROOT, str(request.user.id), str(smell.report.repository.repository_id))
        target_file = os.path.join(repo_path, smell.file_path)
        
        if not os.path.exists(target_file):
            from django.http import Http404
            raise Http404("Original source file not found on disk.")
            
        with open(target_file, 'r', encoding='utf-8') as f:
            original_code = f.read()

        if not suggestion:
            # Simulate generation (UC007)
            suggested_code = AIService.suggest_refactoring(smell, original_code=original_code)
            suggestion = RefactoringSuggestion.objects.create(
                smell=smell,
                suggestion_text=suggested_code
            )

        refactored_content = get_refactored_file_content(original_code, suggestion.suggestion_text)
        left_lines, right_lines = generate_side_by_side_diff(original_code, refactored_content, smell.line_range)

        context = {
            'smell': smell,
            'suggestion': suggestion,
            'original_code': original_code,
            'left_lines': left_lines,
            'right_lines': right_lines
        }
        return render(request, 'refactoring.html', context)

    def post(self, request):
        action = request.POST.get('action')
        
        if action == 'tune':
            instructions = request.POST.get('instructions')
            smell_id = request.POST.get('smell_id')
            smell = get_object_or_404(CodeSmell, smell_id=smell_id, report__repository__user=request.user)
            
            repo_path = os.path.join(settings.MEDIA_ROOT, str(request.user.id), str(smell.report.repository.repository_id))
            target_file = os.path.join(repo_path, smell.file_path)
            
            if not os.path.exists(target_file):
                return JsonResponse({'error': 'Original source file not found on disk.'}, status=404)
                
            with open(target_file, 'r', encoding='utf-8') as f:
                original_code = f.read()
                
            suggested_code = AIService.suggest_refactoring(smell, original_code=original_code, instructions=instructions)
            
            # Find existing pending suggestion or create a new one
            suggestion = smell.suggestions.filter(status='Pending').first()
            if suggestion:
                suggestion.suggestion_text = suggested_code
                suggestion.save()
            else:
                suggestion = RefactoringSuggestion.objects.create(
                    smell=smell,
                    suggestion_text=suggested_code
                )
                
            refactored_content = get_refactored_file_content(original_code, suggestion.suggestion_text)
            left_lines, right_lines = generate_side_by_side_diff(original_code, refactored_content, smell.line_range)
            
            return JsonResponse({
                'success': True,
                'suggestion_id': str(suggestion.suggestion_id),
                'left_lines': left_lines,
                'right_lines': right_lines
            })

        suggestion_id = request.POST.get('suggestion_id')
        suggestion = get_object_or_404(RefactoringSuggestion, suggestion_id=suggestion_id, smell__report__repository__user=request.user)
        
        if action == 'accept':
            # UC011 Apply logic
            suggestion.status = 'Accepted'
            suggestion.save()
            
            repo = suggestion.smell.report.repository
            repo_path = os.path.join(settings.MEDIA_ROOT, str(request.user.id), str(repo.repository_id))
            target_file = os.path.join(repo_path, suggestion.smell.file_path)
            
            # Intelligent Apply Logic using Patching
            try:
                original_lines = []
                if os.path.exists(target_file):
                    with open(target_file, 'r', encoding='utf-8') as f:
                        original_lines = f.readlines()
                
                new_code = suggestion.suggestion_text
                try:
                    import json
                    parsed = json.loads(new_code)
                    if isinstance(parsed, list) and len(parsed) > 0:
                        patch = parsed[0]
                        start = max(0, int(patch.get('START_LINE', 1)) - 1)
                        end = min(len(original_lines), int(patch.get('END_LINE', len(original_lines))))
                        replacement = patch.get('NEW_CODE', '')
                        
                        # Apply patch list insertion
                        if replacement:
                            if not replacement.endswith('\n'):
                                replacement += '\n'
                            original_lines[start:end] = [replacement]
                            new_content = "".join(original_lines)
                        else:
                            new_content = "".join(original_lines)
                    else:
                        new_content = new_code
                except Exception:
                    # Fallback to pure overwrite if not proper JSON patch
                    new_content = new_code
                        
                with open(target_file, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                
                # Mark as resolved instead of deleting, to preserve logs
                suggestion.smell.is_resolved = True
                suggestion.smell.save()
                
            except Exception as e:
                # Fallback to UI error if permissions fail
                pass
                
            return redirect(f'/commits/?repo={repo.repository_id}')
            
        elif action == 'reject':
            suggestion.status = 'Rejected'
            suggestion.save()
            return redirect(f'/analysis-report/?repo={suggestion.smell.report.repository.repository_id}')
            
        return redirect('dashboard')
