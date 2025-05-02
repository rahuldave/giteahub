"""
Integration tests for the GiteaHubClient implementation.

These tests connect to a real Gitea server and perform actual operations.
They verify that our adapter works correctly with a real Gitea instance.

To run just the integration tests:
    uv run pytest tests/integration_test_*.py -v
"""

import os
import pytest
import tempfile
import uuid
import shutil
from pathlib import Path

from giteahub.gitea_huggingface_client import (
    GiteaHubClient,
    REPO_TYPE_REPO,
    REPO_TYPE_MODEL,
    REPO_TYPE_DATASET,
    REPO_TYPE_SPACE
)

# Mark all tests in this file as integration tests
pytestmark = pytest.mark.integration

# Import test utilities for consistent setup
from tests.test_utils import (
    GITEA_URL, 
    GITEA_TOKEN, 
    GITEA_USER, 
    get_random_name, 
    cleanup_repos
)


@pytest.fixture
def client():
    """Create a GiteaHubClient instance for testing."""
    # Set environment variables like the other test files do
    os.environ["HF_ENDPOINT"] = GITEA_URL
    os.environ["HF_TOKEN"] = GITEA_TOKEN
    
    # Create client with the same token used in other tests
    client = GiteaHubClient(GITEA_URL, token=GITEA_TOKEN)
    
    yield client
    
    # Clean up any repositories created during tests
    cleanup_repos(client.gitea, pattern="test-")


@pytest.fixture
def temp_repo(client):
    """Create a temporary repository for testing."""
    # Get current user
    user = client.get_current_user()
    
    # Create a unique repo name to avoid conflicts
    repo_name = f"test-repo-{uuid.uuid4().hex[:8]}"
    repo_id = f"{user.username}/{repo_name}"
    
    # Create the repo
    client.create_repo(repo_id, repo_type=REPO_TYPE_REPO)
    
    # Return the repo ID for use in tests
    yield repo_id
    
    # Clean up - delete the repo after tests
    try:
        client.delete_repo(repo_id)
    except Exception as e:
        print(f"Warning: Failed to delete test repo {repo_id}: {e}")


@pytest.fixture
def temp_file():
    """Create a temporary file for testing uploads."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp:
        tmp.write(b"Test content for file upload")
        tmp_path = tmp.name
    
    yield tmp_path
    
    # Clean up - delete the file after tests
    try:
        os.unlink(tmp_path)
    except Exception:
        pass


class TestGiteaHubClientIntegration:
    """Integration tests for GiteaHubClient."""
    
    def test_client_connection(self, client):
        """Test that the client can connect to the Gitea server."""
        user = client.get_current_user()
        assert user is not None
        assert user.username == GITEA_USER
    
    def test_create_and_get_repo(self, client):
        """Test creating and retrieving a repository."""
        # Get current user to create repo under their account
        user = client.get_current_user()
        
        # Create a unique repo name
        repo_name = f"test-create-{uuid.uuid4().hex[:8]}"
        repo_id = f"{user.username}/{repo_name}"
        
        try:
            # Create a repository
            result = client.create_repo(repo_id, repo_type=REPO_TYPE_MODEL)
            
            # Verify it was created correctly
            assert result["name"] == repo_name
            assert result["full_name"] == repo_id
            
            # Get repository info
            repo_info = client.get_repo_info(repo_id)
            assert repo_info["name"] == repo_name
            
            # Check for the Model topic - it might be lowercase in the existing implementation
            topic_found = False
            for topic in repo_info["topics"]:
                if topic.lower() == REPO_TYPE_MODEL.lower():
                    topic_found = True
                    break
            assert topic_found, f"Repository type {REPO_TYPE_MODEL} not found in topics: {repo_info['topics']}"
            
        finally:
            # Clean up - delete the repository
            try:
                client.delete_repo(repo_id)
            except Exception:
                pass
    
    def test_update_repo_topics(self, client, temp_repo):
        """Test updating repository topics."""
        # Add a new topic
        new_topic = f"test-topic-{uuid.uuid4().hex[:8]}"
        result = client.update_repo_topics(temp_repo, [new_topic])
        
        # Verify the topic was added
        assert new_topic in result["topics"]
        
        # Get the repo and verify the topic is there
        repo_info = client.get_repo_info(temp_repo)
        assert new_topic in repo_info["topics"]
    
    def test_upload_and_update_file(self, client, temp_repo, temp_file):
        """Test uploading and updating a file."""
        # Upload the file
        filename = os.path.basename(temp_file)
        result = client.upload_file(
            repo_id=temp_repo,
            local_path=temp_file,
            repo_path=filename,
            commit_message="Upload test file"
        )
        
        # Verify the upload was successful
        assert "commit" in result
        assert result["content"]["name"] == filename
        
        # Create a new file with updated content
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp:
            tmp.write(b"Updated content for file")
            updated_file_path = tmp.name
        
        try:
            # Update the file
            update_result = client.upload_file(
                repo_id=temp_repo,
                local_path=updated_file_path,
                repo_path=filename,
                commit_message="Update test file"
            )
            
            # Verify the update was successful
            assert "commit" in update_result
            assert update_result["content"]["name"] == filename
            
        finally:
            # Clean up the temporary update file
            try:
                os.unlink(updated_file_path)
            except Exception:
                pass
    
    def test_create_repo_with_different_types(self, client):
        """Test creating repositories with different repository types."""
        # Get current user
        user = client.get_current_user()
        
        # Create repos with different types
        repos = []
        
        try:
            # Create repos with each type
            for repo_type in [REPO_TYPE_REPO, REPO_TYPE_MODEL, REPO_TYPE_DATASET, REPO_TYPE_SPACE]:
                repo_name = f"test-{repo_type.lower()}-{uuid.uuid4().hex[:8]}"
                repo_id = f"{user.username}/{repo_name}"
                
                # Create the repo
                result = client.create_repo(repo_id, repo_type=repo_type)
                assert result["name"] == repo_name
                repos.append(repo_id)
                
                # Verify the topic was set
                repo_info = client.get_repo_info(repo_id)
                
                # Check for the topic - it might be lowercase in the existing implementation
                topic_found = False
                for topic in repo_info["topics"]:
                    if topic.lower() == repo_type.lower():
                        topic_found = True
                        break
                assert topic_found, f"Repository type {repo_type} not found in topics: {repo_info['topics']}"
                
        finally:
            # Clean up - delete all created repositories
            for repo_id in repos:
                try:
                    client.delete_repo(repo_id)
                except Exception:
                    pass
    
    def test_upload_to_nested_path(self, client, temp_repo, temp_file):
        """Test uploading a file to a nested path."""
        # Create a nested path
        nested_path = "nested/folder/structure"
        filename = os.path.basename(temp_file)
        repo_path = f"{nested_path}/{filename}"
        
        # Upload the file to the nested path
        result = client.upload_file(
            repo_id=temp_repo,
            local_path=temp_file,
            repo_path=repo_path,
            commit_message="Upload to nested path"
        )
        
        # Verify the upload was successful
        assert "commit" in result
        assert result["content"]["path"] == repo_path