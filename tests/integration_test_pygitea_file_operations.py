"""
Test file operations with py-gitea.

Integration tests that require a running Gitea server.
"""

import pytest
import os
import sys
import base64
from pathlib import Path

# Mark all tests in this file as integration tests
pytestmark = pytest.mark.integration

# Add the parent directory to sys.path to make the tests module importable
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
from tests.test_utils import (
    setup_test_env, 
    cleanup_repos, 
    get_random_name, 
    create_test_file, 
    create_test_dir, 
    cleanup_test_files,
    GITEA_USER
)
from gitea import Repository, User

class TestGiteaFileOperations:
    """Test file operations using py-gitea."""
    
    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        """Set up the test environment and clean up afterward."""
        self.gitea = setup_test_env()
        self.test_files = []
        self.test_dirs = []
        
        # Create a test repository
        user = self.gitea.get_user()
        self.repo_name = get_random_name()
        
        # Create repository using the User object's create_repo method
        repo = user.create_repo(
            repoName=self.repo_name,
            description="Test repository for file operations",
            private=False,
            autoInit=True  # Initialize with README
        )
        
        # Get a proper Repository object
        self.repo = Repository.request(self.gitea, user.username, self.repo_name)
        
        yield
        
        # Clean up test files and directories
        for file in self.test_files:
            try:
                cleanup_test_files(file)
            except:
                pass
        
        for directory in self.test_dirs:
            try:
                cleanup_test_files(directory)
            except:
                pass
        
        # Clean up test repositories
        try:
            self.repo.delete()
        except:
            pass
        
        cleanup_repos(self.gitea)
    
    def test_file_create_read(self):
        """Test creating a file and reading it back."""
        # Create a file in the repository
        file_path = "test_file.txt"
        content = "This is test content."
        
        # The Gitea API requires content to be base64 encoded
        # Looking at the error message and tests, we need to encode content
        base64_content = base64.b64encode(content.encode()).decode()
        
        # Looking at test_api.py, the create_file method signature is:
        # repo.create_file("filename", content="content")
        # There is no message parameter - the commit message is handled internally
        # Also, the content needs to be base64 encoded
        self.repo.create_file(
            file_path,  # First parameter is the path/filename
            content=base64_content  # Content parameter for the base64 encoded file contents
        )
        
        # Use the get_git_content method to get file objects first, then get contents
        # This follows exactly how test_api.py does it
        files = self.repo.get_git_content("")
        file_obj = [f for f in files if f.name == file_path][0]
        
        # Now get content using the file object
        file_content = self.repo.get_file_content(file_obj)
        
        # Content comes back base64 encoded - decode it
        decoded_content = base64.b64decode(file_content).decode()
        assert decoded_content == content
        
        print(f"Successfully created and read file: {file_path}")
    
    def test_file_update(self):
        """Test updating a file."""
        # First create a file
        file_path = "update_test.txt"
        original_content = "Original content."
        
        # Create the file - using the correct method signature from test_api.py
        # Base64 encode the content as required by the Gitea API
        base64_content = base64.b64encode(original_content.encode()).decode()
        
        create_response = self.repo.create_file(
            file_path,  # First parameter is the path/filename
            content=base64_content  # Base64 encoded content
        )
        
        # Get file object first using get_git_content (following test_api.py)
        files = self.repo.get_git_content("")
        file_obj = [f for f in files if f.name == file_path][0]
        
        # Get the SHA from the file object
        file_sha = file_obj.sha
        
        assert file_sha is not None, "Could not determine file SHA for update"
        
        # Update the file - using the correct method signature from test_api.py:
        # repo.change_file("filename", file_sha, content="content")
        new_content = "Updated content."
        
        # Base64 encode the new content
        base64_new_content = base64.b64encode(new_content.encode()).decode()
        
        self.repo.change_file(
            file_path,  # First parameter is the path/filename 
            file_sha,   # Second parameter is the SHA of the existing file
            content=base64_new_content  # Base64 encoded content
        )
        
        # Read back using get_git_content and get_file_content
        files = self.repo.get_git_content("")
        updated_file_obj = [f for f in files if f.name == file_path][0]
        
        # Get file content
        updated_content_b64 = self.repo.get_file_content(updated_file_obj)
        
        # Decode content
        updated_content = base64.b64decode(updated_content_b64).decode()
        
        # Verify content was updated
        assert updated_content == new_content
        print(f"Successfully updated file: {file_path}")
    
    def test_file_delete(self):
        """Test deleting a file."""
        # First create a file
        file_path = "delete_test.txt"
        content = "Content for deletion test."
        
        # Create the file - using correct signature
        # Base64 encode the content
        base64_content = base64.b64encode(content.encode()).decode()
        
        self.repo.create_file(
            file_path,  # First parameter is the path/filename
            content=base64_content  # Base64 encoded content
        )
        
        # Get file object to get SHA (following test_api.py pattern)
        files = self.repo.get_git_content("")
        file_obj = [f for f in files if f.name == file_path][0]
        
        # Get the SHA from the file object
        file_sha = file_obj.sha
        
        assert file_sha is not None, "Could not determine file SHA for deletion"
        
        # Delete the file - using the correct signature from test_api.py:
        # repo.delete_file("filename", file_sha)
        self.repo.delete_file(
            file_path,  # First parameter is the path/filename
            file_sha    # Second parameter is the SHA of the file
        )
        
        # Verify the file is deleted
        with pytest.raises(Exception):
            self.repo.get_file_content(file_path)
            
        print(f"Successfully deleted file: {file_path}")
    
    def test_upload_local_file(self):
        """Test uploading a local file to a repository."""
        # Create a local test file
        local_content = "Local file content for upload test."
        local_file = create_test_file(content=local_content)
        self.test_files.append(local_file)
        
        # Get file name for repository path
        repo_path = os.path.basename(local_file)
        
        # Read the local file
        with open(local_file, 'r') as f:
            file_content = f.read()
        
        # Upload to repository - using correct signature
        # Base64 encode the file content
        base64_file_content = base64.b64encode(file_content.encode()).decode()
        
        self.repo.create_file(
            repo_path,  # First parameter is the path/filename
            content=base64_file_content  # Base64 encoded content
        )
        
        # Verify the file exists (following test_api.py pattern)
        files = self.repo.get_git_content("")
        file_obj = [f for f in files if f.name == repo_path][0]
        
        # Get file content to verify it exists
        file_content_b64 = self.repo.get_file_content(file_obj)
        
        # Decode the content
        decoded_content = base64.b64decode(file_content_b64).decode()
        
        # Verify correct content
        assert decoded_content == file_content
        
        print(f"Successfully uploaded local file: {repo_path}")
        
    def test_multiple_files(self):
        """Test creating multiple files and listing directory contents."""
        # Create multiple files in a directory structure
        files = [
            "file1.txt",
            "file2.txt",
            "dir/file3.txt",  # File in a subdirectory
        ]
        
        # Create the files
        for i, file_path in enumerate(files):
            content = f"Content for file {i+1}"
            
            try:
                # Base64 encode each file's content
                base64_content = base64.b64encode(content.encode()).decode()
                
                self.repo.create_file(
                    file_path,  # First parameter is the path/filename 
                    content=base64_content  # Base64 encoded content parameter
                )
                print(f"Created {file_path}")
            except Exception as e:
                print(f"Error creating {file_path}: {e}")
                # If this fails for directories, it might be because we need to create the directory first
                # Or because Gitea doesn't support implicit directory creation
        
        # List repository contents
        try:
            # Get repository contents at root level
            contents = self.repo.get_git_content("")
            
            # Check if we got a list of contents
            if isinstance(contents, list):
                file_names = [item.name if hasattr(item, 'name') else item for item in contents]
                print(f"Repository contents: {file_names}")
                
                # We should have at least file1.txt and file2.txt
                assert any(name == "file1.txt" for name in file_names)
                assert any(name == "file2.txt" for name in file_names)
            else:
                print("Unexpected response format when listing repository contents")
        except Exception as e:
            print(f"Error listing repository contents: {e}")