# Implement GiteaHubClient using py-gitea - Issue #1

**Issue URL**: https://github.com/rahuldave/giteahub/issues/1

## Issue Description

Create a new implementation of GiteaHubClient that uses py-gitea library objects instead of direct REST API calls. Implement repository operations with proper type naming conventions: 'Repo' as the standard type, with 'Model', 'Dataset', and 'Space' as specific repository types.

**Tasks:**
- Reimplement the GiteaHubClient class to use py-gitea objects instead of direct REST API calls
- Implement repository creation with proper topic support for models/datasets/spaces
- Ensure repository objects are properly obtained through appropriate channels 
- Add base64 encoding/decoding for file operations
- Follow implementation plan phase 1 (Core Client Implementation)

**Implementation Notes:**
- Repository operations must use proper Repository objects retrieved through `Repository.request()`
- Repositories must be created using the User/Organization object's `create_repo` method
- Topics will be the mechanism for distinguishing repository types
- Support base64 encoding for file content

## Work Completed

- Implemented `GiteaHubClient` class using py-gitea objects
- Fixed parameter names for py-gitea API to use camelCase (e.g., repoName, autoInit)
- Implemented repository creation with proper topic support
- Ensured repository objects are obtained through `Repository.request()`
- Added unit tests for the GiteaHubClient class
- Added integration tests for repository operations
- Properly separated integration and unit tests with markers
- Fixed naming conventions for test files