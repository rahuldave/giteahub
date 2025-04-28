"""
Gitea to Hugging Face Hub Adapter Library

This library provides an adapter to use Gitea as a backend for Hugging Face Hub functionality.
"""

import os
import json
import requests
import tempfile
import shutil
import logging
from pathlib import Path
from typing import Dict, List, Optional, Union, BinaryIO, Tuple, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GiteaHubClient:
    """
    Client for interacting with Gitea API in a way that's compatible with huggingface_hub.
    """

    def __init__(
        self,
        gitea_url: str,
        token: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None
    ):
        """
        Initialize the Gitea Hub client.

        Args:
            gitea_url: Base URL for the Gitea server (e.g., "https://gitea.example.com")
            token: Personal access token for Gitea authentication
            username: Username for basic auth if token isn't provided
            password: Password for basic auth if token isn't provided
        """
        self.gitea_url = gitea_url.rstrip('/')
        self.api_url = f"{self.gitea_url}/api/v1"
        self.token = token
        self.username = username
        self.password = password

        self.session = requests.Session()

        if token:
            self.session.headers.update({
                "Authorization": f"token {token}"
            })
        elif username and password:
            self.session.auth = (username, password)

        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json"
        })

    def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """
        Make a request to the Gitea API.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (without base URL)
            **kwargs: Additional arguments to pass to requests

        Returns:
            Response object
        """
        url = f"{self.api_url}{endpoint}"
        response = self.session.request(method, url, **kwargs)

        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error: {e}")
            logger.error(f"Response content: {response.text}")
            raise

        return response

    # Repository management functions

    def create_repo(
        self,
        repo_id: str,
        private: bool = False,
        repo_type: str = "model",
        exist_ok: bool = False
    ) -> Dict:
        """
        Create a new repository on Gitea.

        Args:
            repo_id: ID of the repository (e.g., "username/repo-name")
            private: Whether the repository is private
            repo_type: Type of repository (model, dataset, or space)
            exist_ok: If True, don't error if repo already exists

        Returns:
            Dictionary with repository information
        """
        if "/" not in repo_id:
            raise ValueError("repo_id must be in the format 'username/repo-name'")

        owner, name = repo_id.split('/', 1)

        # Check if repo exists if exist_ok is True
        if exist_ok:
            try:
                return self.get_repo_info(repo_id)
            except requests.exceptions.HTTPError as e:
                if e.response.status_code != 404:
                    raise

        data = {
            "name": name,
            "private": private,
            "description": f"A {repo_type} repository",
            "auto_init": True,  # Initialize with README
        }

        # For organization repos, use a different endpoint
        try:
            response = self._make_request("POST", f"/org/{owner}/repos", json=data)
        except requests.exceptions.HTTPError as e:
            # If not an org, try creating a user repo
            if e.response.status_code == 404 or e.response.status_code == 422:
                response = self._make_request("POST", "/user/repos", json=data)
            else:
                raise

        repo_info = response.json()

        # Add repo_type as a topic for later filtering
        self.update_repo_topics(repo_id, [repo_type])

        return repo_info

    def get_repo_info(self, repo_id: str) -> Dict:
        """
        Get information about a repository.

        Args:
            repo_id: ID of the repository (e.g., "username/repo-name")

        Returns:
            Dictionary with repository information
        """
        owner, name = repo_id.split('/', 1)
        response = self._make_request("GET", f"/repos/{owner}/{name}")
        return response.json()

    def update_repo_topics(self, repo_id: str, topics: List[str]) -> Dict:
        """
        Update repository topics.

        Args:
            repo_id: ID of the repository
            topics: List of topics to assign to the repo

        Returns:
            Updated repository information
        """
        owner, name = repo_id.split('/', 1)

        # First get existing topics
        repo_info = self.get_repo_info(repo_id)
        existing_topics = repo_info.get("topics", [])

        # Merge existing topics with new ones
        all_topics = list(set(existing_topics + topics))

        data = {
            "topics": all_topics
        }

        response = self._make_request("PUT", f"/repos/{owner}/{name}/topics", json=data)
        return response

    def delete_repo(self, repo_id: str) -> bool:
        """
        Delete a repository.

        Args:
            repo_id: ID of the repository

        Returns:
            True if successful
        """
        owner, name = repo_id.split('/', 1)
        self._make_request("DELETE", f"/repos/{owner}/{name}")
        return True

    # File operations

    def upload_file(
        self,
        repo_id: str,
        local_path: Union[str, Path],
        repo_path: Optional[str] = None,
        commit_message: Optional[str] = None,
        branch: str = "main"
    ) -> Dict:
        """
        Upload a file to a repository.

        Args:
            repo_id: ID of the repository
            local_path: Path to the local file
            repo_path: Path in the repository (defaults to filename)
            commit_message: Commit message (defaults to "Upload {filename}")
            branch: Branch to commit to

        Returns:
            Dictionary with commit information
        """
        owner, name = repo_id.split('/', 1)
        local_path = Path(local_path)

        if not repo_path:
            repo_path = local_path.name

        if repo_path.startswith('/'):
            repo_path = repo_path[1:]

        if not commit_message:
            commit_message = f"Upload {local_path.name}"

        # The Gitea API expects content to be base64 encoded, but we'll avoid loading
        # large files into memory by using the create_content endpoint which accepts
        # multipart/form-data

        # Get the SHA of the file if it already exists
        sha = None
        try:
            file_info = self._make_request("GET", f"/repos/{owner}/{name}/contents/{repo_path}?ref={branch}")
            sha = file_info.json().get("sha")
        except requests.exceptions.HTTPError as e:
            if e.response.status_code != 404:
                raise

        # Prepare the file upload
        with open(local_path, 'rb') as f:
            files = {
                'file': (repo_path, f)
            }

            form_data = {
                'message': commit_message,
                'branch': branch
            }

            if sha:
                form_data['sha'] = sha

            endpoint = f"/repos/{owner}/{name}/contents/{repo_path}"
            response = self._make_request("PUT", endpoint, files=files, data=form_data)

        return response.json()

    def upload_folder(
        self,
        repo_id: str,
        local_folder: Union[str, Path],
        repo_folder: Optional[str] = None,
        commit_message: Optional[str] = None,
        branch: str = "main"
    ) -> Dict:
        """
        Upload a folder to a repository.

        Args:
            repo_id: ID of the repository
            local_folder: Path to the local folder
            repo_folder: Path in the repository (defaults to folder name)
            commit_message: Commit message
            branch: Branch to commit to

        Returns:
            Dictionary with commit information
        """
        local_folder = Path(local_folder)

        if not repo_folder:
            repo_folder = local_folder.name

        if not commit_message:
            commit_message = f"Upload folder {local_folder.name}"

        # Upload each file in the folder
        results = []
        for item in local_folder.glob('**/*'):
            if item.is_file():
                rel_path = item.relative_to(local_folder)
                repo_path = f"{repo_folder}/{rel_path}" if repo_folder else str(rel_path)

                result = self.upload_file(
                    repo_id=repo_id,
                    local_path=item,
                    repo_path=repo_path,
                    commit_message=f"{commit_message} - {rel_path}",
                    branch=branch
                )
                results.append(result)

        return {"files": results}

    def download_file(
        self,
        repo_id: str,
        repo_path: str,
        local_path: Optional[Union[str, Path]] = None,
        revision: Optional[str] = None
    ) -> Path:
        """
        Download a file from a repository.

        Args:
            repo_id: ID of the repository
            repo_path: Path in the repository
            local_path: Path to save the file locally (defaults to current dir)
            revision: Specific revision (branch, tag, or commit) to download from

        Returns:
            Path to the downloaded file
        """
        owner, name = repo_id.split('/', 1)

        if repo_path.startswith('/'):
            repo_path = repo_path[1:]

        if not local_path:
            local_path = Path.cwd() / Path(repo_path).name
        else:
            local_path = Path(local_path)

        # Create directory if it doesn't exist
        local_path.parent.mkdir(parents=True, exist_ok=True)

        # Get the raw file content
        endpoint = f"/repos/{owner}/{name}/raw/{repo_path}"
        if revision:
            endpoint = f"/repos/{owner}/{name}/raw/{revision}/{repo_path}"

        response = self._make_request("GET", endpoint)

        # Save the file
        with open(local_path, 'wb') as f:
            f.write(response.content)

        return local_path

    def list_files(
        self,
        repo_id: str,
        path: str = "",
        revision: Optional[str] = None
    ) -> List[Dict]:
        """
        List files in a repository directory.

        Args:
            repo_id: ID of the repository
            path: Path in the repository
            revision: Specific revision (branch, tag, or commit)

        Returns:
            List of file information dictionaries
        """
        owner, name = repo_id.split('/', 1)

        if path and path.startswith('/'):
            path = path[1:]

        endpoint = f"/repos/{owner}/{name}/contents/{path}"
        if revision:
            endpoint = f"{endpoint}?ref={revision}"

        response = self._make_request("GET", endpoint)
        return response.json()

    # Hugging Face Hub compatibility methods

    def create_commit(
        self,
        repo_id: str,
        operations: List[Dict],
        commit_message: str,
        branch: Optional[str] = None,
        commit_description: Optional[str] = None,
        parent_commit: Optional[str] = None
    ) -> Dict:
        """
        Create a commit with multiple file operations, similar to HF Hub's create_commit.

        Args:
            repo_id: ID of the repository
            operations: List of operations to perform (add, delete, etc.)
            commit_message: Commit message
            branch: Branch to commit to (defaults to 'main')
            commit_description: Extended commit description
            parent_commit: Parent commit SHA (not used in this implementation)

        Returns:
            Dictionary with commit information
        """
        if not branch:
            branch = "main"

        results = []

        # Process each operation
        for op in operations:
            op_type = op.get("type")

            if op_type == "add":
                path = op.get("path")
                content = op.get("content")

                # For file content provided as bytes or string
                if content:
                    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                        if isinstance(content, bytes):
                            temp_file.write(content)
                        else:
                            temp_file.write(content.encode('utf-8'))
                        temp_path = temp_file.name

                    try:
                        result = self.upload_file(
                            repo_id=repo_id,
                            local_path=temp_path,
                            repo_path=path,
                            commit_message=commit_message,
                            branch=branch
                        )
                        results.append(result)
                    finally:
                        os.unlink(temp_path)

                # For file content provided as a local path
                elif op.get("local_path"):
                    result = self.upload_file(
                        repo_id=repo_id,
                        local_path=op.get("local_path"),
                        repo_path=path,
                        commit_message=commit_message,
                        branch=branch
                    )
                    results.append(result)

            elif op_type == "delete":
                path = op.get("path")
                owner, name = repo_id.split('/', 1)

                # Get the SHA of the file
                file_info = self._make_request(
                    "GET",
                    f"/repos/{owner}/{name}/contents/{path}?ref={branch}"
                )
                sha = file_info.json().get("sha")

                # Delete the file
                data = {
                    "message": commit_message,
                    "sha": sha,
                    "branch": branch
                }
                response = self._make_request("DELETE", f"/repos/{owner}/{name}/contents/{path}", json=data)
                results.append(response.json())

            elif op_type == "copy":
                src_path = op.get("src_path")
                dst_path = op.get("dst_path")

                # Download the source file to a temporary location
                temp_dir = tempfile.mkdtemp()
                try:
                    temp_file_path = self.download_file(
                        repo_id=repo_id,
                        repo_path=src_path,
                        local_path=os.path.join(temp_dir, os.path.basename(src_path)),
                        revision=branch
                    )

                    # Upload it to the destination path
                    result = self.upload_file(
                        repo_id=repo_id,
                        local_path=temp_file_path,
                        repo_path=dst_path,
                        commit_message=commit_message,
                        branch=branch
                    )
                    results.append(result)
                finally:
                    shutil.rmtree(temp_dir, ignore_errors=True)
                path = op.get("path")
                content = op.get("content")

                # For file content provided as bytes or string
                if content:
                    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                        if isinstance(content, bytes):
                            temp_file.write(content)
                        else:
                            temp_file.write(content.encode('utf-8'))
                        temp_path = temp_file.name

                    try:
                        result = self.upload_file(
                            repo_id=repo_id,
                            local_path=temp_path,
                            repo_path=path,
                            commit_message=commit_message,
                            branch=branch
                        )
                        results.append(result)
                    finally:
                        os.unlink(temp_path)

                # For file content provided as a local path
                elif op.get("local_path"):
                    result = self.upload_file(
                        repo_id=repo_id,
                        local_path=op.get("local_path"),
                        repo_path=path,
                        commit_message=commit_message,
                        branch=branch
                    )
                    results.append(result)

            elif op_type == "delete":
                path = op.get("path")
                owner, name = repo_id.split('/', 1)

                # Get the SHA of the file
                file_info = self._make_request(
                    "GET",
                    f"/repos/{owner}/{name}/contents/{path}?ref={branch}"
                )
                sha = file_info.json().get("sha")

                # Delete the file
                data = {
                    "message": commit_message,
                    "sha": sha,
                    "branch": branch
                }
                response = self._make_request("DELETE", f"/repos/{owner}/{name}/contents/{path}", json=data)
                results.append(response.json())

            elif op_type == "copy":
                src_path = op.get("src_path")
                dst_path = op.get("dst_path")

                # Download the source file to a temporary location
                temp_dir = tempfile.mkdtemp()
                try:
                    temp_file_path = self.download_file(
                        repo_id=repo_id,
                        repo_path=src_path,
                        local_path=os.path.join(temp_dir, os.path.basename(src_path)),
                        revision=branch
                    )

                    # Upload it to the destination path
                    result = self.upload_file(
                        repo_id=repo_id,
                        local_path=temp_file_path,
                        repo_path=dst_path,
                        commit_message=commit_message,
                        branch=branch
                    )
                    results.append(result)
                finally:
                    shutil.rmtree(temp_dir, ignore_errors=True)

        return {
            "commit_url": f"{self.gitea_url}/{repo_id}/commit/{branch}",
            "operations": results
        }

    def upload_file_to_hub(
        self,
        path_or_fileobj: Union[str, Path, BinaryIO],
        path_in_repo: str,
        repo_id: str,
        token: Optional[str] = None,
        repo_type: str = "model",
        revision: Optional[str] = None,
        commit_message: Optional[str] = None,
        commit_description: Optional[str] = None,
        create_pr: bool = False,
    ) -> Dict:
        """
        Direct replacement for huggingface_hub's upload_file function.

        Args:
            path_or_fileobj: Path to a file or a file-like object
            path_in_repo: Path in the repository
            repo_id: ID of the repository
            token: Authentication token (uses instance token if not provided)
            repo_type: Type of repository (model, dataset, or space)
            revision: Specific revision (branch, tag, or commit)
            commit_message: Commit message
            commit_description: Extended commit description
            create_pr: Whether to create a pull request (not implemented)

        Returns:
            Dictionary with commit information
        """
        if create_pr:
            logger.warning("Pull request creation is not implemented in this adapter")

        if token and token != self.token:
            # Create a temporary client with the new token
            temp_client = GiteaHubClient(self.gitea_url, token=token)
            return temp_client.upload_file_to_hub(
                path_or_fileobj=path_or_fileobj,
                path_in_repo=path_in_repo,
                repo_id=repo_id,
                token=None,  # Already used in the temp client
                repo_type=repo_type,
                revision=revision,
                commit_message=commit_message,
                commit_description=commit_description,
            )

        if not revision:
            revision = "main"

        if not commit_message:
            if isinstance(path_or_fileobj, (str, Path)):
                filename = os.path.basename(str(path_or_fileobj))
            else:
                filename = os.path.basename(path_in_repo)
            commit_message = f"Upload {filename}"

        # Check if repo exists, if not create it
        try:
            self.get_repo_info(repo_id)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                self.create_repo(repo_id, repo_type=repo_type)
            else:
                raise

        # Handle file-like objects by saving to a temporary file
        if not isinstance(path_or_fileobj, (str, Path)):
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                shutil.copyfileobj(path_or_fileobj, temp_file)
                temp_path = temp_file.name

            try:
                result = self.upload_file(
                    repo_id=repo_id,
                    local_path=temp_path,
                    repo_path=path_in_repo,
                    commit_message=commit_message,
                    branch=revision
                )
            finally:
                os.unlink(temp_path)
        else:
            result = self.upload_file(
                repo_id=repo_id,
                local_path=path_or_fileobj,
                repo_path=path_in_repo,
                commit_message=commit_message,
                branch=revision
            )

        return result

    def upload_folder_to_hub(
        self,
        folder_path: Union[str, Path],
        repo_id: str,
        path_in_repo: Optional[str] = None,
        token: Optional[str] = None,
        repo_type: str = "model",
        revision: Optional[str] = None,
        commit_message: Optional[str] = None,
        commit_description: Optional[str] = None,
        create_pr: bool = False,
        ignore_patterns: Optional[List[str]] = None,
    ) -> Dict:
        """
        Direct replacement for huggingface_hub's upload_folder function.

        Args:
            folder_path: Path to the folder to upload
            repo_id: ID of the repository
            path_in_repo: Path in the repository
            token: Authentication token (uses instance token if not provided)
            repo_type: Type of repository (model, dataset, or space)
            revision: Specific revision (branch, tag, or commit)
            commit_message: Commit message
            commit_description: Extended commit description
            create_pr: Whether to create a pull request (not implemented)
            ignore_patterns: List of file patterns to ignore

        Returns:
            Dictionary with commit information
        """
        if create_pr:
            logger.warning("Pull request creation is not implemented in this adapter")

        if token and token != self.token:
            # Create a temporary client with the new token
            temp_client = GiteaHubClient(self.gitea_url, token=token)
            return temp_client.upload_folder_to_hub(
                folder_path=folder_path,
                repo_id=repo_id,
                path_in_repo=path_in_repo,
                token=None,  # Already used in the temp client
                repo_type=repo_type,
                revision=revision,
                commit_message=commit_message,
                commit_description=commit_description,
            )

        if not revision:
            revision = "main"

        if not commit_message:
            folder_name = os.path.basename(str(folder_path))
            commit_message = f"Upload folder {folder_name}"

        # Check if repo exists, if not create it
        try:
            self.get_repo_info(repo_id)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                self.create_repo(repo_id, repo_type=repo_type)
            else:
                raise

        result = self.upload_folder(
            repo_id=repo_id,
            local_folder=folder_path,
            repo_folder=path_in_repo,
            commit_message=commit_message,
            branch=revision
        )

        return result

    def download_file_from_hub(
        self,
        repo_id: str,
        filename: str,
        revision: Optional[str] = None,
        repo_type: Optional[str] = None,
        local_dir: Optional[Union[str, Path]] = None,
        local_dir_use_symlinks: bool = True,
        token: Optional[str] = None,
        library_name: Optional[str] = None,
        library_version: Optional[str] = None,
    ) -> str:
        """
        Direct replacement for huggingface_hub's hf_hub_download function.

        Args:
            repo_id: ID of the repository
            filename: Name of the file to download
            revision: Specific revision (branch, tag, or commit)
            repo_type: Type of repository (not used in this implementation)
            local_dir: Directory to save the file to
            local_dir_use_symlinks: Whether to use symlinks (not used in this implementation)
            token: Authentication token (uses instance token if not provided)
            library_name: Name of the library (not used in this implementation)
            library_version: Version of the library (not used in this implementation)

        Returns:
            Path to the downloaded file
        """
        if token and token != self.token:
            # Create a temporary client with the new token
            temp_client = GiteaHubClient(self.gitea_url, token=token)
            return temp_client.download_file_from_hub(
                repo_id=repo_id,
                filename=filename,
                revision=revision,
                repo_type=repo_type,
                local_dir=local_dir,
                local_dir_use_symlinks=local_dir_use_symlinks,
                token=None,  # Already used in the temp client
                library_name=library_name,
                library_version=library_version,
            )

        local_path = None
        if local_dir:
            local_path = Path(local_dir) / filename

        downloaded_path = self.download_file(
            repo_id=repo_id,
            repo_path=filename,
            local_path=local_path,
            revision=revision
        )

        return str(downloaded_path)

    def get_hf_file_metadata(
        self,
        repo_id: str,
        filename: str,
        revision: Optional[str] = None,
        repo_type: Optional[str] = None,
        token: Optional[str] = None,
    ) -> Dict:
        """
        Get metadata for a file in a repository (HF Hub compatibility).

        Args:
            repo_id: ID of the repository
            filename: Name of the file to get metadata for
            revision: Specific revision (branch, tag, or commit)
            repo_type: Type of repository (not used in this implementation)
            token: Authentication token (uses instance token if not provided)

        Returns:
            Dictionary with file metadata
        """
        if token and token != self.token:
            # Create a temporary client with the new token
            temp_client = GiteaHubClient(self.gitea_url, token=token)
            return temp_client.get_hf_file_metadata(
                repo_id=repo_id,
                filename=filename,
                revision=revision,
                repo_type=repo_type,
                token=None,  # Already used in the temp client
            )

        owner, name = repo_id.split('/', 1)

        if filename.startswith('/'):
            filename = filename[1:]

        endpoint = f"/repos/{owner}/{name}/contents/{filename}"
        if revision:
            endpoint = f"{endpoint}?ref={revision}"

        response = self._make_request("GET", endpoint)
        file_info = response.json()

        # Construct a metadata object similar to huggingface_hub's
        metadata = {
            "commit_id": file_info.get("sha", ""),
            "sha": file_info.get("sha", ""),
            "size": file_info.get("size", 0),
            "etag": file_info.get("sha", ""),  # Use SHA as etag
            "location": file_info.get("download_url", ""),
            "last_modified": file_info.get("last_commit_date", ""),
        }

        return metadata

    def get_model_tags(self, repo_id: str) -> List[str]:
        """
        Get the tags (topics) for a model repository.

        Args:
            repo_id: ID of the repository

        Returns:
            List of tags
        """
        repo_info = self.get_repo_info(repo_id)
        return repo_info.get("topics", [])

    def model_info(self, repo_id: str) -> Dict:
        """
        Get information about a model repository.

        Args:
            repo_id: ID of the repository

        Returns:
            Dictionary with model information
        """
        repo_info = self.get_repo_info(repo_id)

        # Transform to match huggingface_hub's format
        model_info = {
            "id": repo_id,
            "modelId": repo_id.split('/')[-1],
            "author": repo_info.get("owner", {}).get("login", ""),
            "lastModified": repo_info.get("updated_at", ""),
            "tags": repo_info.get("topics", []),
            "private": repo_info.get("private", False),
            "downloads": repo_info.get("watchers_count", 0),  # Use watches as proxy for downloads
            "likes": repo_info.get("stars_count", 0),
        }

        return model_info

    def list_models(
        self,
        filter: Optional[str] = None,
        author: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict]:
        """
        List models available on the Gitea server.

        Args:
            filter: Filter string (not implemented)
            author: Filter by author
            search: Search query
            limit: Maximum number of models to return

        Returns:
            List of model information dictionaries
        """
        # Get repositories
        if author:
            # Get user's repositories
            response = self._make_request("GET", f"/users/{author}/repos?limit={limit}")
        else:
            # Get all repositories
            response = self._make_request("GET", f"/repos/search?limit={limit}")

        repos = response.json()

        if isinstance(repos, dict) and "data" in repos:
            repos = repos["data"]

        # Filter to only include model repositories
        models = []
        for repo in repos:
            topics = repo.get("topics", [])
            if "model" in topics:
                # Transform to match huggingface_hub's format
                owner = repo.get("owner", {}).get("login", "")
                model_info = {
                    "id": f"{owner}/{repo.get('name')}",
                    "modelId": repo.get("name"),
                    "author": owner,
                    "lastModified": repo.get("updated_at", ""),
                    "tags": topics,
                    "private": repo.get("private", False),
                    "downloads": repo.get("watchers_count", 0),
                    "likes": repo.get("stars_count", 0),
                }
                models.append(model_info)

        # Apply search filter if provided
        if search:
            search = search.lower()
            models = [m for m in models if search in m["id"].lower() or search in str(m["tags"]).lower()]

        return models[:limit]

    # Dataset-specific methods

    def list_datasets(
        self,
        filter: Optional[str] = None,
        author: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict]:
        """
        List datasets available on the Gitea server.

        Args:
            filter: Filter string (not implemented)
            author: Filter by author
            search: Search query
            limit: Maximum number of datasets to return

        Returns:
            List of dataset information dictionaries
        """
        # Get repositories
        if author:
            # Get user's repositories
            response = self._make_request("GET", f"/users/{author}/repos?limit={limit}")
        else:
            # Get all repositories
            response = self._make_request("GET", f"/repos/search?limit={limit}")

        repos = response.json()

        if isinstance(repos, dict) and "data" in repos:
            repos = repos["data"]

        # Filter to only include dataset repositories
        datasets = []
        for repo in repos:
            topics = repo.get("topics", [])
            if "dataset" in topics:
                # Transform to match huggingface_hub's format
                owner = repo.get("owner", {}).get("login", "")
                dataset_info = {
                    "id": f"{owner}/{repo.get('name')}",
                    "datasetId": repo.get("name"),
                    "author": owner,
                    "lastModified": repo.get("updated_at", ""),
                    "tags": topics,
                    "private": repo.get("private", False),
                    "downloads": repo.get("watchers_count", 0),
                    "likes": repo.get("stars_count", 0),
                }
                datasets.append(dataset_info)

        # Apply search filter if provided
        if search:
            search = search.lower()
            datasets = [d for d in datasets if search in d["id"].lower() or search in str(d["tags"]).lower()]

        return datasets[:limit]


# Create a hub client class that emulates the huggingface_hub API
class HfApi:
    """
    A class that emulates the huggingface_hub HfApi class using Gitea as a backend.
    """

    def __init__(self, endpoint: Optional[str] = None, token: Optional[str] = None):
        """
        Initialize the HfApi class.

        Args:
            endpoint: Base URL for the Gitea server
            token: Authentication token
        """
        self.endpoint = endpoint or os.environ.get("HF_ENDPOINT")
        self.token = token or os.environ.get("HF_TOKEN")

        if not self.endpoint:
            raise ValueError("No endpoint provided. Set the HF_ENDPOINT environment variable or pass endpoint to the constructor.")

        self.client = GiteaHubClient(self.endpoint, token=self.token)

    def create_repo(self, repo_id: str, repo_type: str = "model", private: bool = False) -> Dict:
        """
        Create a new repository.

        Args:
            repo_id: ID of the repository
            repo_type: Type of repository (model, dataset, or space)
            private: Whether the repository is private

        Returns:
            Dictionary with repository information
        """
        return self.client.create_repo(repo_id, private=private, repo_type=repo_type)

    def delete_repo(self, repo_id: str, repo_type: str = "model") -> bool:
        """
        Delete a repository.

        Args:
            repo_id: ID of the repository
            repo_type: Type of repository (not used in this implementation)

        Returns:
            True if successful
        """
        return self.client.delete_repo(repo_id)

    def upload_file(
        self,
        path_or_fileobj: Union[str, Path, BinaryIO],
        path_in_repo: str,
        repo_id: str,
        token: Optional[str] = None,
        repo_type: str = "model",
        revision: Optional[str] = None,
        commit_message: Optional[str] = None,
        commit_description: Optional[str] = None,
        create_pr: bool = False,
    ) -> Dict:
        """
        Upload a file to a repository.

        Args:
            path_or_fileobj: Path to a file or a file-like object
            path_in_repo: Path in the repository
            repo_id: ID of the repository
            token: Authentication token (uses instance token if not provided)
            repo_type: Type of repository (model, dataset, or space)
            revision: Specific revision (branch, tag, or commit)
            commit_message: Commit message
            commit_description: Extended commit description
            create_pr: Whether to create a pull request (not implemented)

        Returns:
            Dictionary with commit information
        """
        return self.client.upload_file_to_hub(
            path_or_fileobj=path_or_fileobj,
            path_in_repo=path_in_repo,
            repo_id=repo_id,
            token=token or self.token,
            repo_type=repo_type,
            revision=revision,
            commit_message=commit_message,
            commit_description=commit_description,
            create_pr=create_pr,
        )

    def upload_folder(
        self,
        folder_path: Union[str, Path],
        repo_id: str,
        path_in_repo: Optional[str] = None,
        token: Optional[str] = None,
        repo_type: str = "model",
        revision: Optional[str] = None,
        commit_message: Optional[str] = None,
        commit_description: Optional[str] = None,
        create_pr: bool = False,
        ignore_patterns: Optional[List[str]] = None,
    ) -> Dict:
        """
        Upload a folder to a repository.

        Args:
            folder_path: Path to the folder to upload
            repo_id: ID of the repository
            path_in_repo: Path in the repository
            token: Authentication token (uses instance token if not provided)
            repo_type: Type of repository (model, dataset, or space)
            revision: Specific revision (branch, tag, or commit)
            commit_message: Commit message
            commit_description: Extended commit description
            create_pr: Whether to create a pull request (not implemented)
            ignore_patterns: List of file patterns to ignore

        Returns:
            Dictionary with commit information
        """
        return self.client.upload_folder_to_hub(
            folder_path=folder_path,
            repo_id=repo_id,
            path_in_repo=path_in_repo,
            token=token or self.token,
            repo_type=repo_type,
            revision=revision,
            commit_message=commit_message,
            commit_description=commit_description,
            create_pr=create_pr,
            ignore_patterns=ignore_patterns,
        )

    def create_commit(
        self,
        repo_id: str,
        operations: List[Dict],
        commit_message: str,
        token: Optional[str] = None,
        repo_type: Optional[str] = None,
        revision: Optional[str] = None,
        commit_description: Optional[str] = None,
        parent_commit: Optional[str] = None,
    ) -> Dict:
        """
        Create a commit with multiple file operations.

        Args:
            repo_id: ID of the repository
            operations: List of operations to perform (add, delete, etc.)
            commit_message: Commit message
            token: Authentication token (uses instance token if not provided)
            repo_type: Type of repository (not used in this implementation)
            revision: Specific revision (branch, tag, or commit)
            commit_description: Extended commit description
            parent_commit: Parent commit SHA (not used in this implementation)

        Returns:
            Dictionary with commit information
        """
        client = self.client
        if token and token != self.token:
            client = GiteaHubClient(self.endpoint, token=token)

        return client.create_commit(
            repo_id=repo_id,
            operations=operations,
            commit_message=commit_message,
            branch=revision,
            commit_description=commit_description,
            parent_commit=parent_commit,
        )

    def model_info(self, repo_id: str, revision: Optional[str] = None, token: Optional[str] = None) -> Dict:
        """
        Get information about a model repository.

        Args:
            repo_id: ID of the repository
            revision: Specific revision (not used in this implementation)
            token: Authentication token (uses instance token if not provided)

        Returns:
            Dictionary with model information
        """
        client = self.client
        if token and token != self.token:
            client = GiteaHubClient(self.endpoint, token=token)

        return client.model_info(repo_id)

    def list_models(
        self,
        filter: Optional[str] = None,
        author: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 50,
        token: Optional[str] = None,
    ) -> List[Dict]:
        """
        List models available on the Gitea server.

        Args:
            filter: Filter string (not implemented)
            author: Filter by author
            search: Search query
            limit: Maximum number of models to return
            token: Authentication token (uses instance token if not provided)

        Returns:
            List of model information dictionaries
        """
        client = self.client
        if token and token != self.token:
            client = GiteaHubClient(self.endpoint, token=token)

        return client.list_models(
            filter=filter,
            author=author,
            search=search,
            limit=limit,
        )

    def list_datasets(
        self,
        filter: Optional[str] = None,
        author: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 50,
        token: Optional[str] = None,
    ) -> List[Dict]:
        """
        List datasets available on the Gitea server.

        Args:
            filter: Filter string (not implemented)
            author: Filter by author
            search: Search query
            limit: Maximum number of datasets to return
            token: Authentication token (uses instance token if not provided)

        Returns:
            List of dataset information dictionaries
        """
        client = self.client
        if token and token != self.token:
            client = GiteaHubClient(self.endpoint, token=token)

        return client.list_datasets(
            filter=filter,
            author=author,
            search=search,
            limit=limit,
        )


# Export compatible functions
def create_repo(
    repo_id: str,
    private: bool = False,
    token: Optional[str] = None,
    repo_type: str = "model",
    exist_ok: bool = False,
) -> Dict:
    """
    Create a new repository.

    Args:
        repo_id: ID of the repository
        private: Whether the repository is private
        token: Authentication token
        repo_type: Type of repository (model, dataset, or space)
        exist_ok: If True, don't error if repo already exists

    Returns:
        Dictionary with repository information
    """
    endpoint = os.environ.get("HF_ENDPOINT")
    if not endpoint:
        raise ValueError("No endpoint provided. Set the HF_ENDPOINT environment variable.")

    client = GiteaHubClient(endpoint, token=token or os.environ.get("HF_TOKEN"))
    return client.create_repo(repo_id, private=private, repo_type=repo_type, exist_ok=exist_ok)


def hf_hub_download(
    repo_id: str,
    filename: str,
    revision: Optional[str] = None,
    repo_type: Optional[str] = None,
    local_dir: Optional[Union[str, Path]] = None,
    local_dir_use_symlinks: bool = True,
    token: Optional[str] = None,
    library_name: Optional[str] = None,
    library_version: Optional[str] = None,
) -> str:
    """
    Download a file from a repository.

    Args:
        repo_id: ID of the repository
        filename: Name of the file to download
        revision: Specific revision (branch, tag, or commit)
        repo_type: Type of repository (not used in this implementation)
        local_dir: Directory to save the file to
        local_dir_use_symlinks: Whether to use symlinks (not used in this implementation)
        token: Authentication token
        library_name: Name of the library (not used in this implementation)
        library_version: Version of the library (not used in this implementation)

    Returns:
        Path to the downloaded file
    """
    endpoint = os.environ.get("HF_ENDPOINT")
    if not endpoint:
        raise ValueError("No endpoint provided. Set the HF_ENDPOINT environment variable.")

    client = GiteaHubClient(endpoint, token=token or os.environ.get("HF_TOKEN"))
    return client.download_file_from_hub(
        repo_id=repo_id,
        filename=filename,
        revision=revision,
        repo_type=repo_type,
        local_dir=local_dir,
        local_dir_use_symlinks=local_dir_use_symlinks,
        token=token,
        library_name=library_name,
        library_version=library_version,
    )


def snapshot_download(
    repo_id: str,
    revision: Optional[str] = None,
    repo_type: Optional[str] = None,
    local_dir: Optional[Union[str, Path]] = None,
    local_dir_use_symlinks: bool = True,
    token: Optional[str] = None,
    library_name: Optional[str] = None,
    library_version: Optional[str] = None,
    ignore_patterns: Optional[List[str]] = None,
) -> str:
    """
    Download the whole repository.

    Args:
        repo_id: ID of the repository
        revision: Specific revision (branch, tag, or commit)
        repo_type: Type of repository (not used in this implementation)
        local_dir: Directory to save the files to
        local_dir_use_symlinks: Whether to use symlinks (not used in this implementation)
        token: Authentication token
        library_name: Name of the library (not used in this implementation)
        library_version: Version of the library (not used in this implementation)
        ignore_patterns: List of file patterns to ignore

    Returns:
        Path to the downloaded repository
    """
    endpoint = os.environ.get("HF_ENDPOINT")
    if not endpoint:
        raise ValueError("No endpoint provided. Set the HF_ENDPOINT environment variable.")

    client = GiteaHubClient(endpoint, token=token or os.environ.get("HF_TOKEN"))

    # Create local_dir if it doesn't exist
    if not local_dir:
        local_dir = Path.cwd() / repo_id.split('/')[-1]
    else:
        local_dir = Path(local_dir)

    local_dir.mkdir(parents=True, exist_ok=True)

    # List all files in the repository
    owner, name = repo_id.split('/', 1)

    # We'll recursively list and download files
    def download_directory(path="", target_dir=None):
        if target_dir is None:
            target_dir = local_dir

        # List files in the directory
        try:
            files = client.list_files(repo_id, path=path, revision=revision)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                logger.warning(f"Directory {path} not found in repository {repo_id}")
                return
            raise

        for file_info in files:
            file_type = file_info.get("type")
            file_path = file_info.get("path", "")

            # Skip files that match ignore patterns
            if ignore_patterns:
                if any(pattern in file_path for pattern in ignore_patterns):
                    continue

            # Create the local directory structure
            rel_path = file_path[len(path):].lstrip("/")
            local_file_path = target_dir / rel_path

            if file_type == "dir":
                # Create directory and process its contents
                local_file_path.mkdir(parents=True, exist_ok=True)
                download_directory(file_path, target_dir)
            else:
                # Download the file
                client.download_file(
                    repo_id=repo_id,
                    repo_path=file_path,
                    local_path=local_file_path,
                    revision=revision
                )

    # Start the download process
    download_directory()

    return str(local_dir)
