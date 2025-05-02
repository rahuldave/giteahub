"""
Unit tests for the HfApi class.
"""

import os
import pytest
import tempfile
import base64
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open

from giteahub.gitea_huggingface_client import (
    HfApi,
    GiteaHubClient,
    REPO_TYPE_MODEL,
    REPO_TYPE_DATASET,
    REPO_TYPE_SPACE
)

class TestHfApi:
    """Unit tests for the HfApi class."""
    
    @pytest.fixture
    def mock_client(self):
        """Mock the GiteaHubClient."""
        with patch('giteahub.gitea_huggingface_client.GiteaHubClient') as mock_client_cls:
            # Set up mock instance
            mock_client_instance = mock_client_cls.return_value
            
            # Set up mock methods
            mock_client_instance.create_repo.return_value = {"name": "test-repo"}
            mock_client_instance.delete_repo.return_value = True
            mock_client_instance.upload_file.return_value = {
                "commit": {"sha": "commit-sha"},
                "content": {"path": "test.txt", "name": "test.txt"}
            }
            
            yield mock_client_instance
    
    def test_initialization(self, mock_client):
        """Test initialization of the HfApi class."""
        # Set environment variables for testing
        os.environ["HF_ENDPOINT"] = "https://gitea.test"
        os.environ["HF_TOKEN"] = "test-token"
        
        # Initialize the API
        api = HfApi()
        
        # Verify client was created with correct parameters
        from giteahub.gitea_huggingface_client import GiteaHubClient
        GiteaHubClient.assert_called_with("https://gitea.test", token="test-token")
        
        # Clean up
        del os.environ["HF_ENDPOINT"]
        del os.environ["HF_TOKEN"]
    
    def test_create_repo(self, mock_client):
        """Test creating a repository."""
        # Set environment variables for testing
        os.environ["HF_ENDPOINT"] = "https://gitea.test"
        os.environ["HF_TOKEN"] = "test-token"
        
        # Initialize the API
        api = HfApi()
        
        # Test create_repo method
        result = api.create_repo("testuser/test-repo", repo_type=REPO_TYPE_MODEL, private=True)
        
        # Verify client method was called with correct parameters
        mock_client.create_repo.assert_called_with(
            "testuser/test-repo", 
            private=True, 
            repo_type=REPO_TYPE_MODEL
        )
        
        # Verify result
        assert result == {"name": "test-repo"}
        
        # Clean up
        del os.environ["HF_ENDPOINT"]
        del os.environ["HF_TOKEN"]
    
    def test_delete_repo(self, mock_client):
        """Test deleting a repository."""
        # Set environment variables for testing
        os.environ["HF_ENDPOINT"] = "https://gitea.test"
        os.environ["HF_TOKEN"] = "test-token"
        
        # Initialize the API
        api = HfApi()
        
        # Test delete_repo method
        result = api.delete_repo("testuser/test-repo")
        
        # Verify client method was called
        mock_client.delete_repo.assert_called_with("testuser/test-repo")
        
        # Verify result
        assert result is True
        
        # Clean up
        del os.environ["HF_ENDPOINT"]
        del os.environ["HF_TOKEN"]
    
    def test_upload_file(self, mock_client):
        """Test uploading a file."""
        # Set environment variables for testing
        os.environ["HF_ENDPOINT"] = "https://gitea.test"
        os.environ["HF_TOKEN"] = "test-token"
        
        # Initialize the API
        api = HfApi()
        
        # Test with a file path
        result = api.upload_file(
            path_or_fileobj="/path/to/test.txt",
            path_in_repo="test.txt",
            repo_id="testuser/test-repo",
            commit_message="Upload test file"
        )
        
        # Verify client method was called with correct parameters
        mock_client.upload_file.assert_called_with(
            repo_id="testuser/test-repo",
            local_path="/path/to/test.txt",
            repo_path="test.txt",
            commit_message="Upload test file",
            branch="main"
        )
        
        # Verify result
        assert result == {
            "commit": {"sha": "commit-sha"},
            "content": {"path": "test.txt", "name": "test.txt"}
        }
        
        # Clean up
        del os.environ["HF_ENDPOINT"]
        del os.environ["HF_TOKEN"]
        
    def test_upload_file_with_fileobj(self, mock_client):
        """Test uploading a file with a file-like object."""
        # Set environment variables for testing
        os.environ["HF_ENDPOINT"] = "https://gitea.test"
        os.environ["HF_TOKEN"] = "test-token"
        
        # Initialize the API
        api = HfApi()
        
        # Mock file object
        file_content = b"test file content"
        fileobj = MagicMock()
        fileobj.read.return_value = file_content
        
        # Mock tempfile.NamedTemporaryFile
        mock_temp = MagicMock()
        mock_temp.__enter__.return_value = mock_temp
        mock_temp.name = "/tmp/tempfile123"
        
        with patch('tempfile.NamedTemporaryFile', return_value=mock_temp):
            # Test with a file-like object
            result = api.upload_file(
                path_or_fileobj=fileobj,
                path_in_repo="test.txt",
                repo_id="testuser/test-repo",
                commit_message="Upload test file"
            )
            
            # Verify tempfile was written to
            mock_temp.write.assert_called_with(file_content)
            
            # Verify client method was called with correct parameters
            mock_client.upload_file.assert_called_with(
                repo_id="testuser/test-repo",
                local_path="/tmp/tempfile123",
                repo_path="test.txt",
                commit_message="Upload test file",
                branch="main"
            )
        
        # Clean up
        del os.environ["HF_ENDPOINT"]
        del os.environ["HF_TOKEN"]
        
    def test_upload_folder(self, mock_client):
        """Test uploading a folder."""
        # Set environment variables for testing
        os.environ["HF_ENDPOINT"] = "https://gitea.test"
        os.environ["HF_TOKEN"] = "test-token"
        
        # Initialize the API
        api = HfApi()
        
        # Create a temporary directory structure
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create files in the temp directory
            file1_path = os.path.join(temp_dir, "file1.txt")
            with open(file1_path, 'w') as f:
                f.write("File 1 content")
                
            # Create subdirectory
            sub_dir = os.path.join(temp_dir, "subdir")
            os.makedirs(sub_dir)
            
            # Create file in subdirectory
            file2_path = os.path.join(sub_dir, "file2.txt")
            with open(file2_path, 'w') as f:
                f.write("File 2 content")
                
            # Set up mock responses for each file upload
            file1_result = {
                "commit": {"sha": "commit-sha-1"},
                "content": {"path": "file1.txt", "name": "file1.txt"}
            }
            file2_result = {
                "commit": {"sha": "commit-sha-2"},
                "content": {"path": "subdir/file2.txt", "name": "file2.txt"}
            }
            
            # Set up the mock to return different values for each call
            mock_client.upload_file.side_effect = [file1_result, file2_result]
            
            # Test upload_folder method
            result = api.upload_folder(
                folder_path=temp_dir,
                repo_id="testuser/test-repo",
                commit_message="Upload folder"
            )
            
            # Verify that upload_file was called for each file
            assert mock_client.upload_file.call_count == 2
            
            # Verify the result is the last upload result
            assert result == file2_result
        
        # Clean up
        del os.environ["HF_ENDPOINT"]
        del os.environ["HF_TOKEN"]
        
    def test_hf_hub_download(self):
        """Test downloading a file from a repository."""
        # Create mock objects
        with patch('giteahub.gitea_huggingface_client.GiteaHubClient') as mock_client_cls, \
             patch('giteahub.gitea_huggingface_client.Repository') as mock_repo_cls, \
             patch('os.makedirs') as mock_makedirs, \
             patch('builtins.open', mock_open()) as mock_file:
            
            # Set up mock client
            mock_client = MagicMock()
            mock_client_cls.return_value = mock_client
            mock_gitea = MagicMock()
            mock_client.gitea = mock_gitea
            
            # Set up mock repository
            mock_repo = MagicMock()
            mock_repo_cls.request.return_value = mock_repo
            
            # Set up mock file object returned by get_git_content
            mock_file_obj = MagicMock()
            mock_file_obj.path = "test_file.txt"
            mock_file_obj.name = "test_file.txt"
            mock_repo.get_git_content.return_value = [mock_file_obj]
            
            # Set up mock file content (base64 encoded)
            test_content = "This is test content"
            encoded_content = base64.b64encode(test_content.encode()).decode()
            mock_repo.get_file_content.return_value = encoded_content
            
            # Set environment variables
            os.environ["HF_ENDPOINT"] = "https://gitea.test"
            os.environ["HF_TOKEN"] = "test-token"
            
            # Call the function
            from giteahub.gitea_huggingface_client import hf_hub_download
            result = hf_hub_download(
                repo_id="testuser/test-repo",
                filename="test_file.txt",
                local_dir="downloads"
            )
            
            # Verify Repository.request was called with gitea client
            mock_repo_cls.request.assert_called_with(mock_gitea, "testuser", "test-repo")
            
            # Verify get_git_content was called
            mock_repo.get_git_content.assert_called_with()
            
            # Verify get_file_content was called with the correct file object
            mock_repo.get_file_content.assert_called_with(mock_file_obj)
            
            # Verify makedirs was called to create the downloads directory
            mock_makedirs.assert_called_with("downloads", exist_ok=True)
            
            # Verify file was opened for writing
            mock_file.assert_called_with(os.path.join("downloads", "test_file.txt"), 'wb')
            
            # Verify file contents were written (base64 decoded)
            mock_file().write.assert_called_with(base64.b64decode(encoded_content))
            
            # Verify the result is the absolute path to the downloaded file
            assert result == os.path.abspath(os.path.join("downloads", "test_file.txt"))
            
            # Clean up
            del os.environ["HF_ENDPOINT"]
            del os.environ["HF_TOKEN"]
            
    def test_hf_hub_download_file_not_found(self):
        """Test downloading a file that doesn't exist."""
        with patch('giteahub.gitea_huggingface_client.GiteaHubClient') as mock_client_cls, \
             patch('giteahub.gitea_huggingface_client.Repository') as mock_repo_cls:
            # Set up mock client
            mock_client = MagicMock()
            mock_client_cls.return_value = mock_client
            mock_gitea = MagicMock()
            mock_client.gitea = mock_gitea
            
            # Set up mock repository
            mock_repo = MagicMock()
            mock_repo_cls.request.return_value = mock_repo
            
            # Return empty list from get_git_content (no files)
            mock_repo.get_git_content.return_value = []
            
            # Set environment variables
            os.environ["HF_ENDPOINT"] = "https://gitea.test"
            os.environ["HF_TOKEN"] = "test-token"
            
            # Verify that ValueError is raised
            from giteahub.gitea_huggingface_client import hf_hub_download
            with pytest.raises(ValueError, match="File 'missing_file.txt' not found in repository"):
                hf_hub_download(
                    repo_id="testuser/test-repo",
                    filename="missing_file.txt"
                )
            
            # Clean up
            del os.environ["HF_ENDPOINT"]
            del os.environ["HF_TOKEN"]
            
    def test_snapshot_download(self):
        """Test downloading an entire repository."""
        # Create mock objects
        with patch('giteahub.gitea_huggingface_client.GiteaHubClient') as mock_client_cls, \
             patch('giteahub.gitea_huggingface_client.Repository') as mock_repo_cls, \
             patch('os.makedirs') as mock_makedirs, \
             patch('os.path.join', side_effect=os.path.join) as mock_join, \
             patch('os.path.abspath', side_effect=os.path.abspath) as mock_abspath, \
             patch('os.path.dirname', side_effect=os.path.dirname) as mock_dirname, \
             patch('builtins.open', mock_open()) as mock_file:
            
            # Set up mock client
            mock_client = MagicMock()
            mock_client_cls.return_value = mock_client
            mock_gitea = MagicMock()
            mock_client.gitea = mock_gitea
            
            # Set up mock repository
            mock_repo = MagicMock()
            mock_repo_cls.request.return_value = mock_repo
            
            # Set up mock file objects returned by get_git_content
            mock_file_obj1 = MagicMock()
            mock_file_obj1.path = "file1.txt"
            mock_file_obj1.name = "file1.txt"
            mock_file_obj1.type = "file"
            
            mock_file_obj2 = MagicMock()
            mock_file_obj2.path = "subdir/file2.txt"
            mock_file_obj2.name = "file2.txt"
            mock_file_obj2.type = "file"
            
            mock_repo.get_git_content.return_value = [mock_file_obj1, mock_file_obj2]
            
            # Set up mock file contents (base64 encoded)
            file1_content = "Content for file 1"
            file2_content = "Content for file 2"
            encoded_file1 = base64.b64encode(file1_content.encode()).decode()
            encoded_file2 = base64.b64encode(file2_content.encode()).decode()
            
            # Setup get_file_content to return different values for different file objects
            def mock_get_file_content(file_obj):
                if file_obj.path == "file1.txt":
                    return encoded_file1
                elif file_obj.path == "subdir/file2.txt":
                    return encoded_file2
                return ""
                
            mock_repo.get_file_content.side_effect = mock_get_file_content
            
            # Set environment variables
            os.environ["HF_ENDPOINT"] = "https://gitea.test"
            os.environ["HF_TOKEN"] = "test-token"
            
            # Call the function
            from giteahub.gitea_huggingface_client import snapshot_download
            result = snapshot_download(
                repo_id="testuser/test-repo",
                local_dir="full_download"
            )
            
            # Verify Repository.request was called with gitea client
            mock_repo_cls.request.assert_called_with(mock_gitea, "testuser", "test-repo")
            
            # Verify get_git_content was called
            mock_repo.get_git_content.assert_called_with()
            
            # Verify makedirs was called for the base directory
            mock_makedirs.assert_any_call("full_download", exist_ok=True)
            
            # Verify makedirs was called for the subdirectory
            mock_makedirs.assert_any_call(os.path.dirname(os.path.join("full_download", "subdir/file2.txt")), exist_ok=True)
            
            # Verify the returned path is correct
            assert result == os.path.abspath("full_download")
            
            # Clean up
            del os.environ["HF_ENDPOINT"]
            del os.environ["HF_TOKEN"]
            
    def test_snapshot_download_empty_repo(self):
        """Test downloading an empty repository."""
        # Create mock objects
        with patch('giteahub.gitea_huggingface_client.GiteaHubClient') as mock_client_cls, \
             patch('giteahub.gitea_huggingface_client.Repository') as mock_repo_cls, \
             patch('os.makedirs') as mock_makedirs, \
             patch('os.path.abspath', side_effect=os.path.abspath) as mock_abspath:
            
            # Set up mock client
            mock_client = MagicMock()
            mock_client_cls.return_value = mock_client
            mock_gitea = MagicMock()
            mock_client.gitea = mock_gitea
            
            # Set up mock repository
            mock_repo = MagicMock()
            mock_repo_cls.request.return_value = mock_repo
            
            # Set up get_git_content to return empty list (no files in repo)
            mock_repo.get_git_content.return_value = []
            
            # Set environment variables
            os.environ["HF_ENDPOINT"] = "https://gitea.test"
            os.environ["HF_TOKEN"] = "test-token"
            
            # Call the function
            from giteahub.gitea_huggingface_client import snapshot_download
            result = snapshot_download(
                repo_id="testuser/test-repo",
                local_dir="full_download"
            )
            
            # Verify makedirs was called for the base directory
            mock_makedirs.assert_called_with("full_download", exist_ok=True)
            
            # Verify the returned path is correct
            assert result == os.path.abspath("full_download")
            
            # Clean up
            del os.environ["HF_ENDPOINT"]
            del os.environ["HF_TOKEN"]