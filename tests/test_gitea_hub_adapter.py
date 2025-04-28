"""
Test the Gitea Hub adapter implementation that leverages py-gitea.
"""

import pytest
import os
import shutil
from pathlib import Path
from tests.test_utils import (
    setup_test_env, 
    cleanup_repos, 
    get_random_name, 
    create_test_file, 
    create_test_dir, 
    cleanup_test_files,
    GITEA_URL,
    GITEA_TOKEN,
    GITEA_USER,
    GITEA_ORG
)

# Import our adapter implementation - this will be what we're going to build
from giteahub.gitea_huggingface_client import HfApi, create_repo, hf_hub_download, snapshot_download

class TestGiteaHubAdapter:
    """Test the Gitea Hub adapter implementation."""
    
    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        """Set up the test environment and clean up afterward."""
        self.gitea = setup_test_env()
        self.test_repos = []
        self.test_files = []
        self.test_dirs = []
        
        # Set environment variables
        os.environ["HF_ENDPOINT"] = GITEA_URL
        os.environ["HF_TOKEN"] = GITEA_TOKEN
        
        # Initialize the API client
        self.api = HfApi()
        
        yield
        
        # Clean up test files and directories
        for file in self.test_files:
            cleanup_test_files(file)
        
        for directory in self.test_dirs:
            cleanup_test_files(directory)
        
        # Clean up test downloads
        if os.path.exists("downloads"):
            shutil.rmtree("downloads")
        
        if os.path.exists("full_download"):
            shutil.rmtree("full_download")
            
        # Clean up repositories
        cleanup_repos(self.gitea)
    
    def test_create_repo(self):
        """Test creating a repository."""
        repo_name = get_random_name()
        repo_id = f"{GITEA_USER}/{repo_name}"
        
        # Create using the adapter
        repo_info = create_repo(
            repo_id=repo_id,
            private=False,
            repo_type="model",
            exist_ok=False
        )
        
        assert repo_info is not None
        assert "name" in repo_info
        assert repo_info["name"] == repo_name
        print(f"Created repository: {repo_id}")
        
        # Clean up - delete the repo
        self.api.delete_repo(repo_id)
        print(f"Deleted repository: {repo_id}")
    
    def test_upload_file(self):
        """Test uploading a file to a repository."""
        # Create a repository
        repo_name = get_random_name()
        repo_id = f"{GITEA_USER}/{repo_name}"
        
        repo_info = self.api.create_repo(
            repo_id=repo_id,
            private=False,
            repo_type="model"
        )
        
        # Create a test file
        test_content = "Test file content for upload"
        local_file = create_test_file(content=test_content)
        self.test_files.append(local_file)
        
        # Upload the file
        commit_info = self.api.upload_file(
            path_or_fileobj=local_file,
            path_in_repo="test_file.txt",
            repo_id=repo_id,
            commit_message="Upload test file"
        )
        
        assert commit_info is not None
        print(f"Uploaded file to {repo_id}: {local_file}")
        
        # Clean up - delete the repo
        self.api.delete_repo(repo_id)
        print(f"Deleted repository: {repo_id}")
    
    def test_download_file(self):
        """Test downloading a file from a repository."""
        # Create a repository
        repo_name = get_random_name()
        repo_id = f"{GITEA_USER}/{repo_name}"
        
        repo_info = self.api.create_repo(
            repo_id=repo_id,
            private=False,
            repo_type="model"
        )
        
        # Create and upload a test file
        test_content = "Test file content for download"
        local_file = create_test_file(content=test_content)
        self.test_files.append(local_file)
        
        self.api.upload_file(
            path_or_fileobj=local_file,
            path_in_repo="test_file.txt",
            repo_id=repo_id,
            commit_message="Upload test file for download"
        )
        
        # Download the file
        download_path = hf_hub_download(
            repo_id=repo_id,
            filename="test_file.txt",
            local_dir="downloads"
        )
        
        assert os.path.exists(download_path)
        
        # Check content
        with open(download_path, 'r') as f:
            content = f.read()
            assert content == test_content
        
        print(f"Downloaded file from {repo_id}: {download_path}")
        
        # Clean up - delete the repo
        self.api.delete_repo(repo_id)
        print(f"Deleted repository: {repo_id}")
    
    def test_upload_folder(self):
        """Test uploading a folder to a repository."""
        # Create a repository
        repo_name = get_random_name()
        repo_id = f"{GITEA_USER}/{repo_name}"
        
        repo_info = self.api.create_repo(
            repo_id=repo_id,
            private=False,
            repo_type="dataset"
        )
        
        # Create a test directory with files
        test_dir, test_files = create_test_dir()
        self.test_dirs.append(test_dir)
        
        # Upload the folder
        commit_info = self.api.upload_folder(
            folder_path=test_dir,
            repo_id=repo_id,
            commit_message="Upload test folder"
        )
        
        assert commit_info is not None
        print(f"Uploaded folder to {repo_id}: {test_dir}")
        
        # Clean up - delete the repo
        self.api.delete_repo(repo_id)
        print(f"Deleted repository: {repo_id}")
    
    def test_snapshot_download(self):
        """Test downloading an entire repository."""
        # Create a repository
        repo_name = get_random_name()
        repo_id = f"{GITEA_USER}/{repo_name}"
        
        repo_info = self.api.create_repo(
            repo_id=repo_id,
            private=False,
            repo_type="model"
        )
        
        # Upload multiple files
        for i in range(3):
            test_content = f"Content for file {i}"
            local_file = create_test_file(content=test_content)
            self.test_files.append(local_file)
            
            self.api.upload_file(
                path_or_fileobj=local_file,
                path_in_repo=f"file_{i}.txt",
                repo_id=repo_id,
                commit_message=f"Upload file {i}"
            )
        
        # Download the entire repository
        download_path = snapshot_download(
            repo_id=repo_id,
            local_dir="full_download"
        )
        
        assert os.path.exists(download_path)
        
        # Check that all files were downloaded
        for i in range(3):
            file_path = os.path.join(download_path, f"file_{i}.txt")
            assert os.path.exists(file_path)
            
            with open(file_path, 'r') as f:
                content = f.read()
                assert content == f"Content for file {i}"
        
        print(f"Downloaded repository snapshot: {download_path}")
        
        # Clean up - delete the repo
        self.api.delete_repo(repo_id)
        print(f"Deleted repository: {repo_id}")
    
    def test_create_commit(self):
        """Test creating a commit with multiple file operations."""
        # Create a repository
        repo_name = get_random_name()
        repo_id = f"{GITEA_USER}/{repo_name}"
        
        repo_info = self.api.create_repo(
            repo_id=repo_id,
            private=False,
            repo_type="model"
        )
        
        # Create test files
        file1_content = "Content for file 1"
        file2_content = "Content for file 2"
        
        # Define operations
        operations = [
            {
                "type": "add",
                "path": "file1.txt",
                "content": file1_content
            },
            {
                "type": "add",
                "path": "file2.txt",
                "content": file2_content
            }
        ]
        
        # Create commit
        commit_info = self.api.create_commit(
            repo_id=repo_id,
            operations=operations,
            commit_message="Add multiple files"
        )
        
        assert commit_info is not None
        print(f"Created commit in {repo_id}")
        
        # Verify files exist
        file1_path = hf_hub_download(
            repo_id=repo_id,
            filename="file1.txt",
            local_dir="downloads"
        )
        
        file2_path = hf_hub_download(
            repo_id=repo_id,
            filename="file2.txt",
            local_dir="downloads"
        )
        
        assert os.path.exists(file1_path)
        assert os.path.exists(file2_path)
        
        with open(file1_path, 'r') as f:
            content = f.read()
            assert content == file1_content
            
        with open(file2_path, 'r') as f:
            content = f.read()
            assert content == file2_content
            
        print(f"Verified files in commit")
        
        # Now test delete operation
        delete_operations = [
            {
                "type": "delete",
                "path": "file1.txt"
            }
        ]
        
        delete_commit = self.api.create_commit(
            repo_id=repo_id,
            operations=delete_operations,
            commit_message="Delete file1.txt"
        )
        
        assert delete_commit is not None
        print(f"Created delete commit in {repo_id}")
        
        # Try to download deleted file - should fail
        with pytest.raises(Exception):
            hf_hub_download(
                repo_id=repo_id,
                filename="file1.txt",
                local_dir="downloads"
            )
            
        print(f"Verified file deletion")
        
        # Clean up - delete the repo
        self.api.delete_repo(repo_id)
        print(f"Deleted repository: {repo_id}")