## Huggingface Hub has a local cache

The new cache file layout looks like this:

The cache directory contains one subfolder per repo_id (namespaced by repo type)
inside each repo folder:
refs is a list of the latest known revision => commit_hash pairs
blobs contains the actual file blobs (identified by their git-sha or sha256, depending on whether they’re LFS files or not)
snapshots contains one subfolder per commit, each “commit” contains the subset of the files that have been resolved at that particular commit. Each filename is a symlink to the blob at that particular commit.

```
Copied
[  96]  .
└── [ 160]  models--julien-c--EsperBERTo-small
    ├── [ 160]  blobs
    │   ├── [321M]  403450e234d65943a7dcf7e05a771ce3c92faa84dd07db4ac20f592037a1e4bd
    │   ├── [ 398]  7cb18dc9bafbfcf74629a4b760af1b160957a83e
    │   └── [1.4K]  d7edf6bd2a681fb0175f7735299831ee1b22b812
    ├── [  96]  refs
    │   └── [  40]  main
    └── [ 128]  snapshots
        ├── [ 128]  2439f60ef33a0d46d85da5001d52aeda5b00ce9f
        │   ├── [  52]  README.md -> ../../blobs/d7edf6bd2a681fb0175f7735299831ee1b22b812
        │   └── [  76]  pytorch_model.bin -> ../../blobs/403450e234d65943a7dcf7e05a771ce3c92faa84dd07db4ac20f592037a1e4bd
        └── [ 128]  bbc77c8132af1cc5cf678da3f1ddf2de43606d48
            ├── [  52]  README.md -> ../../blobs/7cb18dc9bafbfcf74629a4b760af1b160957a83e
            └── [  76]  pytorch_model.bin -> ../../blobs/403450e234d65943a7dcf7e05a771ce3c92faa84dd07db4ac20f592037a1e4bd
```

If local_dir is provided, the file structure from the repo will be replicated in this location. When using this option, the cache_dir will not be used and a .cache/huggingface/ folder will be created at the root of local_dir to store some metadata related to the downloaded files. While this mechanism is not as robust as the main cache-system, it’s optimized for regularly pulling the latest version of a repository.

## Gitea to Hugging Face Hub Adapter

This library provides an adapter to use Gitea as a backend for Hugging Face Hub functionality. It implements API-compatible replacements for the huggingface_hub library, allowing you to use Gitea as a drop-in replacement for the Hugging Face Hub.

## Overview

The adapter allows you to:

1. Use Gitea as a backend for hosting models and datasets
2. Work with the Hugging Face Hub API interface
3. Integrate with the datasets and transformers libraries
4. Perform common operations like uploading/downloading files, creating repositories, etc.

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/gitea-huggingface-adapter.git
cd gitea-huggingface-adapter

# Install the package
pip install -e .
```

## Usage

### Basic Usage

```python
import os
from gitea_huggingface_client import HfApi, create_repo, hf_hub_download

# Set environment variables for the Gitea server
os.environ["HF_ENDPOINT"] = "https://gitea.example.com"
os.environ["HF_TOKEN"] = "your_gitea_api_token"

# Create a repository
api = HfApi()
repo_info = api.create_repo(
    repo_id="username/my-model",
    repo_type="model",
    private=False
)

# Upload a file
api.upload_file(
    path_or_fileobj="model.bin",
    path_in_repo="model.bin",
    repo_id="username/my-model",
    commit_message="Upload model file"
)

# Download a file
file_path = hf_hub_download(
    repo_id="username/my-model",
    filename="model.bin"
)
```

### Patching the datasets Library

The adapter includes functionality to patch the `datasets` library to use Gitea as a backend:

```python
# Import the patching module before importing datasets
import gitea_datasets_integration

# Now import datasets with Gitea support
from datasets import load_dataset, Dataset

# Create a dataset
data = {
    "text": ["Hello world", "How are you?", "I am fine"],
    "label": [0, 1, 1]
}
dataset = Dataset.from_dict(data)

# Push to Gitea
dataset.push_to_hub("username/my-dataset")

# Load from Gitea
loaded_dataset = load_dataset("username/my-dataset")
```

## API Reference

The adapter implements the following huggingface_hub API functions:

### HfApi Class

- `create_repo` - Create a new repository
- `delete_repo` - Delete a repository
- `upload_file` - Upload a file to a repository
- `upload_folder` - Upload a folder to a repository
- `create_commit` - Create a commit with multiple file operations
- `model_info` - Get information about a model repository
- `list_models` - List models available on the server
- `list_datasets` - List datasets available on the server

### Standalone Functions

- `create_repo` - Create a new repository
- `hf_hub_download` - Download a file from a repository
- `snapshot_download` - Download the whole repository

## Current Limitations

This initial implementation has the following limitations:

1. **No LFS support yet** - Large files are stored directly in Git without LFS
2. **Limited API coverage** - Not all huggingface_hub functions are implemented
3. **No file preview functionality** - Unlike the Hugging Face Hub, file previews are not supported
4. **Reduced search capabilities** - Search functionality is more limited than on the Hugging Face Hub

## Roadmap

Future improvements planned for this adapter:

1. Add Git LFS support for large file storage
2. Implement model versioning
3. Add support for Spaces (web applications)
4. Improve search functionality
5. Add support for more huggingface_hub functions

## License

This project is licensed under the MIT License - see the LICENSE file for details.
