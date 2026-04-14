# NMOS Documentation Generator

This repo includes Python scripts and a GitHub workflow to:
- Gets the list of NMOS specifications from <https://specs.amwa.tv/nmos>
- Gets the documentation for each specification
- Generates a navigation tree
- Uses Zensical to build a static site
- Deploy the generated site to GitHub Pages

Some AI was used to create the scripts.

## Usage

To run the documentation generator locally, you can use the following command:

```bash
brew install virtualenv  # or similar
virtualenv scripts/venv # or similar
source ./scripts/venv/bin activate # or similar
pip install zensical requests toml
python scripts/fetch_specs.py 
python scripts/generate_docs.py
python scripts/generate_nav.py
zensical serve
```
