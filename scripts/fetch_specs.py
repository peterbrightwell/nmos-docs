import argparse
import os
from urllib.parse import urljoin

import requests
import yaml

NMOS_SPEC_LIST_URL = "https://raw.githubusercontent.com/AMWA-TV/nmos/main/spec_list.yml"
GITHUB_RAW_BASE = "https://raw.githubusercontent.com/AMWA-TV/{repo}/{branch}/"

CACHE_DIR = "nmos_cache"


def fetch_url(url):
    print(f"Fetching {url}")
    r = requests.get(url)
    if r.status_code == 200:
        return r.text
    else:
        print(f"Failed to fetch {url}: {r.status_code}")
        return None


def get_default_branch(repo):
    url = f"https://api.github.com/repos/AMWA-TV/{repo}"
    r = requests.get(url)
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


from urllib.parse import unquote


def fetch_and_save(repo, path, subpath="", branch="main"):
    url = GITHUB_RAW_BASE.format(repo=repo, branch=branch) + path
    content = fetch_url(url)
    if content:
        # Decode any URL-encoded characters in the filename
        filename = unquote(os.path.basename(path))
        save_file(os.path.join(CACHE_DIR, repo, subpath, filename), content)
        return content
    return None


def fetch_spec_repo(repo):
    print(f"\nProcessing repo: {repo}")
    repo_dir = os.path.join(CACHE_DIR, repo)
    os.makedirs(repo_dir, exist_ok=True)

    # Determine correct branch from spec.yml
    branch = get_default_branch(repo)
    print(f"Using branch '{branch}' for repo '{repo}'")

    # 1. Main README
    fetch_and_save(repo, "README.md", branch=branch)

    # 2. docs/README.md and referenced docs
    docs_readme = fetch_and_save(repo, "docs/README.md", "docs", branch=branch)
    if docs_readme:
        # Find markdown links in docs/README.md
        import re

        md_links = re.findall(r"\[.*?\]\(([^)]+\.md)\)", docs_readme)
        for md_file in md_links:
            fetch_and_save(repo, f"docs/{md_file}", "docs", branch=branch)

    # 3. APIs/ (RAML files)
    for apis_subdir in ["APIs", "API"]:
        url = f"https://api.github.com/repos/AMWA-TV/{repo}/contents/{apis_subdir}?ref={branch}"
        r = requests.get(url)
        if r.status_code == 200:
            for item in r.json():
                if item["name"].endswith(".raml"):
                    fetch_and_save(
                        repo,
                        f"{apis_subdir}/{item['name']}",
                        apis_subdir,
                        branch=branch,
                    )
                if item["type"] == "dir" and item["name"].lower() == "schemas":
                    # Fetch schemas
                    schemas_url = f"https://api.github.com/repos/AMWA-TV/{repo}/contents/{apis_subdir}/{item['name']}?ref={branch}"
                    r2 = requests.get(schemas_url)
                    if r2.status_code == 200:
                        for schema in r2.json():
                            if schema["name"].endswith(".json"):
                                fetch_and_save(
                                    repo,
                                    f"{apis_subdir}/{item['name']}/{schema['name']}",
                                    f"{apis_subdir}/schemas",
                                    branch=branch,
                                )

    # 4. examples/
    url = f"https://api.github.com/repos/AMWA-TV/{repo}/contents/examples?ref={branch}"
    r = requests.get(url)
    if r.status_code == 200:
        for item in r.json():
            if item["type"] == "file":
                fetch_and_save(
                    repo, f"examples/{item['name']}", "examples", branch=branch
                )


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
        fetch_spec_repo(repo)


import json


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
