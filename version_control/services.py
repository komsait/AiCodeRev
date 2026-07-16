import git

class GitService:
    """
    A service class that wraps the GitPython library to execute Git commands
    on the downloaded repositories in the workspace directory.
    """
    
    @staticmethod
    def get_status(repo_path):
        """
        Retrieves the current Git status of the repository, including changed, 
        untracked, and staged files.

        Args:
            repo_path (str): The absolute path to the local repository.

        Returns:
            dict: A dictionary containing lists of 'changed', 'untracked', and 'staged' files.
        """
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
        """
        Generates a summary of all unstaged changes in the working directory.
        Used primarily by the AI to generate automated commit messages.

        Args:
            repo_path (str): The absolute path to the local repository.

        Returns:
            str: The raw string output of `git diff`.
        """
        repo = git.Repo(repo_path)
        diff = repo.git.diff('HEAD') if repo.heads else repo.git.diff()
        return diff
        
    @staticmethod
    def commit_all(repo_path, message):
        """
        Stages all changes in the working directory (`git add -A`) and commits them
        with the provided message.

        Args:
            repo_path (str): The absolute path to the local repository.
            message (str): The commit message.

        Returns:
            str: The SHA hash of the new commit.
            
        Raises:
            Exception: If there is nothing to commit.
        """
        repo = git.Repo(repo_path)
        repo.git.add(A=True)
        if not repo.is_dirty(index=True, untracked_files=True):
            raise Exception("Nothing to commit: working tree is clean.")
        commit = repo.index.commit(message)
        return commit.hexsha

    @staticmethod
    def get_log(repo_path, max_count=50):
        """
        Retrieves the commit history (git log) for the active branch.

        Args:
            repo_path (str): The absolute path to the local repository.
            max_count (int): The maximum number of commits to return. Defaults to 50.

        Returns:
            list: A list of dictionaries containing commit metadata (hash, message, author, date).
        """
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
        """
        Extracts the list of files changed in a specific commit, along with the 
        old and new content of each file to render a diff view.

        For initial commits (no parent), compares against the empty Git tree so
        that the old side is empty and the new side shows the full committed content.

        Args:
            repo_path (str): The absolute path to the local repository.
            commit_hash (str): The SHA hash of the target commit.

        Returns:
            dict: A dictionary with 'files' (list of change dicts) and
                  'is_initial_commit' (bool).
        """
        repo = git.Repo(repo_path)
        commit = repo.commit(commit_hash)
        is_initial_commit = len(commit.parents) == 0

        if commit.parents:
            parent = commit.parents[0]
            diffs = parent.diff(commit, create_patch=False)
        else:
            # Initial commit: compare empty tree → commit tree.
            # Using the well-known empty tree SHA so the diff direction is
            # correct (old=empty, new=committed files).
            EMPTY_TREE_SHA = '4b825dc642cb6eb9a060e54bf8d69288fbee4904'
            empty_tree = repo.tree(EMPTY_TREE_SHA)
            diffs = empty_tree.diff(commit.tree, create_patch=False)

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
                "is_initial_commit": is_initial_commit,
            })

        return {"files": files, "is_initial_commit": is_initial_commit}
