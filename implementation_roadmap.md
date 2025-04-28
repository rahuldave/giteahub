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
- **Tag Management**: Creating and managing tags
- **Batch Operations**: Efficient handling of multiple file operations in a single commit
- **LFS Support**: Large file handling (to be implemented later)

### 2. Hugging Face Hub Specific Features

These features have no direct Gitea equivalent and need custom implementation:

- **Model Cards**: Standardized README format for models
- **Dataset Cards**: Standardized README format for datasets
- **Dataset Preview**: Generating previews for dataset files
- **Repository Typing**: Clear identification of repository types (model/dataset)

### 3. Authentication and Permission Mapping

- Map Hugging Face Hub permissions to Gitea permissions
- Implement token-based authentication consistent with Hugging Face Hub

## Implementation Priority

1. **Core Repository Operations**
   - Fix and reimplement basic repository CRUD operations with py-gitea

2. **File Operations**
   - Reimplement file upload/download operations with proper error handling
   - Implement efficient file batch operations

3. **Git Operations**
   - Implement commit, branch, and tag functionality
   - Ensure proper handling of repository history

4. **Dataset Integration**
   - Update the datasets integration to use new implementation

5. **Extended Features**
   - Add missing functionality from Hugging Face Hub API

## Testing Strategy

1. Unit tests for all reimplemented functions
2. Integration tests that verify compatibility with the Hugging Face Hub API
3. Comparison tests between original and new implementations to ensure compatibility