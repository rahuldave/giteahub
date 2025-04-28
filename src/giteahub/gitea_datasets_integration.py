"""
Integration between Gitea Hub Adapter and the Hugging Face Datasets library.

This module provides patches for the datasets library to work with the Gitea backend.
"""

import os
import sys
import functools
import importlib
from typing import Optional, Dict, Any, Union

# Function to patch the datasets library
def patch_datasets_library():
    """
    Patch the datasets library to use our Gitea adapter.

    This function needs to be called before importing datasets.
    """
    try:
        # Import our adapter
        import gitea_huggingface_client
        from gitea_huggingface_client import HfApi

        # Save the original imports
        original_huggingface_hub = sys.modules.get('huggingface_hub')

        # Replace huggingface_hub with our adapter
        sys.modules['huggingface_hub'] = gitea_huggingface_client

        # Import datasets after patching
        import datasets
        import datasets.config
        from datasets.download.download_manager import DownloadManager

        # Patch download methods if needed
        original_get_from_hub = DownloadManager._get_from_hub

        @functools.wraps(original_get_from_hub)
        def patched_get_from_hub(self, url_or_filename, **kwargs):
            # Modify URL to point to our Gitea server if needed
            if hasattr(self, 'gitea_url') and url_or_filename.startswith('https://huggingface.co/'):
                gitea_url = getattr(self, 'gitea_url')
                url_or_filename = url_or_filename.replace('https://huggingface.co/', gitea_url)

            # Call the original method with our modified URL
            return original_get_from_hub(self, url_or_filename, **kwargs)

        # Apply the patch
        DownloadManager._get_from_hub = patched_get_from_hub

        # Add a Gitea URL attribute to the download manager
        gitea_url = os.environ.get('HF_ENDPOINT', 'https://gitea.example.com')
        setattr(DownloadManager, 'gitea_url', gitea_url)

        # Restore the original huggingface_hub if it was there
        if original_huggingface_hub:
            sys.modules['huggingface_hub_original'] = original_huggingface_hub

        return True
    except ImportError as e:
        print(f"Error patching datasets library: {e}")
        return False

# Apply the patch if this module is imported
patched = patch_datasets_library()

# Monkey patch the Dataset.push_to_hub method to work with our adapter
def patch_push_to_hub():
    """
    Patch the Dataset.push_to_hub method to work with our adapter.
    """
    try:
        import datasets
        from datasets import Dataset, DatasetDict
        import gitea_huggingface_client as hub

        # Save the original method
        original_push_to_hub = Dataset.push_to_hub

        @functools.wraps(original_push_to_hub)
        def patched_push_to_hub(self, repo_id, private=False, token=None, branch=None, **kwargs):
            """
            Patched version of push_to_hub that works with Gitea.
            """
            # Check if repo exists, if not create it
            api = hub.HfApi()
            repo_type = "dataset"

            try:
                api.model_info(repo_id=repo_id)
            except Exception:
                # Create the repo if it doesn't exist
                api.create_repo(repo_id=repo_id, repo_type=repo_type, private=private)

            # Save dataset to a temporary directory
            import tempfile
            import shutil
            from pathlib import Path

            with tempfile.TemporaryDirectory() as tmp_dir:
                # Save the dataset to the temp directory
                dataset_path = Path(tmp_dir) / "dataset"
                self.save_to_disk(dataset_path)

                # Upload the entire directory to the hub
                api.upload_folder(
                    folder_path=dataset_path,
                    repo_id=repo_id,
                    token=token,
                    repo_type=repo_type,
                    revision=branch,
                    commit_message="Update dataset",
                )

            return repo_id

        # Apply the patch
        Dataset.push_to_hub = patched_push_to_hub

        # Also patch DatasetDict.push_to_hub if it exists
        if hasattr(DatasetDict, 'push_to_hub'):
            original_dict_push_to_hub = DatasetDict.push_to_hub

            @functools.wraps(original_dict_push_to_hub)
            def patched_dict_push_to_hub(self, repo_id, private=False, token=None, branch=None, **kwargs):
                """
                Patched version of DatasetDict.push_to_hub that works with Gitea.
                """
                # Check if repo exists, if not create it
                api = hub.HfApi()
                repo_type = "dataset"

                try:
                    api.model_info(repo_id=repo_id)
                except Exception:
                    # Create the repo if it doesn't exist
                    api.create_repo(repo_id=repo_id, repo_type=repo_type, private=private)

                # Save dataset to a temporary directory
                import tempfile
                import shutil
                from pathlib import Path

                with tempfile.TemporaryDirectory() as tmp_dir:
                    # Save the dataset to the temp directory
                    dataset_path = Path(tmp_dir) / "dataset"
                    self.save_to_disk(dataset_path)

                    # Upload the entire directory to the hub
                    api.upload_folder(
                        folder_path=dataset_path,
                        repo_id=repo_id,
                        token=token,
                        repo_type=repo_type,
                        revision=branch,
                        commit_message="Update dataset",
                    )

                return repo_id

            # Apply the patch
            DatasetDict.push_to_hub = patched_dict_push_to_hub

        return True
    except ImportError as e:
        print(f"Error patching Dataset.push_to_hub: {e}")
        return False

# Apply the push_to_hub patch if this module is imported
patched_push = patch_push_to_hub()

# Patch the load_dataset function to work with our adapter
def patch_load_dataset():
    """
    Patch the load_dataset function to work with our adapter.
    """
    try:
        import datasets

        # Save the original function
        original_load_dataset = datasets.load_dataset

        @functools.wraps(original_load_dataset)
        def patched_load_dataset(path, *args, **kwargs):
            """
            Patched version of load_dataset that works with Gitea.
            """
            # If path looks like a hub path (username/dataset), handle it specially
            if '/' in path and not path.startswith('./') and not path.startswith('/'):
                # Import our hub adapter
                import gitea_huggingface_client as hub

                # Check if the dataset exists on Gitea
                try:
                    # Download the entire repository
                    import tempfile
                    import shutil
                    from pathlib import Path

                    with tempfile.TemporaryDirectory() as tmp_dir:
                        # Download the dataset
                        repo_path = hub.snapshot_download(
                            repo_id=path,
                            local_dir=tmp_dir,
                            repo_type="dataset",
                        )

                        # Use the downloaded dataset
                        return original_load_dataset(repo_path, *args, **kwargs)
                except Exception as e:
                    print(f"Error loading dataset from Gitea: {e}")
                    # Fall back to original behavior
                    pass

            # Default to original behavior for all other cases
            return original_load_dataset(path, *args, **kwargs)

        # Apply the patch
        datasets.load_dataset = patched_load_dataset

        return True
    except ImportError as e:
        print(f"Error patching load_dataset: {e}")
        return False

# Apply the load_dataset patch if this module is imported
patched_load = patch_load_dataset()

if __name__ == "__main__":
    # Example usage of the patched datasets library
    import os

    # Set environment variables for the Gitea server
    os.environ["HF_ENDPOINT"] = "https://gitea.example.com"
    os.environ["HF_TOKEN"] = "your_gitea_api_token"

    try:
        # Import the patched datasets library
        from datasets import load_dataset, Dataset

        # Create a simple dataset
        data = {
            "text": ["Hello world", "How are you?", "I am fine"],
            "label": [0, 1, 1]
        }
        dataset = Dataset.from_dict(data)
        print(f"Dataset created with {len(dataset)} examples")

        # Push the dataset to the Gitea server
        dataset.push_to_hub("username/my-text-dataset")
        print("Dataset pushed to hub")

        # Load the dataset back
        loaded_dataset = load_dataset("username/my-text-dataset")
        print(f"Dataset loaded with {len(loaded_dataset['train'])} examples")
        print(f"First example: {loaded_dataset['train'][0]}")

    except ImportError:
        print("The datasets library is not installed. Skipping this example.")
        print("Install it with: pip install datasets")
