# Contributing to ODPS Python Library

Thank you for your interest in contributing to the ODPS Python Library! This document provides guidelines and information for contributors.

## 📋 Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Contributing Guidelines](#contributing-guidelines)
- [Code Style](#code-style)
- [Testing](#testing)
- [Documentation](#documentation)
- [Submitting Changes](#submitting-changes)
- [Release Process](#release-process)

## 🤝 Code of Conduct

This project adheres to a code of conduct adapted from the [Contributor Covenant](https://www.contributor-covenant.org/). By participating, you are expected to uphold this code.

### Our Standards

- **Be respectful**: Treat all community members with respect and kindness
- **Be inclusive**: Welcome newcomers and encourage diverse participation
- **Be constructive**: Provide helpful feedback and constructive criticism
- **Be professional**: Maintain professional conduct in all interactions

## 🚀 Getting Started

### Prerequisites

- Python 3.8 or higher
- Git
- Basic understanding of ODPS v4.1 specification
- Familiarity with Python development tools

### Areas for Contribution

We welcome contributions in several areas:

- **Bug fixes**: Help resolve issues and improve reliability
- **New features**: Implement enhancements following ODPS specification
- **Documentation**: Improve guides, examples, and API documentation
- **Testing**: Add test cases and improve coverage
- **Performance**: Optimize algorithms and data structures
- **Standards compliance**: Ensure adherence to international standards
- **Examples**: Create tutorials and usage examples

## 🛠️ Development Setup

### 1. Fork and Clone

```bash
# Fork the repository on GitHub, then clone your fork
git clone https://github.com/accenture/odps-python.git
cd odps-python
```

### 2. Set Up Development Environment

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install development dependencies
pip install -e ".[dev]"

# Install pre-commit hooks (optional but recommended)
pip install pre-commit
pre-commit install
```

### 3. Verify Setup

```bash
# Run tests to ensure everything works
python -m pytest tests/ -v

# Check code quality
python -m flake8 odps/
python -m mypy odps/

# Run example scripts
python examples/basic_usage.py
python examples/advanced_features.py
```

## 📝 Contributing Guidelines

### Issue Reporting

Before creating a new issue:

1. **Search existing issues** to avoid duplicates
2. **Use issue templates** when available
3. **Provide detailed information**:
   - Python version and environment
   - ODPS library version
   - Steps to reproduce the issue
   - Expected vs. actual behavior
   - Code examples or stack traces

### Feature Requests

For new features:

1. **Check ODPS v4.1 specification** for compliance requirements
2. **Discuss in GitHub Discussions** before implementing large features
3. **Create detailed proposals** including:
   - Use case and motivation
   - Proposed API changes
   - Implementation considerations
   - Backward compatibility impact

### Pull Request Process

1. **Create feature branch** from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make focused changes**:
   - Keep PRs small and focused on single features/fixes
   - Follow existing code patterns and architecture
   - Maintain backward compatibility when possible

3. **Update documentation**:
   - Add/update docstrings for new/modified functions
   - Update README.md if needed
   - Add examples for new features

4. **Add tests**:
   - Write unit tests for new functionality
   - Ensure all existing tests still pass
   - Aim for high test coverage

5. **Commit with clear messages**:
   ```bash
   git commit -m "feat: add support for SLA profiles"
   git commit -m "fix: resolve camelCase conversion issue"
   git commit -m "docs: update API documentation for new methods"
   ```

6. **Push and create PR**:
   ```bash
   git push origin feature/your-feature-name
   # Create PR on GitHub with detailed description
   ```

## 🎨 Code Style

### Python Code Standards

We follow PEP 8 with some specific guidelines:

#### Formatting
```bash
# Use Black for code formatting
python -m black odps/ examples/ tests/

# Line length: 88 characters (Black default)
# Use double quotes for strings
# 4 spaces for indentation
```

#### Type Hints
```python
# Always use type hints
def process_data(data: Dict[str, Any], options: Optional[List[str]] = None) -> bool:
    """Process data with optional configuration."""
    return True

# Use Union for multiple types
from typing import Union
def handle_input(value: Union[str, int, List[str]]) -> str:
    """Handle various input types."""
```

#### Documentation
```python
def validate_component(component: Any, rules: List[ValidationRule]) -> List[str]:
    """
    Validate a component against multiple rules.
    
    Args:
        component: The component to validate
        rules: List of validation rules to apply
        
    Returns:
        List of validation error messages (empty if valid)
        
    Raises:
        ODPSValidationError: If component is None
        
    Example:
        >>> rules = [RequiredFieldValidator(), FormatValidator()]
        >>> errors = validate_component(my_component, rules)
        >>> if errors:
        ...     print(f"Validation failed: {errors}")
    """
```

#### Imports
```python
# Standard library imports first
import json
import time
from typing import Dict, List, Optional, Any

# Third-party imports
import yaml
from pycountry import countries

# Local imports
from .models import ProductDetails, DataHolder
from .exceptions import ODPSValidationError
from .protocols import ValidatableProtocol
```

### Architecture Principles

#### Modular Design
- Keep components loosely coupled
- Use dependency injection where appropriate
- Follow single responsibility principle

#### Performance
- Use `__slots__` for data classes when beneficial
- Implement caching for expensive operations
- Profile code changes for performance impact

#### Error Handling
- Use specific exception types
- Provide detailed error context
- Follow the established exception hierarchy

## 🧪 Testing

### Test Structure

```
tests/
├── unit/
│   ├── test_core.py
│   ├── test_models.py
│   ├── test_validation.py
│   └── test_protocols.py
├── integration/
│   ├── test_full_workflow.py
│   └── test_standards_compliance.py
├── performance/
│   └── test_caching.py
└── fixtures/
    ├── valid_documents/
    └── invalid_documents/
```

### Writing Tests

```python
import pytest
from open_data_products.odps import OpenDataProduct, ProductDetails
from open_data_products.odps.exceptions import ODPSValidationError

class TestProductValidation:
    """Test suite for product validation."""
    
    def test_valid_product_creation(self):
        """Test creating a valid product."""
        details = ProductDetails(
            name="Test Product",
            product_id="test-001",
            visibility="public",
            status="draft",
            type="dataset"
        )
        product = OpenDataProduct(details)
        
        assert product.validate() is True
        assert product.is_valid is True
        assert product.validation_errors == []
    
    def test_invalid_product_raises_error(self):
        """Test that invalid product raises appropriate error."""
        details = ProductDetails(
            name="",  # Invalid empty name
            product_id="test-001",
            visibility="public",
            status="draft",
            type="dataset"
        )
        product = OpenDataProduct(details)
        
        with pytest.raises(ODPSValidationError) as exc_info:
            product.validate()
        
        assert "name" in str(exc_info.value).lower()
    
    @pytest.mark.parametrize("status", [
        "announcement", "draft", "development", "testing",
        "acceptance", "production", "sunset", "retired"
    ])
    def test_valid_status_values(self, status):
        """Test all valid status values are accepted."""
        details = ProductDetails(
            name="Test Product",
            product_id="test-001",
            visibility="public",
            status=status,
            type="dataset"
        )
        product = OpenDataProduct(details)
        assert product.validate() is True
```

### Running Tests

```bash
# Run all tests
python -m pytest

# Run with coverage
python -m pytest --cov=odps --cov-report=html

# Run specific test file
python -m pytest tests/unit/test_core.py -v

# Run performance tests
python -m pytest tests/performance/ -v
```

## 📚 Documentation

### Docstring Standards

Use Google-style docstrings:

```python
def complex_function(param1: str, param2: Optional[int] = None) -> Dict[str, Any]:
    """
    Brief description of the function.
    
    Longer description if needed, explaining the purpose and behavior
    in more detail.
    
    Args:
        param1: Description of the first parameter
        param2: Description of the optional second parameter
        
    Returns:
        Dictionary containing the results with structure:
        {
            'status': bool,
            'data': Any,
            'errors': List[str]
        }
        
    Raises:
        ODPSValidationError: When validation fails
        ValueError: When input parameters are invalid
        
    Example:
        >>> result = complex_function("test", 42)
        >>> print(result['status'])
        True
        
    Note:
        This function is optimized for performance with internal caching.
    """
```

### Documentation Updates

When adding new features:

1. **Update API documentation** in `docs/API.md`
2. **Add examples** to `examples/` directory
3. **Update README.md** if public API changes
4. **Update CHANGELOG.md** with your changes

## 📤 Submitting Changes

### Pull Request Checklist

Before submitting a pull request:

- [ ] Code follows style guidelines
- [ ] All tests pass locally
- [ ] New tests added for new functionality
- [ ] Documentation updated
- [ ] CHANGELOG.md updated
- [ ] No merge conflicts with main branch
- [ ] PR description clearly explains changes

### PR Description Template

```markdown
## Description
Brief description of changes made.

## Type of Change
- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update

## Testing
- [ ] New tests added
- [ ] All existing tests pass
- [ ] Manual testing performed

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] CHANGELOG.md updated
```

### Review Process

1. **Automated checks** run on all PRs
2. **Code review** by maintainers
3. **Discussion and iteration** as needed
4. **Approval and merge** by maintainers

## 🚢 Release Process

### Versioning

We follow [Semantic Versioning](https://semver.org/):

- **MAJOR**: Breaking changes
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes (backward compatible)

### Release Steps

1. **Update version** in `odps/__init__.py`
2. **Update CHANGELOG.md** with new version
3. **Create release tag**:
   ```bash
   git tag -a v0.7.0 -m "Release version 0.7.0"
   git push origin v0.7.0
   ```
4. **Build and publish** to PyPI (maintainers only)

## 🙋 Getting Help

- **GitHub Issues**: For bugs and feature requests
- **GitHub Discussions**: For questions and general discussion
- **Documentation**: Check README.md and docs/ directory
- **Examples**: Review examples/ directory for usage patterns

## 📜 License

By contributing to this project, you agree that your contributions will be licensed under the same Apache License 2.0 that covers the project.

---

Thank you for contributing to the ODPS Python Library! Your help makes this project better for everyone. 🎉
