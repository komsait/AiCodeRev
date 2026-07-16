import os
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone
from .models import RefactoringSuggestion
from analysis.models import CodeSmell
from analysis.services import AIService

def parse_line_range(line_range_str):
    """
    Parses a string representing a range of lines (e.g., '10-20' or 'Lines 10-20')
    into a set of integers for easy lookup during diff generation.

    Args:
        line_range_str (str): The raw line range string.

    Returns:
        set: A set containing all line numbers in the range.
    """
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
    """
    Attempts to merge a JSON-formatted code patch from the AI into the original code.
    If the suggestion is not valid JSON, it defaults to returning the suggestion as 
    a raw drop-in replacement for the entire file.

    Args:
        original_code (str): The full text of the original file.
        suggestion_text (str): The raw response from the AI.

    Returns:
        str: The fully merged/refactored file content.
    """
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
    """
    Generates a structured side-by-side diff representation between the original 
    and refactored code. This is used by the frontend to render the dual-pane UI.
    
    It highlights unchanged lines, deleted lines (red), and added lines (green).
    It also applies specific CSS classes to lines flagged as "code smells".

    Args:
        original_code (str): The original file content.
        refactored_code (str): The new file content.
        smell_line_range_str (str): The string representing the smelly lines.

    Returns:
        tuple: (left_side_data, right_side_data)
    """
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
    """
    Handles the dual-pane UI for reviewing and applying AI-suggested code fixes.
    Supports editable refactoring with three-way comparison.
    """
    
    def get(self, request):
        """
        Renders the refactoring review page. 
        If a specific smell is requested, it generates the side-by-side diff
        between the original file on disk and the AI's proposed patch.
        When an edit exists, also generates a third pane for the developer-edited version.
        
        Args:
            request: The HTTP GET request.
        """
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

        import json
        context = {
            'smell': smell,
            'suggestion': suggestion,
            'original_code': original_code,
            'refactored_content_json': json.dumps(refactored_content),
            'left_lines': left_lines,
            'right_lines': right_lines,
            'was_edited': suggestion.was_edited,
            'developer_edited_code_json': json.dumps(suggestion.developer_edited_code or ''),
        }

        # Generate third-pane diff if developer has edited the suggestion
        if suggestion.was_edited and suggestion.developer_edited_code:
            edited_left, edited_right = generate_side_by_side_diff(
                original_code, suggestion.developer_edited_code, smell.line_range
            )
            context['edited_left_lines'] = edited_left
            context['edited_right_lines'] = edited_right

        return render(request, 'refactoring.html', context)

    def post(self, request):
        """
        Handles user actions on a refactoring suggestion:
        - 'save_edit': Saves developer-edited refactoring code.
        - 'accept': Applies the correct version (edited or AI) to the repository file.
        - 'reject': Marks the suggestion as rejected, preserving edit history.
        - 'tune': (Disabled feature) Instructs the AI to rewrite the patch with custom instructions.

        Args:
            request: The HTTP POST request containing 'action' and 'suggestion_id'.
        """
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

        # --- Save Edit action (AJAX) ---
        if action == 'save_edit':
            suggestion_id = request.POST.get('suggestion_id')
            edited_code = request.POST.get('edited_code', '')
            suggestion = get_object_or_404(
                RefactoringSuggestion,
                suggestion_id=suggestion_id,
                smell__report__repository__user=request.user
            )

            # Validation: edited code must not be empty
            if not edited_code or not edited_code.strip():
                return JsonResponse({'error': 'Edited code cannot be empty.'}, status=400)

            # Save the developer-edited version (does NOT overwrite AI suggestion)
            suggestion.developer_edited_code = edited_code
            suggestion.was_edited = True
            suggestion.edited_at = timezone.now()
            suggestion.save()

            # Read original code for generating diffs
            repo_path = os.path.join(
                settings.MEDIA_ROOT,
                str(request.user.id),
                str(suggestion.smell.report.repository.repository_id)
            )
            target_file = os.path.join(repo_path, suggestion.smell.file_path)

            if not os.path.exists(target_file):
                return JsonResponse({'error': 'Original source file not found on disk.'}, status=404)

            with open(target_file, 'r', encoding='utf-8') as f:
                original_code = f.read()

            # Generate the AI suggestion diff (unchanged)
            refactored_content = get_refactored_file_content(original_code, suggestion.suggestion_text)
            left_lines, right_lines = generate_side_by_side_diff(
                original_code, refactored_content, suggestion.smell.line_range
            )

            # Generate the developer-edited diff
            edited_left, edited_right = generate_side_by_side_diff(
                original_code, edited_code, suggestion.smell.line_range
            )

            return JsonResponse({
                'success': True,
                'was_edited': True,
                'left_lines': left_lines,
                'right_lines': right_lines,
                'edited_left_lines': edited_left,
                'edited_right_lines': edited_right,
            })

        suggestion_id = request.POST.get('suggestion_id')
        suggestion = get_object_or_404(RefactoringSuggestion, suggestion_id=suggestion_id, smell__report__repository__user=request.user)
        
        if action == 'accept':
            # UC011 Apply logic — determine the correct code to apply
            suggestion.status = 'Accepted'
            suggestion.accepted_at = timezone.now()

            # Backend decides which version to apply
            if suggestion.was_edited and suggestion.developer_edited_code:
                final_code = suggestion.developer_edited_code
            else:
                final_code = suggestion.suggestion_text

            suggestion.applied_code = final_code
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

                # If the suggestion was NOT edited, try JSON patch format
                if not suggestion.was_edited:
                    new_code = final_code
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
                else:
                    # Developer-edited code is always applied as-is (full file replacement)
                    new_content = final_code
                        
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
            # Note: developer_edited_code and was_edited are preserved for traceability
            return redirect(f'/analysis-report/?repo={suggestion.smell.report.repository.repository_id}')
            
        return redirect('dashboard')
