import os
import re
from urllib.parse import unquote

import toml

DOCS_DIR = "docs"


def parse_readme_nav(readme_path, spec):
    with open(readme_path, encoding="utf-8") as f:
        lines = f.readlines()

    nav = []
    stack = [(0, nav)]

    for line in lines:
        # Heading (section)
        heading = re.match(r"^(#+)\s+(.*)", line)
        if heading:
            level = len(heading.group(1))
            title = heading.group(2).strip()
            # Pop stack to the right level
            while stack and stack[-1][0] >= level:
                stack.pop()
            parent = stack[-1][1]
            parent.append({title: []})
            stack.append((level, parent[-1][title]))
            continue

        # List item (link)
        item = re.match(r"^\s*-\s+\[([^\]]+)\]\(([^)]+)\)", line)
        if item:
            title = unquote(item.group(1).strip())
            path = unquote(item.group(2).strip())
            parent = stack[-1][1]
            if path.endswith(".md"):
                parent.append({title: f"{spec}/docs/{path}"})
            else:
                parent.append({title: []})
            continue

        # Sub-list item (indented, e.g. "  - [Title](Path)")
        subitem = re.match(r"^\s{2,}-\s+\[([^\]]+)\]\(([^)]+)\)", line)
        if subitem:
            title = unquote(subitem.group(1).strip())
            path = unquote(subitem.group(2).strip())
            parent = stack[-1][1]
            if path.endswith(".md"):
                parent.append({title: f"{spec}/docs/{path}"})
            else:
                parent.append({title: []})
            continue

    return nav


def build_nested_nav(spec_navs):
    # Map specs to display names
    SPEC_DISPLAY = {
        "is-04": "IS-04 Discovery",
        "is-05": "IS-05 Connection Management",
        "is-12": "IS-12 Control Protocol",
        "ms-05-01": "MS-05-01 Control Architecture",
        "ms-05-02": "MS-05-02 Control Framework",
        "bcp-002-01": "BCP-002-01 Natural Grouping",
        "bcp-002-02": "BCP-002-02 Asset Distinguishing Info",
        "bcp-008-01": "BCP-008-01 Receiver Status Monitoring",
        "bcp-008-02": "BCP-008-02 Sender Status Monitoring",
        # Add more as needed
    }
    GROUPS = {
        "NMOS Connect": ["is-04", "is-05", "bcp-002-01", "bcp-002-02"],
        "NMOS Control": ["is-12", "ms-05-01", "ms-05-02", "bcp-008-01", "bcp-008-02"],
        # Add more groups as needed
    }

    # Build grouped nav
    grouped = {}
    for group, specs in GROUPS.items():
        grouped[group] = []
        for spec in specs:
            if spec in spec_navs:
                display = SPEC_DISPLAY.get(spec, spec.upper())
                grouped[group].append({display: spec_navs[spec]})

    # Add any ungrouped specs at the end
    grouped["Other Specs"] = []
    for spec, nav in spec_navs.items():
        if not any(spec in specs for specs in GROUPS.values()):
            display = SPEC_DISPLAY.get(spec, spec.upper())
            grouped["Other Specs"].append({display: nav})

    # Build the final nav array
    nav = [
        {"NMOS Specs": "nmos-specs.md"},
        *([{group: entries} for group, entries in grouped.items() if entries]),
    ]
    return nav


def create_zensical_nav(spec_navs):
    # Build nested nav
    new_nav = build_nested_nav(spec_navs)

    # Pretty-print nav.toml with only [project] nav
    def toml_inline_array(obj, indent=0):
        IND = "  " * indent
        if isinstance(obj, list):
            items = []
            for item in obj:
                items.append(toml_inline_array(item, indent + 1))
            return "[\n" + ",\n".join(IND + "  " + i for i in items) + "\n" + IND + "]"
        elif isinstance(obj, dict):
            k, v = list(obj.items())[0]
            if isinstance(v, list):
                return f'{{ "{k}" = {toml_inline_array(v, indent + 1)} }}'
            else:
                return f'{{ "{k}" = "{v}" }}'
        else:
            import json

            return json.dumps(obj)

    with open("nav.toml", "w", encoding="utf-8") as f:
        f.write("[project]\n")
        f.write(f"nav = {toml_inline_array(new_nav)}\n")

    # Combine config.toml and nav.toml into zensical.toml
    def combine_configs():
        import re

        with open("config.toml", "r", encoding="utf-8") as f:
            config = f.read()
        with open("nav.toml", "r", encoding="utf-8") as f:
            nav = f.read()
        # Remove any [project] header from nav.toml to avoid duplication
        nav = re.sub(r"^\[project\]\s*", "", nav, flags=re.MULTILINE)
        # Insert nav after [project] in config.toml
        zensical = re.sub(r"(\[project\][^\[]*)", r"\1" + nav, config, count=1)
        with open("zensical.toml", "w", encoding="utf-8") as f:
            f.write(zensical)

    combine_configs()
    print("Wrote nav.toml and combined with config.toml into zensical.toml")


def main():
    spec_navs = {}
    for spec in os.listdir(DOCS_DIR):
        readme_path = os.path.join(DOCS_DIR, spec, "docs", "README.md")
        if os.path.exists(readme_path):
            nav = parse_readme_nav(readme_path, spec)
            if nav:
                spec_navs[spec] = nav

    if not spec_navs:
        print("No spec README.md navs found.")
        return

    create_zensical_nav(spec_navs)
    print("Created zensical.toml nav with spec docs.")


if __name__ == "__main__":
    main()
