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

3. **Carefully implement base functionality** before adding complex features
   - Get core repository and file operations working first
   - Add advanced operations like multi-file commits and LFS later

## Workflow and Development Process

1. **Issue-Driven Development**
   - Create an issue for each implementation task
   - Work on the implementation and associated test together
   - Use either test-driven (test → implementation) or implementation-driven (implementation → test) approach based on complexity
   - Close the issue once the implementation is complete and tested

2. **GitHub Operations**
   - Use `gh` CLI tool for GitHub operations (creating repos, issues, etc.)
   - Commit directly to the main branch without pull requests for now
   - Follow standard git workflow: create, add, commit, push

3. **Repository Management**
   - Host the repository at `rahuldave/giteahub` on GitHub
   - Maintain a clean commit history with meaningful commit messages
   - Use conventional git operations for all changes

## Next Session Focus

For our next session, we should focus on implementing the initial `HfApi` class and core repository operations using py-gitea. This includes:

1. Creating a proper `GiteaHubClient` class using py-gitea objects
2. Implementing repository creation with topic support for models/datasets/spaces
3. Adding file upload operations with proper base64 encoding
4. Building initial download functionality