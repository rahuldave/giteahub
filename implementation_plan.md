# Hugging Face Hub to Gitea Adapter Implementation Plan

This document outlines the step-by-step approach to reimplementing the Hugging Face Hub adapter using py-gitea.

## Phase 1: Core Client Implementation

### 1.1 Create Base Client Class

Replace the current `GiteaHubClient` with a py-gitea based implementation:

```python
from gitea import Gitea, Repository, User

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
        """Initialize the client with py-gitea."""
        self.gitea_url = gitea_url.rstrip('/')
        self.gitea = Gitea(gitea_url, token)
        self.token = token
        self.username = username
        self.password = password
```

### 1.2 Repository Management

Reimplement basic repository operations:

```python
def create_repo(self, repo_id: str, private: bool = False, repo_type: str = "model", exist_ok: bool = False) -> Dict:
    """
    Create a new repository using py-gitea.
    """
    if "/" not in repo_id:
        raise ValueError("repo_id must be in the format 'username/repo-name'")

    owner, name = repo_id.split('/', 1)
    
    # Check if repo exists if exist_ok is True
    if exist_ok:
        try:
            return self.get_repo_info(repo_id)
        except Exception:
            pass
    
    # Create repository using py-gitea
    repo = self.gitea.create_repo(
        repoOwner=owner,
        repoName=name,
        description=f"A {repo_type} repository",
        private=private,
        autoInit=True
    )
    
    # Add repo_type as a topic
    repo.add_topic(repo_type)
    
    # Convert to dict format compatible with huggingface_hub
    return self._convert_repo_to_dict(repo)
```

### 1.3 File Operations

Reimplement file operations using py-gitea:

```python
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
    repo = self.gitea.get_repo(owner, name)
    
    # Read file content
    with open(local_path, 'rb') as f:
        content = f.read()
    
    # Check if file exists
    try:
        existing_file = repo.get_file_content(repo_path, ref=branch)
        # Update file
        response = repo.change_file(
            path=repo_path,
            content=content,
            message=commit_message,
            branch=branch,
            sha=existing_file.sha
        )
    except Exception:
        # Create new file
        response = repo.create_file(
            path=repo_path,
            content=content,
            message=commit_message,
            branch=branch
        )
    
    return response
```

## Phase 2: Core API Compatibility Layer

### 2.1 Implement HfApi Class

Reimplement the `HfApi` class to use our new py-gitea client:

```python
class HfApi:
    """
    A class that emulates the huggingface_hub HfApi class using Gitea as a backend.
    """

    def __init__(self, endpoint: Optional[str] = None, token: Optional[str] = None):
        self.endpoint = endpoint or os.environ.get("HF_ENDPOINT")
        self.token = token or os.environ.get("HF_TOKEN")
        
        if not self.endpoint:
            raise ValueError("No endpoint provided. Set the HF_ENDPOINT environment variable or pass endpoint to the constructor.")
            
        self.client = GiteaHubClient(self.endpoint, token=self.token)
```

### 2.2 Implement Standalone Functions

Reimplement standalone functions:

```python
def create_repo(
    repo_id: str,
    private: bool = False,
    token: Optional[str] = None,
    repo_type: str = "model",
    exist_ok: bool = False,
) -> Dict:
    endpoint = os.environ.get("HF_ENDPOINT")
    if not endpoint:
        raise ValueError("No endpoint provided. Set the HF_ENDPOINT environment variable.")
        
    client = GiteaHubClient(endpoint, token=token or os.environ.get("HF_TOKEN"))
    return client.create_repo(repo_id, private=private, repo_type=repo_type, exist_ok=exist_ok)
```

## Phase 3: Advanced Features

### 3.1 Implement Repository Class

Create a `Repository` wrapper class that's compatible with huggingface_hub's Repository:

```python
class Repository:
    """
    A wrapper around a Gitea repository that's compatible with huggingface_hub.
    """
    
    def __init__(
        self,
        local_dir: Union[str, Path],
        clone_from: Optional[str] = None,
        repo_type: Optional[str] = None,
        token: Optional[str] = None,
        git_user: Optional[str] = None,
        git_email: Optional[str] = None,
        revision: Optional[str] = None,
        huggingface_token: Optional[str] = None,
    ):
        # Implementation
```

### 3.2 Implement Multi-file Commit Operations

Implement efficient multi-file commit operations:

```python
def create_commit(
    self,
    repo_id: str,
    operations: List[Dict],
    commit_message: str,
    branch: Optional[str] = None,
    commit_description: Optional[str] = None,
    parent_commit: Optional[str] = None
) -> Dict:
    # Implementation using py-gitea
```

## Phase 4: Dataset Integration

Update the dataset integration module to use our new implementation:

```python
def patch_datasets_library():
    """
    Patch the datasets library to use our Gitea adapter.
    """
    # Updated implementation
```

## Testing Plan

1. Unit tests for each reimplemented method
2. Integration tests against a real Gitea server
3. Compatibility tests with Hugging Face Hub API
4. Performance tests comparing old and new implementations

## Implementation Timeline

- **Week 1**: Core client implementation (Phase 1)
- **Week 2**: API compatibility layer (Phase 2)
- **Week 3**: Advanced features (Phase 3)
- **Week 4**: Dataset integration and testing (Phase 4)