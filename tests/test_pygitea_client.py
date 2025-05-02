"""
Tests for the py-gitea based GiteaHubClient implementation.
"""

import os
import base64
import pytest
from unittest.mock import patch, MagicMock, mock_open
import tempfile
from pathlib import Path

# Import the module we're testing
from giteahub.gitea_huggingface_client import (
    GiteaHubClient, 
    REPO_TYPE_REPO,
    REPO_TYPE_MODEL,
    REPO_TYPE_DATASET,
    REPO_TYPE_SPACE
)

# Mock the gitea library
@pytest.fixture
def mock_gitea():
    """Mock the gitea library components."""
    with patch('giteahub.gitea_huggingface_client.Gitea') as mock_gitea_cls, \
         patch('giteahub.gitea_huggingface_client.Repository') as mock_repo_cls, \
         patch('giteahub.gitea_huggingface_client.User') as mock_user_cls, \
         patch('giteahub.gitea_huggingface_client.Organization') as mock_org_cls:
        
        # Set up mock gitea instance
        mock_gitea_instance = mock_gitea_cls.return_value
        
        # Set up mock user
        mock_user = mock_user_cls.return_value
        mock_gitea_instance.get_user.return_value = mock_user
        
        # Set up mock repo
        mock_repo = mock_repo_cls.return_value
        mock_repo_cls.request.return_value = mock_repo
        
        yield {
            'gitea_cls': mock_gitea_cls,
            'gitea': mock_gitea_instance,
            'repo_cls': mock_repo_cls,
            'repo': mock_repo,
            'user_cls': mock_user_cls,
            'user': mock_user,
            'org_cls': mock_org_cls
        }

class TestGiteaHubClient:
    """Tests for the GiteaHubClient class."""
    
    def test_initialization(self, mock_gitea):
        """Test initialization of the client."""
        # Test with token
        client = GiteaHubClient("https://gitea.example.com", token="test_token")
        mock_gitea['gitea_cls'].assert_called_with("https://gitea.example.com", token="test_token")
        
        # Test with username/password
        client = GiteaHubClient("https://gitea.example.com", username="user", password="pass")
        mock_gitea['gitea_cls'].assert_called_with("https://gitea.example.com", auth=("user", "pass"))
        
        # Test without auth
        client = GiteaHubClient("https://gitea.example.com")
        mock_gitea['gitea_cls'].assert_called_with("https://gitea.example.com")
    
    def test_get_current_user(self, mock_gitea):
        """Test getting the current user."""
        client = GiteaHubClient("https://gitea.example.com", token="test_token")
        
        # Test caching behavior
        mock_gitea['gitea'].get_user.return_value = "test_user"
        
        # First call should use the API
        user = client.get_current_user()
        assert user == "test_user"
        mock_gitea['gitea'].get_user.assert_called_once()
        
        # Second call should use the cache
        mock_gitea['gitea'].get_user.reset_mock()
        user = client.get_current_user()
        assert user == "test_user"
        mock_gitea['gitea'].get_user.assert_not_called()
    
    def test_create_repo(self, mock_gitea):
        """Test repository creation."""
        client = GiteaHubClient("https://gitea.example.com", token="test_token", username="testuser")
        
        # Mock user and repo
        mock_user = mock_gitea['user']
        mock_user.username = "testuser"
        mock_repo = MagicMock()
        mock_repo.full_name = "testuser/test-repo"
        
        # Set up create_repo to return our mock repo
        mock_user.create_repo.return_value = mock_repo
        
        # Force the organization lookup to fail
        mock_gitea['gitea'].get_organization.side_effect = Exception("Not an organization")
        
        # Pre-set the current user (this matches what get_current_user would return)
        client._current_user = mock_user
        
        # Call the method
        result = client.create_repo("testuser/test-repo", repo_type=REPO_TYPE_MODEL)
        
        # Verify repo was created with correct parameters
        mock_user.create_repo.assert_called_with(
            "test-repo", 
            description=f"A {REPO_TYPE_MODEL} repository",
            private=False,
            auto_init=True
        )
        
        # Verify topics were added
        mock_repo.add_topic.assert_called_with(REPO_TYPE_MODEL)
        
    def test_create_repo_with_org(self, mock_gitea):
        """Test repository creation for an organization."""
        client = GiteaHubClient("https://gitea.example.com", token="test_token")
        
        # Mock org and repo
        mock_org = MagicMock()
        mock_org.username = "testorg"
        mock_repo = MagicMock()
        mock_repo.full_name = "testorg/test-repo"
        
        # Set up create_repo to return our mock repo
        mock_org.create_repo.return_value = mock_repo
        
        # Mock get_organization to return our mock org
        mock_gitea['gitea'].get_organization.return_value = mock_org
        
        # Call the method
        result = client.create_repo("testorg/test-repo", repo_type=REPO_TYPE_DATASET)
        
        # Verify org was retrieved
        mock_gitea['gitea'].get_organization.assert_called_with("testorg")
        
        # Verify repo was created with correct parameters
        mock_org.create_repo.assert_called_with(
            "test-repo", 
            description=f"A {REPO_TYPE_DATASET} repository",
            private=False,
            auto_init=True
        )
        
        # Verify topics were added
        mock_repo.add_topic.assert_called_with(REPO_TYPE_DATASET)
    
    def test_create_repo_exist_ok(self, mock_gitea):
        """Test repository creation with exist_ok=True."""
        client = GiteaHubClient("https://gitea.example.com", token="test_token")
        
        # Mock get_repo_info to return an existing repo
        client.get_repo_info = MagicMock(return_value={"full_name": "testuser/test-repo"})
        
        # Call the method with exist_ok=True
        result = client.create_repo("testuser/test-repo", exist_ok=True)
        
        # Verify get_repo_info was called
        client.get_repo_info.assert_called_with("testuser/test-repo")
        
        # Verify no repo creation was attempted
        mock_gitea['user'].create_repo.assert_not_called()
        
    def test_get_repo_info(self, mock_gitea):
        """Test getting repository information."""
        client = GiteaHubClient("https://gitea.example.com", token="test_token")
        
        # Mock Repository.request to return our mock repo
        mock_repo = mock_gitea['repo']
        mock_repo.full_name = "testuser/test-repo"
        mock_repo.name = "test-repo"
        mock_repo.owner.login = "testuser"
        mock_repo.description = "Test repository"
        mock_repo.private = False
        mock_repo.topics = ["Model"]
        mock_repo.updated_at = "2023-01-01T00:00:00Z"
        mock_repo.stars_count = 10
        mock_repo.watchers_count = 5
        
        mock_gitea['repo_cls'].request.return_value = mock_repo
        
        # Call the method
        result = client.get_repo_info("testuser/test-repo")
        
        # Verify Repository.request was called
        mock_gitea['repo_cls'].request.assert_called_with(
            mock_gitea['gitea'], 
            "testuser", 
            "test-repo"
        )
        
        # Verify result has expected structure
        assert result["full_name"] == "testuser/test-repo"
        assert result["name"] == "test-repo"
        assert result["owner"]["login"] == "testuser"
        assert result["description"] == "Test repository"
        assert result["private"] == False
        assert result["topics"] == ["Model"]
        assert result["updated_at"] == "2023-01-01T00:00:00Z"
        assert result["stars_count"] == 10
        assert result["watchers_count"] == 5
    
    def test_delete_repo(self, mock_gitea):
        """Test repository deletion."""
        client = GiteaHubClient("https://gitea.example.com", token="test_token")
        
        # Mock Repository.request to return our mock repo
        mock_repo = mock_gitea['repo']
        mock_gitea['repo_cls'].request.return_value = mock_repo
        
        # Call the method
        result = client.delete_repo("testuser/test-repo")
        
        # Verify Repository.request was called
        mock_gitea['repo_cls'].request.assert_called_with(
            mock_gitea['gitea'], 
            "testuser", 
            "test-repo"
        )
        
        # Verify delete was called
        mock_repo.delete.assert_called_once()
        
        # Verify result is True
        assert result is True
        
    def test_update_repo_topics(self, mock_gitea):
        """Test updating repository topics."""
        client = GiteaHubClient("https://gitea.example.com", token="test_token")
        
        # Mock Repository.request to return our mock repo
        mock_repo = mock_gitea['repo']
        mock_repo.topics = ["existing-topic"]
        mock_gitea['repo_cls'].request.return_value = mock_repo
        
        # Call the method
        result = client.update_repo_topics("testuser/test-repo", ["new-topic"])
        
        # Verify Repository.request was called
        mock_gitea['repo_cls'].request.assert_called_with(
            mock_gitea['gitea'], 
            "testuser", 
            "test-repo"
        )
        
        # Verify add_topic was called
        mock_repo.add_topic.assert_called_with("new-topic")
        
    def test_upload_file_new(self, mock_gitea):
        """Test uploading a new file."""
        client = GiteaHubClient("https://gitea.example.com", token="test_token")
        
        # Mock Repository.request to return our mock repo
        mock_repo = mock_gitea['repo']
        mock_gitea['repo_cls'].request.return_value = mock_repo
        
        # Mock get_git_content to return an empty list (no files)
        mock_repo.get_git_content.return_value = []
        
        # Mock create_file to return a response
        mock_result = MagicMock()
        mock_result.sha = "commit-sha"
        mock_repo.create_file.return_value = mock_result
        
        # Mock open to return file content
        file_content = b"test file content"
        encoded_content = base64.b64encode(file_content).decode('utf-8')
        
        with patch("builtins.open", mock_open(read_data=file_content)):
            # Call the method
            result = client.upload_file(
                repo_id="testuser/test-repo",
                local_path="/path/to/test.txt",
                repo_path="test.txt",
                commit_message="Upload test file"
            )
            
        # Verify Repository.request was called
        mock_gitea['repo_cls'].request.assert_called_with(
            mock_gitea['gitea'], 
            "testuser", 
            "test-repo"
        )
        
        # Verify get_git_content was called
        mock_repo.get_git_content.assert_called_with("main", "")
        
        # Verify create_file was called with base64 encoded content
        mock_repo.create_file.assert_called_with(
            path="test.txt",
            content=encoded_content,
            message="Upload test file",
            branch="main"
        )
        
        # Verify result has expected structure
        assert result["commit"]["sha"] == "commit-sha"
        assert result["commit"]["message"] == "Upload test file"
        assert result["content"]["path"] == "test.txt"
        assert result["content"]["name"] == "test.txt"
        
    def test_upload_file_update(self, mock_gitea):
        """Test updating an existing file."""
        client = GiteaHubClient("https://gitea.example.com", token="test_token")
        
        # Mock Repository.request to return our mock repo
        mock_repo = mock_gitea['repo']
        mock_gitea['repo_cls'].request.return_value = mock_repo
        
        # Mock get_git_content to return a file
        mock_file = MagicMock()
        mock_file.path = "test.txt"
        mock_file.sha = "file-sha"
        mock_repo.get_git_content.return_value = [mock_file]
        
        # Mock change_file to return a response
        mock_result = MagicMock()
        mock_result.sha = "commit-sha"
        mock_repo.change_file.return_value = mock_result
        
        # Mock open to return file content
        file_content = b"updated file content"
        encoded_content = base64.b64encode(file_content).decode('utf-8')
        
        with patch("builtins.open", mock_open(read_data=file_content)):
            # Call the method
            result = client.upload_file(
                repo_id="testuser/test-repo",
                local_path="/path/to/test.txt",
                repo_path="test.txt",
                commit_message="Update test file"
            )
            
        # Verify Repository.request was called
        mock_gitea['repo_cls'].request.assert_called_with(
            mock_gitea['gitea'], 
            "testuser", 
            "test-repo"
        )
        
        # Verify get_git_content was called
        mock_repo.get_git_content.assert_called_with("main", "")
        
        # Verify change_file was called with base64 encoded content
        mock_repo.change_file.assert_called_with(
            path="test.txt",
            content=encoded_content,
            message="Update test file",
            branch="main",
            sha="file-sha"
        )
        
        # Verify result has expected structure
        assert result["commit"]["sha"] == "commit-sha"
        assert result["commit"]["message"] == "Update test file"
        assert result["content"]["path"] == "test.txt"
        assert result["content"]["name"] == "test.txt"
        
    def test_upload_file_nested_path(self, mock_gitea):
        """Test uploading a file to a nested path."""
        client = GiteaHubClient("https://gitea.example.com", token="test_token")
        
        # Mock Repository.request to return our mock repo
        mock_repo = mock_gitea['repo']
        mock_gitea['repo_cls'].request.return_value = mock_repo
        
        # Mock get_git_content to raise an exception (directory doesn't exist)
        mock_repo.get_git_content.side_effect = Exception("Directory not found")
        
        # Mock create_file to return a response
        mock_result = MagicMock()
        mock_result.sha = "commit-sha"
        mock_repo.create_file.return_value = mock_result
        
        # Mock open to return file content
        file_content = b"test file content"
        encoded_content = base64.b64encode(file_content).decode('utf-8')
        
        with patch("builtins.open", mock_open(read_data=file_content)):
            # Call the method
            result = client.upload_file(
                repo_id="testuser/test-repo",
                local_path="/path/to/test.txt",
                repo_path="nested/path/test.txt",
                commit_message="Upload test file"
            )
            
        # Verify Repository.request was called
        mock_gitea['repo_cls'].request.assert_called_with(
            mock_gitea['gitea'], 
            "testuser", 
            "test-repo"
        )
        
        # Verify get_git_content was called
        mock_repo.get_git_content.assert_called_with("main", "nested/path")
        
        # Verify create_file was called with base64 encoded content
        mock_repo.create_file.assert_called_with(
            path="nested/path/test.txt",
            content=encoded_content,
            message="Upload test file",
            branch="main"
        )
        
        # Verify result has expected structure
        assert result["commit"]["sha"] == "commit-sha"
        assert result["commit"]["message"] == "Upload test file"
        assert result["content"]["path"] == "nested/path/test.txt"
        assert result["content"]["name"] == "test.txt"