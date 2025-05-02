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

### 3.1 Implement Multi-file Commit Operations

Implement efficient multi-file commit operations, supporting different operation types in a single commit:

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
    """
    Create a commit with multiple file operations in a single transaction.
    
    Args:
        repo_id: Repository identifier in the format "owner/repo-name"
        operations: List of operation dictionaries, each containing:
            - type: Operation type ("add", "delete", "update")
            - path: Path to the file in the repository
            - content: File content (for "add" and "update" operations)
        commit_message: Message for the commit
        branch: Branch to commit to (defaults to "main")
        commit_description: Optional extended description for the commit
        parent_commit: Optional parent commit SHA

    Returns:
        Dict with commit information
    """
    # Implementation using py-gitea with proper base64 encoding
```

This implementation should:
1. Support "add", "update", and "delete" operations
2. Handle base64 encoding for file content
3. Process operations sequentially, as py-gitea does not have a native batch commit method
4. Properly retrieve file SHAs for update and delete operations
5. Return commit information in a format compatible with Hugging Face Hub

### 3.2 Implement Branch Management

Add branch creation and deletion capabilities:

```python
def create_branch(
    self,
    repo_id: str,
    branch: str,
    from_branch: Optional[str] = None
) -> Dict:
    """
    Create a new branch in a repository.
    
    Args:
        repo_id: Repository identifier
        branch: Name of the new branch
        from_branch: Source branch (defaults to the default branch)
        
    Returns:
        Dict with branch information
    """
    # Implementation using py-gitea
```

```python
def delete_branch(
    self,
    repo_id: str,
    branch: str
) -> None:
    """
    Delete a branch from a repository.
    
    Args:
        repo_id: Repository identifier
        branch: Name of the branch to delete
    """
    # Implementation using py-gitea
```

### 3.3 Implement Tag Management

Add tag creation and deletion capabilities:

```python
def create_tag(
    self,
    repo_id: str,
    tag: str,
    message: Optional[str] = None,
    from_revision: Optional[str] = None
) -> Dict:
    """
    Create a new tag in a repository.
    
    Args:
        repo_id: Repository identifier
        tag: Name of the new tag
        message: Optional tag message
        from_revision: Source revision (commit, branch, etc.)
        
    Returns:
        Dict with tag information
    """
    # Implementation using py-gitea
```

```python
def delete_tag(
    self,
    repo_id: str,
    tag: str
) -> None:
    """
    Delete a tag from a repository.
    
    Args:
        repo_id: Repository identifier
        tag: Name of the tag to delete
    """
    # Implementation using py-gitea
```

### 3.4 Implement Repository List and Info Methods

Add methods to list and get information about repositories:

```python
def list_models(
    self,
    search: Optional[str] = None,
    owner: Optional[str] = None,
    limit: Optional[int] = None
) -> List[Dict]:
    """
    List model repositories.
    
    Args:
        search: Optional search query
        owner: Optional owner filter
        limit: Optional limit on results
        
    Returns:
        List of model repository information
    """
    # Implementation using py-gitea with topic filtering
```

```python
def model_info(
    self,
    repo_id: str
) -> Dict:
    """
    Get detailed information about a model repository.
    
    Args:
        repo_id: Repository identifier
        
    Returns:
        Dict with model information
    """
    # Implementation using py-gitea with Repository properties
```

Similar methods for datasets: `list_datasets()` and `dataset_info()`

### 3.5 Implement Repository Class

Create a `Repository` wrapper class that's compatible with huggingface_hub's Repository for local Git operations:

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
        """
        Initialize a Repository instance.
        
        Args:
            local_dir: Local directory path
            clone_from: Optional repository to clone from
            repo_type: Type of repository (model, dataset, space)
            token: Authentication token
            git_user: Git username for commits
            git_email: Git email for commits
            revision: Git revision to clone
            huggingface_token: Token for Hugging Face Hub
        """
        # Implementation
```

Key methods to implement:
- `clone_from()` - Clone a remote repository
- `git_config_username_and_email()` - Configure Git user
- `git_head_hash()` - Get the current HEAD commit hash
- `git_remote_url()` - Get the remote URL
- `list_deleted_files()` - List files deleted in the working directory
- `push_to_hub()` - Push changes to the remote repository

## Phase 4: Dataset Integration and Advanced Features

### 4.1 Dataset Library Integration

Update the dataset integration module to use our new implementation:

```python
def patch_datasets_library():
    """
    Patch the datasets library to use our Gitea adapter.
    """
    # Implementation to intercept and redirect huggingface_hub calls
```

This should include:
1. Patching the datasets library to use our adapter
2. Supporting dataset-specific file formats
3. Handling dataset card generation and parsing

### 4.2 Advanced File Operations

Add support for advanced file operations:

```python
def get_hf_file_metadata(
    self,
    repo_id: str,
    filename: str,
    revision: Optional[str] = None
) -> Dict:
    """
    Get metadata for a file in a repository.
    
    Args:
        repo_id: Repository identifier
        filename: Path to the file
        revision: Optional git revision
        
    Returns:
        Dict with file metadata
    """
    # Implementation using py-gitea
```

```python
def file_exists(
    self,
    repo_id: str,
    filename: str,
    revision: Optional[str] = None
) -> bool:
    """
    Check if a file exists in a repository.
    
    Args:
        repo_id: Repository identifier
        filename: Path to the file
        revision: Optional git revision
        
    Returns:
        True if the file exists, False otherwise
    """
    # Implementation using py-gitea
```

### 4.3 LFS Support

Add support for Large File Storage (LFS):

```python
def preupload_lfs_files(
    self,
    repo_id: str,
    files: List[Union[str, Path]],
    token: Optional[str] = None
) -> None:
    """
    Prepare large files for upload using LFS.
    
    Args:
        repo_id: Repository identifier
        files: List of file paths
        token: Optional authentication token
    """
    # Implementation using py-gitea and LFS API
```

### 4.4 Model and Dataset Card Support

Add support for model and dataset cards:

```python
def generate_model_card(
    self,
    model_name: str,
    model_description: str,
    language: Optional[str] = None,
    license: Optional[str] = None,
    tags: Optional[List[str]] = None
) -> str:
    """
    Generate a model card markdown file.
    
    Args:
        model_name: Name of the model
        model_description: Description of the model
        language: Optional language of the model
        license: Optional license
        tags: Optional tags
        
    Returns:
        Markdown string for the model card
    """
    # Implementation
```

Similar method for dataset cards: `generate_dataset_card()`

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