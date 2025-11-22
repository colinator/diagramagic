# Building diagramagic from source (offline-friendly)

These steps build the project from the local working tree without needing to pull packages from PyPI, as long as you have the dependencies available locally.

## Prereqs
- Python 3.9+ and `pip`
- Rust toolchain with Cargo (`rustup` works)
- Recommended (online): install `dev-requirements.txt` for maturin/Pillow/build tools:
  ```bash
  pip install -r dev-requirements.txt
  ```
- Offline option: place wheels/sdists for `Pillow>=10`, `maturin>=1.4` in a directory and use `--no-index --find-links`.

### Install Rust (rustc + cargo)
- Recommended: `curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh`
- Or with a package manager:
  - macOS (Homebrew): `brew install rustup-init` then `rustup-init`
  - Debian/Ubuntu: `sudo apt-get install rustc cargo` (versions may lag)
  - Windows: https://win.rustup.rs

## Setup a virtualenv
```bash
python -m venv .venv
source .venv/bin/activate  # or Scripts\\activate on Windows
```

## Install Python deps from local artifacts
If you are offline, point `--find-links` to a directory where you’ve placed the wheels/sdists for Pillow and maturin:
```bash
pip install --no-index --find-links /path/to/wheels pillow maturin
```

## Build and install the extension + package
Use maturin to compile the bundled resvg-based extension and install the Python package from the current tree:
```bash
maturin develop --release --locked
```
Alternatively, to produce distributable wheels:
```bash
maturin build --release --locked  # wheels land in target/wheels/
```

## Run tests/fixtures
After the extension is built/installed:
```bash
python tests/run_tests.py
```
This regenerates SVG fixtures next to their `.svg++` inputs.
