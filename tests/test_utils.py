"""
Test utilities for Gitea Hub tests.
"""

import os
import random
import string
import uuid
from gitea import Gitea, User, Organization

# Constants for testing
GITEA_URL = "http://localhost:3000"
GITEA_TOKEN = "82f3959223e7a14111e7ee531cdca7c28e60062d"
GITEA_USER = "rahuldave"
GITEA_ORG = "rahuldaveorg"

def get_random_name(prefix="test-"):
    """Generate a random repository name for testing."""
    return f"{prefix}{uuid.uuid4().hex[:8]}"

def setup_test_env():
    """Set up the test environment."""
    os.environ["HF_ENDPOINT"] = GITEA_URL
    os.environ["HF_TOKEN"] = GITEA_TOKEN
    return Gitea(GITEA_URL, GITEA_TOKEN)

def cleanup_repos(gitea_client, pattern="test-"):
    """Clean up test repositories that match the pattern."""
    # Cleanup user repos
    try:
        # First get the user object since py-gitea works with objects, not string names
        # This returns the authenticated user based on the provided token
        user = gitea_client.get_user()
        
        # Looking at the code and tests, we need to use direct API endpoints
        # because the high-level methods have inconsistencies
        try:
            # Get list of repositories for the user
            repos_data = gitea_client.requests_get(f"/repos/search?uid={user.id}")
            
            # Extract repo data - repositories may be in data key if using search endpoint
            if isinstance(repos_data, dict) and "data" in repos_data:
                repos = repos_data["data"]
            else:
                repos = repos_data
                
            # Process repositories
            for repo_data in repos:
                try:
                    # Extract owner and repo name
                    if "full_name" in repo_data and "/" in repo_data["full_name"]:
                        owner_name, repo_name = repo_data["full_name"].split("/")
                        
                        # Check if this is a test repo by name pattern
                        if repo_name.startswith(pattern):
                            # Delete the repository directly using the API endpoint
                            # This is more reliable than creating a Repository object
                            # which can have inconsistent state management
                            try:
                                gitea_client.requests_delete(f"/repos/{owner_name}/{repo_name}")
                                print(f"Deleted user repository: {repo_name}")
                            except Exception as e:
                                print(f"Failed to delete repository {repo_name}: {e}")
                except Exception as e:
                    print(f"Failed to process repository data: {e}")
        except Exception as e:
            print(f"Error fetching user repositories: {e}")
            
    except Exception as e:
        print(f"Error during user repo cleanup: {e}")

    # Cleanup org repos - only if organization exists
    try:
        # Try to get the organization - will fail gracefully if it doesn't exist
        try:
            org_response = gitea_client.requests_get(f"/orgs/{GITEA_ORG}")
            
            if org_response:
                # Get all repositories and filter by organization
                try:
                    repos_data = gitea_client.requests_get(f"/repos/search?q=&sort=updated&order=desc")
                    
                    # Extract repo data
                    if isinstance(repos_data, dict) and "data" in repos_data:
                        repos = repos_data["data"]
                    else:
                        repos = repos_data
                        
                    # Process repositories - look for ones belonging to our org
                    for repo_data in repos:
                        try:
                            # Extract owner and repo name
                            if "full_name" in repo_data and "/" in repo_data["full_name"]:
                                owner_name, repo_name = repo_data["full_name"].split("/")
                                
                                # Check if this repo belongs to our org and matches the test pattern
                                if owner_name == GITEA_ORG and repo_name.startswith(pattern):
                                    # Delete repository directly
                                    try:
                                        gitea_client.requests_delete(f"/repos/{owner_name}/{repo_name}")
                                        print(f"Deleted organization repository: {repo_name}")
                                    except Exception as e:
                                        print(f"Failed to delete org repository {repo_name}: {e}")
                        except Exception as e:
                            print(f"Failed to process org repository data: {e}")
                except Exception as e:
                    print(f"Error searching repositories: {e}")
        except Exception:
            # Organization may not exist, which is okay - silently skip
            pass
    except Exception as e:
        print(f"Error during org repo cleanup: {e}")

def create_test_file(content="test content", ext=".txt"):
    """Create a temporary test file with the given content."""
    filename = f"temp_{uuid.uuid4().hex[:8]}{ext}"
    with open(filename, "w") as f:
        f.write(content)
    return filename

def create_test_dir(base_dir="test_dir", num_files=3):
    """Create a temporary test directory with some files."""
    dir_name = f"{base_dir}_{uuid.uuid4().hex[:8]}"
    os.makedirs(dir_name, exist_ok=True)
    
    files = []
    for i in range(num_files):
        file_path = os.path.join(dir_name, f"file_{i}.txt")
        with open(file_path, "w") as f:
            f.write(f"Content for file {i}")
        files.append(file_path)
    
    return dir_name, files

def cleanup_test_files(files):
    """Clean up temporary test files."""
    if isinstance(files, str):
        files = [files]
    
    for file in files:
        try:
            if os.path.isdir(file):
                import shutil
                shutil.rmtree(file)
            else:
                os.remove(file)
        except Exception as e:
            print(f"Failed to delete {file}: {e}")