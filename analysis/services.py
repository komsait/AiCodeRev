import os
import re
import json
import time
import logging

logger = logging.getLogger(__name__)

import requests

# ---------------------------------------------------------------------------
# Chunking configuration
# ---------------------------------------------------------------------------
CHUNK_TARGET_LINES = 120      # Target chunk size in lines
CHUNK_MAX_LINES = 150         # Hard upper limit per chunk
CHUNK_MIN_LINES = 30          # Don't create tiny trailing chunks
MAX_RETRIES = 2               # Retry count for transient API failures
RETRY_BACKOFF_BASE = 2        # Seconds – exponential backoff base


class AIService:
    """
    AIService integration utilizing Gemini API.
    """

    # ------------------------------------------------------------------
    # Low-level Gemini caller with retry
    # ------------------------------------------------------------------
    @staticmethod
    def query_local_model(prompt, max_new_tokens=2048):
        """
        Deprecated: Used only for backward compatibility in tests.
        """
        from .providers.factory import AIProviderFactory
        try:
            provider = AIProviderFactory.get_provider()
            response = provider._execute_with_retry(prompt, max_tokens=max_new_tokens)
            return [{"generated_text": response}]
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Structure-aware code chunking
    # ------------------------------------------------------------------
    @staticmethod
    def _chunk_code(content, language_hint=""):
        """
        Splits *content* into chunks of ~CHUNK_TARGET_LINES lines.

        Strategy:
        1. Walk through lines looking for structural boundaries
           (class/function/method definitions, blank-line separators).
        2. When the current chunk reaches CHUNK_TARGET_LINES, look for the
           nearest boundary within ±20 lines to break at.
        3. Never exceed CHUNK_MAX_LINES.
        4. Merge a tiny trailing fragment (< CHUNK_MIN_LINES) into the
           previous chunk.

        Returns a list of (start_line_1indexed, chunk_text) tuples.
        """
        lines = content.split('\n')
        total = len(lines)

        if total <= CHUNK_MAX_LINES:
            return [(1, content)]

        # Detect structural boundary lines (0-indexed)
        boundary_pattern = re.compile(
            r'^\s*(def |class |function |public |private |protected |'
            r'static |void |int |String |async |export )',
        )
        boundaries = set()
        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                boundaries.add(i)            # blank line
            elif boundary_pattern.match(line):
                boundaries.add(i)            # structural keyword

        chunks = []
        chunk_start = 0                      # 0-indexed

        while chunk_start < total:
            ideal_end = chunk_start + CHUNK_TARGET_LINES
            hard_end = min(chunk_start + CHUNK_MAX_LINES, total)

            if ideal_end >= total:
                # Remaining lines fit in one chunk
                break_at = total
            else:
                # Look for the best boundary near ideal_end
                best = None
                for offset in range(0, 21):
                    for candidate in (ideal_end + offset, ideal_end - offset):
                        if (chunk_start < candidate <= hard_end
                                and candidate in boundaries):
                            best = candidate
                            break
                    if best is not None:
                        break
                break_at = best if best else hard_end

            chunk_text = '\n'.join(lines[chunk_start:break_at])
            chunks.append((chunk_start + 1, chunk_text))   # 1-indexed
            chunk_start = break_at

        # Merge tiny trailing chunk into the previous one
        if len(chunks) > 1:
            last_start, last_text = chunks[-1]
            if last_text.count('\n') + 1 < CHUNK_MIN_LINES:
                prev_start, prev_text = chunks[-2]
                chunks[-2] = (prev_start, prev_text + '\n' + last_text)
                chunks.pop()

        return chunks

    # ------------------------------------------------------------------
    # Main analysis pipeline  (UC004 + UC005)
    # ------------------------------------------------------------------
    @staticmethod
    def extract_and_send(repo_path, files_to_analyze=None):
        """
        Traverses repo, extracts code, chunks large files, and requests
        Gemini analysis per chunk (UC004).  Results are aggregated with
        correct per-file line offsets.
        """
        supported_exts = ['.py', '.java', '.js', '.php', '.rb', '.go', '.c', '.cs']
        all_smells = []

        files_found = []
        for root, dirs, files in os.walk(repo_path):
            if '.git' in root or 'venv' in root or '__pycache__' in root:
                continue
            for file in files:
                if any(file.endswith(ext) for ext in supported_exts):
                    if files_to_analyze and file not in files_to_analyze:
                        continue
                    files_found.append(os.path.join(root, file))

        # PROTOTYPE LIMIT: Cap to 5 files to prevent long processing times.
        # TODO: Remove or increase this limit for production deployment.
        files_found = files_found[:5]

        for file_path in files_found:
            rel_path = os.path.relpath(file_path, repo_path)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Determine language hint from extension
                ext = os.path.splitext(file_path)[1].lower()
                lang_hint = {
                    '.py': 'Python', '.java': 'Java', '.js': 'JavaScript',
                    '.php': 'PHP', '.rb': 'Ruby', '.go': 'Go',
                    '.c': 'C', '.cs': 'C#'
                }.get(ext, '')

                # --- Send entire file at once to avoid duplicate chunk-level smells ---
                chunks = [(1, content)]
                file_parsed_ok = False

                for chunk_start_line, chunk_text in chunks:
                    # Cap file size to ~300k chars to prevent massive context explosion
                    chunk_text_safe = chunk_text[:300000]

                    try:
                        from .providers.factory import AIProviderFactory
                        provider = AIProviderFactory.get_provider()
                        json_str = provider.detect_code_smells(
                            code=chunk_text_safe,
                            file_path=rel_path,
                            language=lang_hint,
                            chunk_start_line=chunk_start_line
                        )
                        
                        # Find the first '[' and last ']' to extract JSON array
                        start = json_str.find('[')
                        end = json_str.rfind(']') + 1
                        
                        if start != -1 and end != 0 and start < end:
                            json_data = json_str[start:end]
                            try:
                                smells = json.loads(json_data)
                            except json.JSONDecodeError:
                                # Fallback: try to fix trailing commas or common issues, or use regex
                                # Alternatively, just log the raw output for debugging
                                raise Exception(f"JSONDecodeError on: {json_data[:100]}...")
                                
                            if isinstance(smells, list):
                                for s in smells:
                                    if not isinstance(s, dict):
                                        continue
                                    s['file_path'] = rel_path
                                    
                                    # Always ensure line_range exists for the DB
                                    start_line = s.get('start_line', '')
                                    end_line = s.get('end_line', '')
                                    raw_range = str(s.get('line_range', f"{start_line}-{end_line}" if start_line and end_line else start_line))
                                    s['line_range'] = raw_range
                                    all_smells.append(s)
                                file_parsed_ok = True
                    except Exception as e:
                        logger.error(f"Analysis failed for {rel_path}: {e}")
                        # Keep track of error for the heuristic fallback
                        last_error = str(e)

                if not file_parsed_ok:
                    # All chunks failed -> heuristic fallback for this file
                    total_lines = content.count('\n') + 1
                    err_msg = locals().get('last_error', 'LLM timeout/parsing failure.')
                    all_smells.append({
                        "smell_type": "Complexity/Length Issue",
                        "severity_level": "Major",
                        "file_path": rel_path,
                        "line_range": f"Lines 1-{total_lines}",
                        "description": f"Analysis defaulted to heuristic rules due to AI failure: {err_msg}"
                    })

            except Exception as e:
                logger.error(f"Failed processing {file_path}: {e}")

        if not all_smells:
            all_smells.append({
                "smell_type": "No Analytical Findings",
                "severity_level": "Minor",
                "file_path": "repository_root",
                "line_range": "0",
                "description": (
                    "The analyzer did not identify any actionable smells "
                    "in the scanned files."
                )
            })

        return {"smells": all_smells}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _offset_line_range(raw_range, offset):
        """
        Adds *offset* to every number found in *raw_range*.
        E.g. "Lines 5-20" with offset 120 → "Lines 125-140"
        """
        def _add(m):
            return str(int(m.group()) + offset)
        return re.sub(r'\d+', _add, raw_range)

    @staticmethod
    def classify_and_store(raw_response, repository):
        """
        Parses AI response, classifies smells and persists them to
        Database (UC005).
        """
        from .models import AnalysisReport, CodeSmell

        try:
            from .providers.factory import AIProviderFactory
            provider = AIProviderFactory.get_provider()
            ai_model = f"{provider.provider_name} / {provider.model_name}"
        except Exception:
            ai_model = "Unknown AI Provider"

        report = AnalysisReport.objects.create(
            repository=repository,
            ai_model=ai_model
        )

        for smell_data in raw_response.get("smells", []):
            severity = str(smell_data.get("severity_level", "Minor")).capitalize()
            if severity not in ["Major", "Moderate", "Minor"]:
                severity = "Moderate"  # normalize format

            CodeSmell.objects.create(
                report=report,
                smell_type=smell_data.get("smell_type", "Unknown Smell")[:100],
                severity_level=severity,
                file_path=smell_data.get("file_path", "unknown")[:500],
                line_range=str(smell_data.get("line_range", ""))[:100],
                description=str(smell_data.get(
                    "description", "No description provided."
                ))
            )

        return report

    @staticmethod
    def suggest_refactoring(code_smell, original_code="", instructions=None):
        """
        Requests refactoring generation from Gemini API (UC007).
        """
        try:
            from .providers.factory import AIProviderFactory
            provider = AIProviderFactory.get_provider()
            return provider.generate_refactoring(code_smell, original_code, instructions=instructions)
        except Exception as e:
            return (
                f"# Refactoring failed. Ensure AI provider is configured.\n"
                f"# Target Issue: {code_smell.smell_type}\n"
                f"# {code_smell.description}\n\n"
                f"def apply_patch():\n    pass # Implement fix manually"
            )

    @staticmethod
    def generate_commit_message(diff_summary):
        """
        Generates Git commit messages using Gemini API based on
        git diff (UC008).
        """
        if not diff_summary:
            return "Auto-commit: saved changes"

        try:
            from .providers.factory import AIProviderFactory
            provider = AIProviderFactory.get_provider()
            msg = provider.generate_commit_message(diff_summary[:1000])
            if msg.startswith('"') and msg.endswith('"'):
                msg = msg[1:-1]
            if msg:
                return msg
        except Exception:
            pass

        return "Refactor: apply automated repository optimizations"
