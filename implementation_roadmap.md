# Hugging Face Hub to Gitea Adapter Implementation Roadmap

This document outlines our strategy for reimplementing the existing code using py-gitea and adding missing functionality to create a complete adapter between Hugging Face Hub and Gitea.

## Core Approach

1. Replace direct REST API calls with py-gitea's object-oriented API
2. Fix existing bugs and implementation issues
3. Add missing functionality required for complete compatibility

## Current Implementation Analysis

The current implementation has several issues:
- Uses direct REST API calls instead of leveraging py-gitea
- Duplicated code in several places (especially in file operations)
- Non-idiomatic error handling
- Missing functionality for key Hugging Face Hub features

## Implementation Mapping

### 1. Repository Management

| Hugging Face Hub Function | Current Implementation | py-gitea Implementation |
|---------------------------|------------------------|-------------------------|
| `create_repo()` | Direct REST API calls to create repo and set topics | Use `gitea.create_repo()` and `Repository.add_topic()` |
| `delete_repo()` | Direct REST API call to delete | Use `Repository.delete()` |
| `model_info()` | Custom response formatting from repo info | Use `Repository` object properties with mapping |
| `dataset_info()` | Custom response formatting from repo info | Use `Repository` object properties with mapping |
| `list_models()` | Manual filtering of all repos by topic | Use `gitea.repos.search()` with topic filter |
| `list_datasets()` | Manual filtering of all repos by topic | Use `gitea.repos.search()` with topic filter |

### 2. File Operations

| Hugging Face Hub Function | Current Implementation | py-gitea Implementation |
|---------------------------|------------------------|-------------------------|
| `upload_file()` | Multi-step REST API process | Use `Repository.create_file()` / `Repository.change_file()` |
| `upload_folder()` | Iterative file uploads | Use batch implementation with `Repository.create_file()` |
| `download_file()` | Direct REST API to get raw content | Use `Repository.get_file_content()` |
| `hf_hub_download()` | Wrapper around download_file | Reimplement using `Repository.get_file_content()` |
| `snapshot_download()` | Custom file traversal and download | Use `Repository.get_git_content()` recursively |
| `get_hf_file_metadata()` | Direct REST API call to get file info | Use `Repository.get_file_content()` metadata |

### 3. Git Operations

| Hugging Face Hub Function | Current Implementation | py-gitea Implementation |
|---------------------------|------------------------|-------------------------|
| `create_commit()` | Sequence of individual file operations | Batch with appropriate `Repository` methods |
| `create_branch()` | *Not implemented* | Implement using appropriate py-gitea methods |
| `create_tag()` | *Not implemented* | Implement using appropriate py-gitea methods |

### 4. Content and Repository Types

| Hugging Face Hub Function | Current Implementation | py-gitea Implementation |
|---------------------------|------------------------|-------------------------|
| Model repositories | Uses topics for identification | Continue using topics with improved consistency |
| Dataset repositories | Uses topics for identification | Continue using topics with improved consistency |
| Model versioning | *Not implemented* | Implement using branches and tags |

## Implementation Gaps and Challenges

### 1. Missing py-gitea Functionality

Some functions may require extending py-gitea or making direct API calls:

- **Branch Management**: Creating, listing, and managing branches
  - `create_branch()` - Create a new branch
  - `delete_branch()` - Delete a branch
  - `list_repo_refs()` - List all branches and tags

- **Tag Management**: Creating and managing tags
  - `create_tag()` - Create a new tag
  - `delete_tag()` - Delete a tag

- **Batch Operations**: Efficient handling of multiple file operations in a single commit
  - py-gitea doesn't support true multi-file commits in a single API call
  - Need to implement a sequential approach with individual file operations
  - Each operation will result in a separate Git commit on the server

- **LFS Support**: Large file handling
  - Support for Git LFS (Large File Storage)
  - Uploading and downloading large binary files
  - Tracking LFS objects

### 2. Hugging Face Hub Specific Features

These features have no direct Gitea equivalent and need custom implementation:

- **Repository Class**:
  - Local Git operations for cloning, committing, and pushing
  - Needs to match the huggingface_hub Repository class interface
  - Will require direct Git commands via subprocess

- **Repository Listing and Search**:
  - `list_models()` - List model repositories
  - `list_datasets()` - List dataset repositories
  - Filtering and searching repositories by topics

- **Model and Dataset Info**:
  - `model_info()` - Get detailed model information
  - `dataset_info()` - Get detailed dataset information
  - Formatting repository metadata to match Hugging Face Hub formats

- **Model Cards**: Standardized README format for models
  - Templates for model descriptions
  - Metadata formatting

- **Dataset Cards**: Standardized README format for datasets
  - Templates for dataset descriptions
  - Dataset statistics and examples

- **Dataset Preview**: Generating previews for dataset files
  - Handling tabular data formats (CSV, JSON, Parquet)
  - Metadata extraction for dataset files

- **Repository Typing**: Clear identification of repository types
  - Using topics to identify models, datasets, and spaces
  - Consistent type information across API responses

### 3. Authentication and Permission Mapping

- Map Hugging Face Hub permissions to Gitea permissions
- Implement token-based authentication consistent with Hugging Face Hub
- Handle OAuth authentication flows

## Implementation Priority

1. **Phase 1: Core Repository Operations** (Completed)
   - Implement GiteaHubClient using py-gitea objects
   - Create repositories with appropriate topics
   - Delete repositories
   - Get basic repository information
   - Properly handle authentication and user objects

2. **Phase 2: File Operations** (Completed)
   - Implement upload_file with proper base64 encoding
   - Implement upload_folder for directory structures
   - Implement hf_hub_download for single file downloads
   - Implement snapshot_download for repository downloads
   - Create HfApi compatibility layer

3. **Phase 3: Advanced Git Operations** (Current Phase)
   - Implement create_commit for multi-file operations
   - Add branch management (create_branch, delete_branch)
   - Add tag management (create_tag, delete_tag)
   - Implement repository listing and information methods
   - Create Repository class for local Git operations

4. **Phase 4: Dataset Integration and Advanced Features**
   - Update the datasets library integration
   - Add support for dataset-specific file formats
   - Implement model and dataset card support
   - Add advanced file operations
   - Implement LFS support for large files

5. **Future Extensions**
   - Add support for Spaces
   - Implement webhooks and notification features
   - Add advanced search capabilities
   - Support collaborative features (PRs, discussions)
   - Enhance security and permission mapping

## Testing Strategy

1. Unit tests for all reimplemented functions
2. Integration tests that verify compatibility with the Hugging Face Hub API
3. Comparison tests between original and new implementations to ensure compatibility