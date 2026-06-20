import git

class GitService:
    @staticmethod
    def get_status(repo_path):
        repo = git.Repo(repo_path)
        
        changed_files = [item.a_path for item in repo.index.diff(None)]
        untracked_files = repo.untracked_files
        
        # files staged for commit
        staged_files = [item.a_path for item in repo.index.diff("HEAD")] if repo.heads else []
        
        return {
            'changed': changed_files,
            'untracked': untracked_files,
            'staged': staged_files
        }
        
    @staticmethod
    def get_diff_summary(repo_path):
        repo = git.Repo(repo_path)
        diff = repo.git.diff('HEAD') if repo.heads else repo.git.diff()
        return diff
        
    @staticmethod
    def commit_all(repo_path, message):
        repo = git.Repo(repo_path)
        repo.git.add(A=True)
        if not repo.is_dirty(index=True, untracked_files=True):
            raise Exception("Nothing to commit: working tree is clean.")
        commit = repo.index.commit(message)
        return commit.hexsha

    @staticmethod
    def get_log(repo_path, max_count=50):
        repo = git.Repo(repo_path)
        if not repo.heads:
            return []
        
        try:
            branch = repo.active_branch.name
        except TypeError:
            branch = repo.heads[0].name
        
        commits = list(repo.iter_commits(branch, max_count=max_count))
        result = []
        for c in commits:
            result.append({
                'hash': c.hexsha,
                'message': c.message,
                'author': c.author.name,
                'date': c.committed_datetime
            })
        return result
        
    @staticmethod
    def get_commit_diff_files(repo_path, commit_hash):
        repo = git.Repo(repo_path)
        commit = repo.commit(commit_hash)

        if commit.parents:
            parent = commit.parents[0]
            diffs = parent.diff(commit, create_patch=False)
        else:
            diffs = commit.diff(git.NULL_TREE, create_patch=False)

        files = []

        for d in diffs:
            old_path = d.a_path
            new_path = d.b_path
            filename = new_path or old_path

            change_type = d.change_type

            if change_type == 'A':
                status = 'new'
            elif change_type == 'D':
                status = 'deleted'
            elif change_type == 'R':
                status = 'renamed'
            else:
                status = 'modified'

            old_content = ""
            new_content = ""

            if status != 'new' and d.a_blob:
                try:
                    old_content = d.a_blob.data_stream.read().decode("utf-8", errors="replace")
                except Exception:
                    old_content = "Binary file or unreadable content."

            if status != 'deleted' and d.b_blob:
                try:
                    new_content = d.b_blob.data_stream.read().decode("utf-8", errors="replace")
                except Exception:
                    new_content = "Binary file or unreadable content."

            files.append({
                "filename": filename,
                "old_path": old_path,
                "new_path": new_path,
                "status": status,
                "old_content": old_content,
                "new_content": new_content,
            })

        return files
