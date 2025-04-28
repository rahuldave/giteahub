"""
Test connectivity to Gitea API using py-gitea.
"""

import pytest
import os
import sys
import os.path

# Add the parent directory to sys.path to make the tests module importable
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
from tests.test_utils import setup_test_env, cleanup_repos, get_random_name

class TestGiteaConnection:
    """Test basic connectivity to Gitea API."""
    
    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        """Set up the test environment and clean up afterward."""
        self.gitea = setup_test_env()
        self.test_repos = []
        yield
        # Clean up any repos that weren't properly deleted during tests
        for repo in self.test_repos:
            try:
                repo.delete()
            except:
                pass
        cleanup_repos(self.gitea)
    
    def test_get_version(self):
        """Test that we can retrieve the Gitea version."""
        version = self.gitea.get_version()
        assert version is not None
        print(f"Connected to Gitea version: {version}")
    
    def test_get_user(self):
        """Test that we can retrieve the current user."""
        user = self.gitea.get_user()
        assert user is not None
        assert user.username == "rahuldave"
        print(f"Connected as user: {user.username}")
    
    def test_repo_creation_user(self):
        """Test creating a repository under user account."""
        # Get the user object first - this returns the authenticated user (rahuldave)
        # because we initialized gitea with rahuldave's token
        user = self.gitea.get_user()
        
        # After examining apiobject.py, the correct way to create a repo as a non-admin is:
        # user.create_repo(repo_name, description, private, auto_init, ...)
        # For a regular user, we need to use the User object's create_repo method
        # NOT the gitea instance's create_repo method (which is admin-only)
        repo_name = get_random_name()
        repo = user.create_repo(
            repoName=repo_name,
            description="Test repository",
            private=False,
            autoInit=True
        )
        self.test_repos.append(repo)
        
        assert repo is not None
        assert repo.name == repo_name
        print(f"Created user repository: {repo.name}")
        
        # Add and verify topic - topics are critical for our implementation
        # as they distinguish models from datasets from spaces
        # Based on the py-gitea tests, we should be able to use the Repository object directly
        # But we need to get a proper Repository object first via Repository.request()
        from gitea import Repository
        
        # Get a proper Repository object using Repository.request
        repo = Repository.request(self.gitea, user.username, repo_name)
        
        # Now we can use the add_topic method
        repo.add_topic("test-topic")
        topics = repo.get_topics()
        assert "test-topic" in topics
        print(f"Added and verified topic 'test-topic'")
        
        # Test repo deletion
        # We'll keep track of the repo by name since the object becomes invalid after deletion
        repo.delete()
        # We'll manually clean our test_repos list rather than using .remove()
        # since the repository object is now marked as deleted
        self.test_repos = [r for r in self.test_repos if (hasattr(r, 'name') and r.name != repo_name)]
        print(f"Deleted user repository: {repo_name}")
    
    def test_repo_creation_org(self):
        """Test creating a repository under organization account."""
        # First check if the organization exists using the API endpoint directly
        # since we've seen issues with the get_organization method
        try:
            org_data = self.gitea.requests_get(f"/orgs/rahuldaveorg")
            assert org_data is not None
            
            # Now get the Organization object properly
            from gitea import Organization
            org = Organization.request(self.gitea, "rahuldaveorg")
            assert org is not None
        except Exception as e:
            pytest.skip(f"Organization 'rahuldaveorg' does not exist: {e}")
            
        # Create a repository using the Organization object's create_repo method
        # similar to how we use User.create_repo for user repositories
        repo_name = get_random_name()
        repo = org.create_repo(
            repoName=repo_name,
            description="Test organization repository",
            private=False,
            autoInit=True
        )
        self.test_repos.append(repo)
        
        assert repo is not None
        assert repo.name == repo_name
        print(f"Created organization repository: {repo.name}")
        
        # Add and verify topic - topics are critical for our implementation
        # as they distinguish models from datasets from spaces
        from gitea import Repository
        
        # Get a proper Repository object using Repository.request
        repo = Repository.request(self.gitea, org.username, repo_name)
        
        # Now we can use the add_topic method
        repo.add_topic("test-topic")
        repo.add_topic("org-repo")  # Add a second topic to test multiple topics
        topics = repo.get_topics()
        assert "test-topic" in topics
        assert "org-repo" in topics
        print(f"Added and verified topics 'test-topic', 'org-repo'")
        
        # Test repo deletion
        # We'll keep track of the repo by name since the object becomes invalid after deletion
        repo.delete()
        # We'll manually clean our test_repos list rather than using .remove()
        # since the repository object is now marked as deleted
        self.test_repos = [r for r in self.test_repos if (hasattr(r, 'name') and r.name != repo_name)]
        print(f"Deleted organization repository: {repo_name}")