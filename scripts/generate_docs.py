import os
import shutil
import yaml

CACHE_DIR = "nmos_cache"
DOCS_DIR = "docs"

def safe_mkdir(path):
    os.makedirs(path, exist_ok=True)

def write_md(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def read_text(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def copy_md_files(src_dir, dest_dir):
    if not os.path.exists(src_dir):
        return
    safe_mkdir(dest_dir)
    for fname in os.listdir(src_dir):
        if fname.endswith(".md"):
            shutil.copy(os.path.join(src_dir, fname), os.path.join(dest_dir, fname))

def generate_spec_index(spec_dir, repo):
    readme_path = os.path.join(spec_dir, "README.md")
    spec_yml_path = os.path.join(spec_dir, "spec.yml")
    title = repo
    description = ""
    if os.path.exists(spec_yml_path):
        with open(spec_yml_path, "r") as f:
            try:
                spec = yaml.safe_load(f)
                title = spec.get("title", repo)
                description = spec.get("description", "")
            except Exception:
                pass
    elif os.path.exists(readme_path):
        content = read_text(readme_path)
        lines = content.splitlines()
        if lines and lines[0].startswith("#"):
            title = lines[0].lstrip("#").strip()
        description = " ".join(lines[1:4]).strip()
    overview = f"# {title}\n\n{description}\n\n"
    if os.path.exists(readme_path):
        overview += read_text(readme_path)
    return overview

def main():
    specs = [d for d in os.listdir(CACHE_DIR) if os.path.isdir(os.path.join(CACHE_DIR, d))]
    specs.sort()
    spec_links = []
    for repo in specs:
        spec_dir = os.path.join(CACHE_DIR, repo)
        out_dir = os.path.join(DOCS_DIR, repo)
        safe_mkdir(out_dir)

        # Overview/index.md
        index_md = generate_spec_index(spec_dir, repo)
        write_md(os.path.join(out_dir, "index.md"), index_md)
        spec_links.append(f"- [{repo.upper()}]({repo}/)\n")

        # docs/
        copy_md_files(os.path.join(spec_dir, "docs"), os.path.join(out_dir, "docs"))

        # APIs/
        copy_md_files(os.path.join(spec_dir, "APIs"), os.path.join(out_dir, "APIs"))
        # APIs/schemas/
        copy_md_files(os.path.join(spec_dir, "APIs/schemas"), os.path.join(out_dir, "APIs/schemas"))

        # examples/
        copy_md_files(os.path.join(spec_dir, "examples"), os.path.join(out_dir, "examples"))

    # Top-level overview
    overview_md = "# NMOS Specifications\n\n" + "".join(spec_links)
    write_md(os.path.join(DOCS_DIR, "nmos-specs.md"), overview_md)

if __name__ == "__main__":
    main()
