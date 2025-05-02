# Gitea Hub Project: Progress and Next Steps

## What We've Learned

### py-gitea Library Usage

- Successfully established that py-gitea can be used to interact with a Gitea server, but it requires careful attention to parameter signatures and object types.
- Discovered that repository operations must use specific Repository objects retrieved through proper channels (like `Repository.request()`) rather than created manually.
- Learned that file content must be base64 encoded when creating or updating files, and all file operations follow a specific pattern:
  1. Get file listing with `get_git_content()`
  2. Find the specific file object in the listing
  3. Access content with `get_file_content(file_obj)`
  4. Files must be retrieved and content decoded from base64

### Repository Management

- Repositories can be created using the User or Organization object's `create_repo` method, not the Gitea object's method (which is admin-only).
- Topics can be added to repositories, which will be our mechanism for distinguishing models, datasets, and spaces.
- Repository objects must be properly obtained using `Repository.request(gitea, owner, name)` for operations like adding topics or managing files.

### py-gitea API Structure and Usage

#### Authentication and Initialization

- The Gitea client is initialized with: `Gitea(gitea_url, token)` where token is passed as a positional argument, not a keyword.
- Basic auth can be used with: `Gitea(gitea_url, auth=(username, password))`
- Getting the authenticated user: `user = gitea.get_user()`

#### Repository Operations

- **Creating a repository**:
  - The `Gitea.create_repo()` method is admin-only and should not be used for regular operations
  - For user repositories: `user.create_repo(repoName=name, description="desc", autoInit=True)`
  - For organization repositories: `org.create_repo(repoName=name, description="desc", autoInit=True)`
  - Parameter names are camelCase (e.g., `repoName`, `autoInit`)
  - Key parameters:
    - `repoName` (str): Repository name
    - `description` (str, optional): Repository description
    - `private` (bool, default=False): Whether the repository is private
    - `autoInit` (default=True): Whether to initialize with README
    - `default_branch` (str, default="master"): Default branch name

- **Accessing repositories**:
  - Use `Repository.request(gitea, owner, name)` to get a repository object
  - Do not attempt to create Repository objects directly

- **Repository topics**:
  - Add a topic: `repo.add_topic("topic-name")`
  - Get topics: `topics = repo.get_topics()`

#### User and Organization Management

- **Getting a user**:
  - Get the current user: `gitea.get_user()`
  - Get a specific user: `User.request(gitea, username)`

- **Working with organizations**:
  - Get an organization: `Organization.request(gitea, org_name)`
  - Organization operations may fail with 404 if the org doesn't exist

#### File Operations

- **Getting repository contents**:
  ```python
  # Get all files at the root level
  files = repo.get_git_content()
  
  # Important: get_git_content does NOT accept a path parameter in the current version
  # Files must be retrieved from the result using filtering
  root_files = repo.get_git_content()
  file_obj = [f for f in root_files if f.name == "filename.txt"][0]
  ```

- **Creating a file**:
  ```python
  # Base64 encode content
  base64_content = base64.b64encode(content.encode()).decode()
  
  # Create the file (positional filename, keyword content)
  repo.create_file(
      "path/to/file.txt",  # Path as first positional argument
      content=base64_content  # Base64 encoded content as keyword argument
  )
  ```

- **Updating a file**:
  ```python
  # Get file SHA first
  files = repo.get_git_content()
  file_obj = [f for f in files if f.name == "file.txt"][0]
  file_sha = file_obj.sha
  
  # Update with new content (positional filename, positional SHA, keyword content)
  base64_content = base64.b64encode(new_content.encode()).decode()
  repo.change_file(
      "path/to/file.txt",  # Path as first positional argument
      file_sha,            # SHA as second positional argument
      content=base64_content  # Base64 encoded content as keyword argument
  )
  ```

- **Reading a file**:
  ```python
  # Get directory listing first
  files = repo.get_git_content()
  file_obj = [f for f in files if f.name == "file.txt"][0]
  
  # Get content (returns base64 encoded)
  content_b64 = repo.get_file_content(file_obj)
  
  # Decode content
  content = base64.b64decode(content_b64).decode()
  ```

- **Deleting a file**:
  ```python
  # Get file SHA first
  files = repo.get_git_content()
  file_obj = [f for f in files if f.name == "file.txt"][0]
  file_sha = file_obj.sha
  
  # Delete the file (positional filename, positional SHA)
  repo.delete_file(
      "path/to/file.txt",  # Path as first positional argument
      file_sha             # SHA as second positional argument
  )
  ```

**Important Notes on File Operations**:
1. Parameter order matters - the filename/path is always the first positional argument
2. You cannot directly access nested paths with get_git_content - you must first retrieve root files
3. All content must be base64 encoded before creating or updating files
4. All file operations require explicitly handling the file SHA when updating or deleting

#### Error Handling

- Organization.request will raise a NotFoundException (404) if the org doesn't exist
- Repository operations may fail if permissions are insufficient
- File operations require careful handling of SHAs and paths

### File Operations

- File operations require using the correct sequence:
  - Creating files: base64 encode content, use `create_file(path, content=encoded_content)`
  - Updating files: get SHA from file object, base64 encode new content, use `change_file(path, sha, content=encoded_content)`
  - Deleting files: get SHA from file object, use `delete_file(path, sha)`
  - Reading files: get file object, use `get_file_content(file_obj)`, decode from base64

## Implementation Roadmap

1. **Core Repository API** (first implementation phase)
   - `create_repo` - Create repositories with appropriate topics for models/datasets/spaces
   - `delete_repo` - Delete repositories
   - `model_info`, `dataset_info` - Get information for models/datasets
   - `list_models`, `list_datasets` - List available models/datasets

2. **File Management API** (second implementation phase)
   - `upload_file` - Upload a single file (with base64 encoding)
   - `upload_folder` - Upload a directory structure
   - `hf_hub_download` - Download a single file
   - `snapshot_download` - Download an entire repository

3. **Advanced Git Operations** (third implementation phase)
   - `create_commit` - Perform multiple file operations in a single commit
   - Branch management
   - Tag management

4. **Dataset Integration** (final phase)
   - Patch the datasets library to use our Gitea implementation
   - Handle special dataset formats

## Created Implementation Documents

1. **Implementation Roadmap** (`implementation_roadmap.md`)
   - Detailed mapping between Hugging Face Hub functions and their py-gitea equivalents
   - Analysis of gaps and challenges in our implementation approach
   - Categorized implementation areas: Repository Management, File Operations, Git Operations, etc.

2. **Implementation Plan** (`implementation_plan.md`)
   - Step-by-step approach for implementation phases
   - Code examples for key components
   - Testing approach and timeline

## Development Guidelines

1. **Always add clear explanations (2-3 lines)** for:
   - Why we're making specific implementation choices
   - How we're adapting py-gitea methods to match HF Hub functionality
   - How our approach handles differences between Gitea and HF Hub APIs

2. **Always test thoroughly** before proceeding to new implementations
   - Unit tests for individual functions
   - Integration tests for combined operations
   - Verify Hugging Face Hub compatibility
   - Always run tests using `uv run pytest ...` (never use plain `pytest`)
   - Run both unit tests and integration tests before moving to new tasks
     - Unit tests: `uv run pytest tests/test_*.py -v`
     - Integration tests: `uv run pytest tests/integration_test_*.py -v`
     - All tests: `uv run pytest -v`

3. **Carefully implement base functionality** before adding complex features
   - Get core repository and file operations working first
   - Add advanced operations like multi-file commits and LFS later

4. **Follow a strict development workflow for each method**
   - For every new method or function:
     1. Write unit tests first (test-driven development)
     2. Implement the method with just enough code to pass the tests
     3. Create or update integration tests if needed
     4. Run both unit and integration tests to verify everything works
     5. Only then proceed to the next method
   - Resist the temptation to implement multiple methods at once
   - Keep changes small and focused to make debugging easier

## Workflow and Development Process

1. **Issue-Driven Development**
   - Create an issue for each implementation task
   - Work on the implementation and associated test together
   - Use test-driven development (test → implementation) for all features
   - Document issue details and completed work in the `issues/` folder
   - Use a consistent filename format: `issues/issue_N_descriptive_name.md`
   - Close the issue once the implementation is complete and tested
   - Maintain a clear history of completed work for each issue

2. **GitHub Operations**
   - Use `gh` CLI tool for GitHub operations (creating repos, issues, etc.)
   - Commit directly to the main branch without pull requests for now
   - Follow standard git workflow: create, add, commit, push

3. **Repository Management**
   - Host the repository at `rahuldave/giteahub` on GitHub
   - Maintain a clean commit history with meaningful commit messages
   - Use conventional git operations for all changes

## External Documentation

1. **py-gitea Documentation**
   - GitHub Repository: [https://github.com/Langenfeld/py-gitea/](https://github.com/Langenfeld/py-gitea/)
   - Test Examples: [https://github.com/Langenfeld/py-gitea/blob/master/tests/test_api.py](https://github.com/Langenfeld/py-gitea/blob/master/tests/test_api.py)
   - These resources provide examples of py-gitea usage and API patterns

2. **Hugging Face Hub Documentation**
   - Main Documentation: [https://huggingface.co/docs/huggingface_hub/index](https://huggingface.co/docs/huggingface_hub/index)
   - API Reference: [https://huggingface.co/docs/huggingface_hub/package_reference/index](https://huggingface.co/docs/huggingface_hub/package_reference/index)
   - LLM-friendly Documentation: [https://huggingface-projects-docs-llms-txt.hf.space/hub/llms.txt](https://huggingface-projects-docs-llms-txt.hf.space/hub/llms.txt)
   - These resources provide information about the original API we're adapting

## Development Progress and Future Feature Implementation

### Completed Features

We have successfully implemented the core functionality of the Gitea Hub adapter using py-gitea objects:

1. Created a proper `GiteaHubClient` class using py-gitea objects
2. Implemented repository creation with topic support for models/datasets/spaces
3. Added file upload/download operations with proper base64 encoding
4. Implemented folder upload and repository snapshot download

### Feature Development Workflow

For future feature development, we will follow this workflow:

1. **Issue-Driven Development**
   - Create a GitHub issue for each new feature or phase
   - Clearly describe the tasks and requirements in the issue
   - Implement according to our test-driven development guidelines
   - Close the issue when the feature is complete
   - Keep documentation of issue progress in the `issues/` directory
   - Name files descriptively: `issues/issue_N_feature_name.md`

2. **Immediate Next Steps**
   - Implement `create_commit` method for multi-file operations (Advanced Git Operations phase)
   - Add branch and tag management capabilities
   - Begin dataset integration work

3. **Documentation**
   - Maintain up-to-date implementation status
   - Document lessons learned and technical challenges in this file
   - Add detailed implementation notes to help future development