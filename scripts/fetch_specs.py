import argparse
import json
import os
from urllib.parse import unquote, urljoin

import requests
import yaml

NMOS_SPEC_LIST_URL = "https://raw.githubusercontent.com/AMWA-TV/nmos/main/spec_list.yml"
GITHUB_RAW_BASE = "https://raw.githubusercontent.com/AMWA-TV/{repo}/{branch}/"

CACHE_DIR = "nmos_cache"
SHA_CACHE_FILE = os.path.join(CACHE_DIR, "sha_cache.json")

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
if not GITHUB_TOKEN:
    raise RuntimeError(
        "GITHUB_TOKEN environment variable is not set. "
        "Please set it to a GitHub Personal Access Token to avoid API rate limits."
    )


def github_headers():
    headers = {}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
    headers["Accept"] = "application/vnd.github.v3+json"
    return headers


def load_sha_cache():
    if os.path.exists(SHA_CACHE_FILE):
        with open(SHA_CACHE_FILE, "r") as f:
            return json.load(f)
    return {}


def save_sha_cache(cache):
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(SHA_CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)


def fetch_url(url):
    print(f"Fetching {url}")
    r = requests.get(url, headers=github_headers())
    if r.status_code == 200:
        return r.text
    else:
        print(f"Failed to fetch {url}: {r.status_code}")
        return None


def get_default_branch(repo):
    url = f"https://api.github.com/repos/AMWA-TV/{repo}"
    r = requests.get(url, headers=github_headers())
    if r.status_code == 200:
        data = r.json()
        return data.get("default_branch", "main")
    else:
        print(f"Failed to get default branch for {repo}, using 'main'")
        return "main"


def save_file(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


# from urllib.parse import unquote  # Already imported above


def get_repo_tree(repo, branch):
    # Get the commit SHA for the branch
    branch_url = f"https://api.github.com/repos/AMWA-TV/{repo}/branches/{branch}"
    branch_resp = requests.get(branch_url, headers=github_headers())
    if branch_resp.status_code != 200:
        raise Exception(f"Failed to get branch info for {repo}:{branch}")
    commit_sha = branch_resp.json()["commit"]["sha"]

    # Get the full tree
    tree_url = f"https://api.github.com/repos/AMWA-TV/{repo}/git/trees/{commit_sha}?recursive=1"
    tree_resp = requests.get(tree_url, headers=github_headers())
    if tree_resp.status_code != 200:
        raise Exception(f"Failed to get tree for {repo}:{branch}")
    tree = tree_resp.json()["tree"]
    # Map: path -> sha
    return {entry["path"]: entry["sha"] for entry in tree if entry["type"] == "blob"}


def fetch_spec_repo(repo, sha_cache):
    print(f"\nProcessing repo: {repo}")
    repo_dir = os.path.join(CACHE_DIR, repo)
    os.makedirs(repo_dir, exist_ok=True)

    branch = get_default_branch(repo)
    print(f"Using branch '{branch}' for repo '{repo}'")

    # Get the full file tree (all SHAs in one go)
    tree = get_repo_tree(repo, branch)

    def fetch_if_needed(path, subpath=""):
        cache_key = f"{repo}/{path}"
        remote_sha = tree.get(path)
        cached_sha = sha_cache.get(cache_key)
        if not remote_sha:
            print(f"File {path} not found in repo tree, skipping.")
            return None
        if cached_sha == remote_sha:
            print(f"Skipping {cache_key} (SHA unchanged)")
            return None
        url = GITHUB_RAW_BASE.format(repo=repo, branch=branch) + path
        content = fetch_url(url)
        if content:
            filename = unquote(os.path.basename(path))
            save_file(os.path.join(CACHE_DIR, repo, subpath, filename), content)
            sha_cache[cache_key] = remote_sha
            return content
        return None

    # 1. Main README
    fetch_if_needed("README.md")

    # 2. docs/README.md and referenced docs
    docs_readme = fetch_if_needed("docs/README.md", "docs")
    if docs_readme:
        import re

        md_links = re.findall(r"\[.*?\]\(([^)]+\.md)\)", docs_readme)
        for md_file in md_links:
            fetch_if_needed(f"docs/{md_file}", "docs")

    # 3. APIs/ (RAML files and schemas)
    for apis_subdir in ["APIs", "API"]:
        for path in tree:
            if path.startswith(f"{apis_subdir}/") and path.endswith(".raml"):
                fetch_if_needed(path, apis_subdir)
            if path.startswith(f"{apis_subdir}/schemas/") and path.endswith(".json"):
                fetch_if_needed(path, f"{apis_subdir}/schemas")

    # 4. examples/
    for path in tree:
        if path.startswith("examples/") and "/" not in path[len("examples/") :]:
            fetch_if_needed(path, "examples")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Fetch NMOS specs and cache them locally."
    )
    parser.add_argument(
        "--specs",
        type=str,
        help="Comma-separated list of spec repo names to process (e.g. is-05,is-08)",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    sha_cache = load_sha_cache()
    if args.specs:
        repos = [
            repo.strip().lower().replace("_", "-").replace(" ", "-")
            for repo in args.specs.split(",")
            if repo.strip()
        ]
    else:
        # Step 1: Download spec_list.yml
        spec_list_content = fetch_url(NMOS_SPEC_LIST_URL)
        spec_list = yaml.safe_load(spec_list_content)
        print(spec_list)  # Debug: See the structure

        if isinstance(spec_list, list):
            # Normalize repo names: lowercase and replace underscores/spaces with hyphens
            repos = [
                repo.lower().replace("_", "-").replace(" ", "-")
                for repo in spec_list
                if isinstance(repo, str)
            ]
        else:
            raise Exception(
                "spec_list.yml structure is not as expected. Please check the file format."
            )

    # Step 2: For each repo, fetch content
    for repo in repos:
        fetch_spec_repo(repo, sha_cache)
    save_sha_cache(sha_cache)


def build_specs_summary():
    summary = []
    for repo in os.listdir(CACHE_DIR):
        repo_dir = os.path.join(CACHE_DIR, repo)
        if not os.path.isdir(repo_dir):
            continue
        spec_yml = os.path.join(repo_dir, "spec.yml")
        readme = os.path.join(repo_dir, "README.md")
        title = repo
        description = ""
        if os.path.exists(spec_yml):
            with open(spec_yml, "r") as f:
                try:
                    spec = yaml.safe_load(f)
                    title = spec.get("title", repo)
                    description = spec.get("description", "")
                except Exception:
                    pass
        elif os.path.exists(readme):
            with open(readme, "r") as f:
                lines = f.readlines()
                if lines and lines[0].startswith("#"):
                    title = lines[0].lstrip("#").strip()
                description = " ".join(lines[1:4]).strip()
        summary.append({"repo": repo, "title": title, "description": description})
    with open(os.path.join(CACHE_DIR, "specs.json"), "w") as f:
        json.dump(summary, f, indent=2)


if __name__ == "__main__":
    main()
    build_specs_summary()
