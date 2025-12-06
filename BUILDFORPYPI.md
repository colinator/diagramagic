# Build and Publish to PyPI (v0.1.3)

## Prerequisites
- Python 3.9+
- Rust toolchain (rustc + cargo)
- Virtual environment activated
- `pip install -r dev-requirements.txt` (includes maturin, twine, Pillow)

---

## Distribution Strategy

Choose **ONE** approach:

### Option A: Source-only (RECOMMENDED)
- Simpler - no multi-platform builds needed
- Users must have Rust installed
- Users build extension during `pip install` (~30-60 seconds)

### Option B: Platform-specific wheels
- Users on your platform don't need Rust (faster install)
- You must build on multiple platforms for full coverage
- More complex release process

---

## Option A: Source-Only Distribution

### Commands:
```bash
# 0. Sync documentation to bundled data/ directory
cp AGENTS.md PROJECTSPEC.md README.md src/diagramagic/data/

# 1. Clean
rm -rf dist/ target/

# 2. Build source distribution only
maturin sdist

# 3. Collect to dist/
mkdir -p dist
cp target/wheels/*.tar.gz dist/

# 4. Check
twine check dist/*

# 5. Upload to PyPI (only the .tar.gz)
twine upload dist/*.tar.gz
```

**Done!** Users will compile the Rust extension during installation.

---

## Option B: Platform-Specific Wheels

Build both wheel (for your platform) and sdist (fallback for other platforms).

### Commands:
```bash
# 0. Sync documentation to bundled data/ directory
cp AGENTS.md PROJECTSPEC.md README.md src/diagramagic/data/

# 1. Clean
rm -rf dist/ target/

# 2. Build wheel for current platform
maturin build --release --locked

# 3. Build source distribution
maturin sdist

# 4. Collect to dist/
mkdir -p dist
cp target/wheels/* dist/

# 5. Check
twine check dist/*

# 6. Upload to PyPI (both .whl and .tar.gz)
twine upload dist/*
```

**Result**:
- Users on your platform get pre-built wheel (fast, no Rust needed)
- Users on other platforms build from sdist (slow, needs Rust)

**For full coverage**, repeat step 2 on:
- macOS (Intel + ARM)
- Linux (x86_64, manylinux container recommended)
- Windows (x86_64)

Or use GitHub Actions for automated multi-platform builds.

---

## Notes

- **Version**: Set in `pyproject.toml` (currently 0.1.2)
- **API Token**: Get from https://pypi.org/manage/account/token/
  - Use: `twine upload --username __token__ --password pypi-...`
- **TestPyPI**: Test before production
  - `twine upload --repository testpypi dist/*`
  - `pip install --index-url https://test.pypi.org/simple/ diagramagic`
- **Verify**: After upload, test in fresh environment:
  ```bash
  pip install diagramagic==0.1.3
  diagramagic --cheatsheet
  ```
