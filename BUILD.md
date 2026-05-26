# Building and Distributing Open Data Products Python SDK

This guide explains how to package the Open Data Products Python SDK as a wheel file for distribution.

## Quick Reference

```bash
# Install build tools
pip install build

# Build the package with minimal output
python -m build --quiet

# Install locally for testing
pip install dist/open_data_products-0.2.0-py3-none-any.whl

# Test functionality
python -c "import open_data_products; print(open_data_products.__version__)"
```

## Prerequisites

Install build tools:
```bash
pip install build twine
```

## Method 1: Using `build` (Recommended - PEP 517 compliant)

The modern way using `pyproject.toml`:

```bash
# Install build dependencies
pip install build

# Build the package with minimal output (creates both wheel and source distribution)
python -m build --quiet

# This creates files in dist/:
# - open_data_products-0.2.0-py3-none-any.whl (wheel file)
# - open_data_products-0.2.0.tar.gz (source distribution)
```

## Method 2: Build with specific options

```bash
# Build with clean environment
python -m build --wheel --outdir dist/

# Build source distribution only
python -m build --sdist

# Build with verbose output
python -m build --wheel --verbose
```


## Installing the Built Wheel

After building, install the wheel locally for testing:

```bash
# Install the built wheel
pip install dist/open_data_products-0.2.0-py3-none-any.whl

# Or install in development mode with extras
pip install -e ".[dev]"
```

## Verifying the Package

Test the installed package:

```python
import open_data_products
print(open_data_products.__version__)  # Should print 0.2.0

from open_data_products.odps import OpenDataProduct, ODPSValidator
from open_data_products.odps.models import ProductDetails

# Test basic functionality
product = ProductDetails(
    name="Test", 
    product_id="test-001",
    visibility="public",
    status="production", 
    type="dataset"
)
odp = OpenDataProduct(product)
odp.validate()
print("✓ Package working correctly")
```

## Publishing to PyPI

### Test PyPI (Recommended for testing)

```bash
# Upload to Test PyPI first
python -m twine upload --repository testpypi dist/*

# Install from Test PyPI to verify
pip install --index-url https://test.pypi.org/simple/ odps-python
```

### Production PyPI

```bash
# Upload to production PyPI
python -m twine upload dist/*

# Configure credentials first:
# Create ~/.pypirc with your API tokens
```

## Package Structure

The built wheel contains:
```
odps_python-0.2.0-py3-none-any.whl
├── odps/
│   ├── __init__.py          # Package entry point with version
│   ├── core.py              # Main OpenDataProduct class
│   ├── models.py            # Data models for ODPS components  
│   └── validators.py        # International standards validation
├── odps_python-0.2.0.dist-info/
│   ├── METADATA             # Package metadata
│   ├── WHEEL                # Wheel metadata
│   ├── RECORD               # File checksums
│   └── top_level.txt        # Top-level packages
```

## Build Configuration

### pyproject.toml (Modern)
- Defines build system requirements
- Specifies metadata and dependencies
- Configures development tools (black, mypy)
- PEP 517/518 compliant


## Troubleshooting

### Common Issues

1. **Import errors during build**:
   ```bash
   # Ensure all dependencies are installed
   pip install -r requirements.txt
   ```

2. **Version conflicts**:
   ```bash
   # Clean previous builds
   rm -rf build/ dist/ *.egg-info/
   python -m build --quiet
   ```

3. **Missing files in wheel**:
   ```bash
   # Check MANIFEST.in or pyproject.toml package discovery
   python -m build --verbose
   ```

4. **Upload failures**:
   ```bash
   # Check credentials and package name availability
   python -m twine check dist/*
   ```

## Distribution Checklist

- [ ] Version number updated in `__init__.py`
- [ ] CHANGELOG.md updated with release notes
- [ ] README.md reflects current features
- [ ] All tests passing
- [ ] Dependencies properly specified
- [ ] Built wheel installs and imports correctly
- [ ] Uploaded to Test PyPI successfully
- [ ] Documentation is current

## Automated Building

For CI/CD, add to your workflow:

```yaml
# .github/workflows/build.yml
name: Build and Test
on: [push, pull_request]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: 3.9
    - name: Install dependencies
      run: |
        pip install build twine
        pip install -e ".[dev]"
    - name: Build package
      run: python -m build --quiet
    - name: Check package
      run: python -m twine check dist/*
```
