"""
Configuration for pytest.
"""

import pytest
import os
import sys
import os.path

# Add the parent directory to sys.path to make the tests module importable
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
from tests.test_utils import setup_test_env, cleanup_repos

@pytest.fixture(scope="session", autouse=True)
def global_setup_teardown():
    """
    Set up test environment before all tests run,
    and clean up afterward.
    """
    # Setup
    gitea_client = setup_test_env()
    
    yield
    
    # Teardown - clean up any test repositories that might be left
    cleanup_repos(gitea_client)
    
    # Clean up any temporary files or directories
    temp_patterns = ["temp_*", "test_dir_*", "downloads", "full_download"]
    for pattern in temp_patterns:
        try:
            import glob
            import shutil
            
            for item in glob.glob(pattern):
                if os.path.isdir(item):
                    shutil.rmtree(item)
                else:
                    os.remove(item)
        except Exception as e:
            print(f"Error cleaning up {pattern}: {e}")

def pytest_configure(config):
    """Configure pytest."""
    # Add markers
    config.addinivalue_line("markers", "connection: tests for basic Gitea connection")
    config.addinivalue_line("markers", "file_operations: tests for file operations")
    config.addinivalue_line("markers", "adapter: tests for the Hugging Face Hub adapter")
    config.addinivalue_line("markers", "datasets: tests for the datasets integration")

def pytest_collection_modifyitems(items):
    """Add markers based on file names."""
    for item in items:
        if "test_pygitea_connection" in item.nodeid:
            item.add_marker(pytest.mark.connection)
        elif "test_pygitea_file_operations" in item.nodeid:
            item.add_marker(pytest.mark.file_operations)
        elif "test_gitea_hub_adapter" in item.nodeid:
            item.add_marker(pytest.mark.adapter)
        elif "test_gitea_datasets_integration" in item.nodeid:
            item.add_marker(pytest.mark.datasets)