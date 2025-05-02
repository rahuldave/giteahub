"""
Gitea to Hugging Face Hub Adapter Library

This library provides an adapter to use Gitea as a backend for Hugging Face Hub functionality.
"""

import os
import json
import tempfile
import shutil
import logging
import base64
from pathlib import Path
from typing import Dict, List, Optional, Union, BinaryIO, Tuple, Any

# Import the py-gitea library
from gitea import Gitea, Repository, User, Organization

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Repository types
REPO_TYPE_REPO = "Repo"
REPO_TYPE_MODEL = "Model"
REPO_TYPE_DATASET = "Dataset"
REPO_TYPE_SPACE = "Space"

class GiteaHubClient:
    """
    Client for interacting with Gitea API in a way that's compatible with huggingface_hub.
    This implementation uses py-gitea library instead of direct REST API calls.
    """

    def __init__(
        self,
        gitea_url: str,
        token: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None
    ):
        """
        Initialize the Gitea Hub client using py-gitea.

        Args:
            gitea_url: Base URL for the Gitea server (e.g., "https://gitea.example.com")
            token: Personal access token for Gitea authentication
            username: Username for basic auth if token isn't provided
            password: Password for basic auth if token isn't provided
        """
        self.gitea_url = gitea_url.rstrip('/')
        self.token = token
        self.username = username
        self.password = password

        # Initialize the py-gitea client
        if token:
            self.gitea = Gitea(self.gitea_url, token=token)
        elif username and password:
            self.gitea = Gitea(self.gitea_url, auth=(username, password))
        else:
            self.gitea = Gitea(self.gitea_url)
            
        # Cache for current user and organizations
        self._current_user = None
        self._user_organizations = None
        
    def get_current_user(self) -> User:
        """
        Get the current authenticated user.
        
        Returns:
            User object for the authenticated user
        """
        if self._current_user is None:
            self._current_user = self.gitea.get_user()
        return self._current_user
        
    def create_repo(
        self,
        repo_id: str,
        private: bool = False,
        repo_type: str = REPO_TYPE_REPO,
        exist_ok: bool = False
    ) -> Dict:
        """
        Create a new repository using py-gitea.
        
        Repository types are distinguished by topics. The standard type is 'Repo',
        with specialized types 'Model', 'Dataset', and 'Space'.
        
        Args:
            repo_id: ID of the repository (e.g., "username/repo-name")
            private: Whether the repository is private
            repo_type: Type of repository (Repo, Model, Dataset, or Space)
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
            except Exception:
                # Repo doesn't exist, continue with creation
                pass
                
        # Determine if owner is a user or organization
        # Try to get the owner as an organization first
        try:
            owner_obj = self.gitea.get_organization(owner)
            logger.info(f"Creating repo under organization: {owner}")
        except Exception:
            # If not an organization, use the current user
            if self.username == owner or (self._current_user and self._current_user.username == owner):
                owner_obj = self.get_current_user()
                logger.info(f"Creating repo under current user: {owner}")
            else:
                # For other users, we would need appropriate permissions
                raise ValueError(f"Cannot create repository for user {owner} - insufficient permissions")
                
        # Create the repository using the appropriate owner object
        repo = owner_obj.create_repo(
            name,
            description=f"A {repo_type} repository",
            private=private,
            auto_init=True
        )
        
        # Add repo_type as a topic for later filtering
        repo.add_topic(repo_type)
        
        # Convert to a dictionary format
        return self._convert_repo_to_dict(repo)
        
    def get_repo_info(self, repo_id: str) -> Dict:
        """
        Get information about a repository using py-gitea.
        
        Args:
            repo_id: ID of the repository (e.g., "username/repo-name")
            
        Returns:
            Dictionary with repository information
        """
        owner, name = repo_id.split('/', 1)
        
        # Use Repository.request to get the repository
        # This is the recommended way to get a repository object in py-gitea
        repo = Repository.request(self.gitea, owner, name)
        
        # Convert to a dictionary format
        return self._convert_repo_to_dict(repo)
        
    def delete_repo(self, repo_id: str) -> bool:
        """
        Delete a repository using py-gitea.
        
        Args:
            repo_id: ID of the repository (e.g., "username/repo-name")
            
        Returns:
            True if successful
        """
        owner, name = repo_id.split('/', 1)
        
        # Use Repository.request to get the repository
        repo = Repository.request(self.gitea, owner, name)
        
        # Delete the repository
        repo.delete()
        
        return True

    def update_repo_topics(self, repo_id: str, topics: List[str]) -> Dict:
        """
        Update repository topics using py-gitea.
        
        Args:
            repo_id: ID of the repository
            topics: List of topics to assign to the repo
            
        Returns:
            Updated repository information
        """
        owner, name = repo_id.split('/', 1)
        
        # Get the repository object
        repo = Repository.request(self.gitea, owner, name)
        
        # Get existing topics
        existing_topics = getattr(repo, "topics", [])
        
        # Add new topics
        for topic in topics:
            if topic not in existing_topics:
                repo.add_topic(topic)
                
        # Refresh repository information
        updated_repo = Repository.request(self.gitea, owner, name)
        
        # Return updated repository info
        return self._convert_repo_to_dict(updated_repo)
        
    def upload_file(
        self,
        repo_id: str,
        local_path: Union[str, Path],
        repo_path: Optional[str] = None,
        commit_message: Optional[str] = None,
        branch: str = "main"
    ) -> Dict:
        """
        Upload a file to a repository using py-gitea.
        
        This implementation uses proper base64 encoding as required by the Gitea API.
        
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
            
        # Get repository object
        repo = Repository.request(self.gitea, owner, name)
        
        # Read and encode file content
        with open(local_path, 'rb') as f:
            content = f.read()
            encoded_content = base64.b64encode(content).decode('utf-8')
            
        # Check if file exists
        try:
            # First, get the directory listing
            dir_path = str(Path(repo_path).parent)
            if dir_path == '.':
                dir_path = ''
                
            tree = repo.get_git_content(branch, dir_path)
            
            # Look for the file in the directory
            file_name = Path(repo_path).name
            file_obj = None
            for item in tree:
                if item.path.endswith(file_name):
                    file_obj = item
                    break
                    
            if file_obj:
                # File exists, update it
                result = repo.change_file(
                    path=repo_path,
                    content=encoded_content,
                    message=commit_message,
                    branch=branch,
                    sha=file_obj.sha
                )
            else:
                # File doesn't exist, create it
                result = repo.create_file(
                    path=repo_path,
                    content=encoded_content,
                    message=commit_message,
                    branch=branch
                )
        except Exception as e:
            # If any error occurs (like directory doesn't exist), try to create the file
            logger.info(f"Error checking for existing file, trying to create: {e}")
            result = repo.create_file(
                path=repo_path,
                content=encoded_content,
                message=commit_message,
                branch=branch
            )
            
        # Convert result to standard format
        return {
            "commit": {
                "sha": getattr(result, "sha", ""),
                "message": commit_message
            },
            "content": {
                "path": repo_path,
                "name": Path(repo_path).name
            }
        }
        
    def _convert_repo_to_dict(self, repo) -> Dict:
        """
        Convert a py-gitea Repository object to a dictionary format.
        
        Args:
            repo: py-gitea Repository object
            
        Returns:
            Dictionary with repository information
        """
        # Create a dictionary with repository information
        # The format matches what was returned by the original REST API implementation
        return {
            "id": repo.id,
            "name": repo.name,
            "full_name": repo.full_name,
            "owner": {
                "login": repo.owner.login
            },
            "description": repo.description,
            "private": repo.private,
            "topics": getattr(repo, "topics", []),
            "updated_at": getattr(repo, "updated_at", ""),
            "stars_count": getattr(repo, "stars_count", 0),
            "watchers_count": getattr(repo, "watchers_count", 0)
        }

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

    def create_repo(self, repo_id: str, repo_type: str = REPO_TYPE_MODEL, private: bool = False) -> Dict:
        """
        Create a new repository.

        Args:
            repo_id: ID of the repository
            repo_type: Type of repository (Model, Dataset, or Space)
            private: Whether the repository is private

        Returns:
            Dictionary with repository information
        """
        return self.client.create_repo(repo_id, private=private, repo_type=repo_type)

    def delete_repo(self, repo_id: str, repo_type: str = REPO_TYPE_MODEL) -> bool:
        """
        Delete a repository.

        Args:
            repo_id: ID of the repository
            repo_type: Type of repository (not used in this implementation)

        Returns:
            True if successful
        """
        return self.client.delete_repo(repo_id)

# Export compatible functions
def create_repo(
    repo_id: str,
    private: bool = False,
    token: Optional[str] = None,
    repo_type: str = REPO_TYPE_MODEL,
    exist_ok: bool = False,
) -> Dict:
    """
    Create a new repository.

    Args:
        repo_id: ID of the repository
        private: Whether the repository is private
        token: Authentication token
        repo_type: Type of repository (Model, Dataset, or Space)
        exist_ok: If True, don't error if repo already exists

    Returns:
        Dictionary with repository information
    """
    endpoint = os.environ.get("HF_ENDPOINT")
    if not endpoint:
        raise ValueError("No endpoint provided. Set the HF_ENDPOINT environment variable.")

    client = GiteaHubClient(endpoint, token=token or os.environ.get("HF_TOKEN"))
    return client.create_repo(repo_id, private=private, repo_type=repo_type, exist_ok=exist_ok)