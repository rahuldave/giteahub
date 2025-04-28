"""
Example usage of the Gitea to Hugging Face Hub adapter.

This script shows how to use the adapter as a drop-in replacement for huggingface_hub.
"""

import os
import sys
from pathlib import Path

# Import the adapter instead of huggingface_hub
import giteahub.gitea_huggingface_client as huggingface_hub
from giteahub.gitea_huggingface_client import HfApi, create_repo, hf_hub_download, snapshot_download

# Set environment variables for the Gitea server
os.environ["HF_ENDPOINT"] = "http://localhost:3000"
os.environ["HF_TOKEN"] = "82f3959223e7a14111e7ee531cdca7c28e60062d"

def example_usage_hf_api():
    """Example usage of the HfApi class."""
    print("=== HfApi Example ===")

    # Initialize the API
    api = HfApi()

    # Create a repository
    print("Creating a repository...")
    repo_info = api.create_repo(
        repo_id="rahuldave/my-model2",
        repo_type="model",
        private=False
    )
    print(f"Repository created: {repo_info}")

    # Upload a file
    print("Uploading a file...")
    with open("example.txt", "w") as f:
        f.write("This is an example file")

    commit_info = api.upload_file(
        path_or_fileobj="example.txt",
        path_in_repo="example.txt",
        repo_id="rahuldave/my-model2",
        commit_message="Add example file"
    )
    print(f"File uploaded: {commit_info}")

    # List models
    print("Listing models...")
    models = api.list_models(author="rahuldave", limit=5)
    print(f"Found {len(models)} models:")
    for model in models:
        print(f"  - {model['id']}")

    # Clean up
    os.remove("example.txt")

def example_usage_functions():
    """Example usage of the standalone functions."""
    print("=== Standalone Functions Example ===")

    # Create a repository
    print("Creating a repository...")
    repo_info = create_repo(
        repo_id="rahuldave/my-dataset",
        repo_type="dataset",
        private=True,
        exist_ok=True
    )
    print(f"Repository created: {repo_info}")

    # Create a test file
    print("Creating test files...")
    os.makedirs("test_data", exist_ok=True)
    with open("test_data/data.csv", "w") as f:
        f.write("id,value\n1,test1\n2,test2\n")
    with open("test_data/metadata.json", "w") as f:
        f.write('{"description": "Test dataset"}')

    # Upload the files
    api = HfApi()
    print("Uploading files...")
    commit_info = api.upload_folder(
        folder_path="test_data",
        repo_id="rahuldave/my-dataset",
        commit_message="Add dataset files"
    )
    print(f"Files uploaded: {commit_info}")

    # Download a single file
    print("Downloading a single file...")
    file_path = hf_hub_download(
        repo_id="rahuldave/my-dataset",
        filename="data.csv",
        local_dir="downloads"
    )
    print(f"File downloaded to: {file_path}")

    # Download the entire repository
    print("Downloading the entire repository...")
    repo_path = snapshot_download(
        repo_id="rahuldave/my-dataset",
        local_dir="full_download"
    )
    print(f"Repository downloaded to: {repo_path}")

    # Clean up
    import shutil
    shutil.rmtree("test_data", ignore_errors=True)
    shutil.rmtree("downloads", ignore_errors=True)
    shutil.rmtree("full_download", ignore_errors=True)

def example_with_datasets_library():
    """Example of using the adapter with the datasets library."""
    print("=== Datasets Library Example ===")

    try:
        from datasets import load_dataset, Dataset

        # Create a simple dataset
        print("Creating a dataset...")
        data = {
            "text": ["Hello world", "How are you?", "I am fine"],
            "label": [0, 1, 1]
        }
        dataset = Dataset.from_dict(data)
        print(f"Dataset created with {len(dataset)} examples")

        # Push the dataset to the Gitea server
        print("Pushing dataset to hub...")
        dataset.push_to_hub("rahuldave/my-text-dataset")
        print("Dataset pushed to hub")

        # Load the dataset back
        print("Loading dataset from hub...")
        loaded_dataset = load_dataset("rahuldave/my-text-dataset")
        print(f"Dataset loaded with {len(loaded_dataset['train'])} examples")
        print(f"First example: {loaded_dataset['train'][0]}")

    except ImportError:
        print("The datasets library is not installed. Skipping this example.")
        print("Install it with: pip install datasets")

if __name__ == "__main__":
    # Check if the environment variables are set
    if not os.environ.get("HF_ENDPOINT") or not os.environ.get("HF_TOKEN"):
        print("Please set the HF_ENDPOINT and HF_TOKEN environment variables")
        sys.exit(1)

    # Run the examples
    example_usage_hf_api()
    print()
    #example_usage_functions()
    #print()

    # example_with_datasets_library()
