"""
CONTRIBUTING.md - Contribution guidelines for NanoBio Studio Backend.
"""

# Contributing to NanoBio Studio Backend

## Code Standards

### Python Style
- Follow PEP 8
- Use `black` for formatting: `black nanobio_studio/ tests/`
- Use `ruff` for linting: `ruff check nanobio_studio/`
- Type hints required for all functions

### Documentation
- Module docstrings for all files
- Function/method docstrings (following Google style)
- Clear comments for complex logic
- Update README for user-facing changes

### Testing
- Write tests for all new features
- Maintain >80% code coverage
- Run tests: `pytest tests/`
- All tests must pass before PR submission

## Commit Messages

Format:
```
<type>: <short description>

<detailed explanation if needed>
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `refactor`: Code reorganization
- `test`: Testing additions
- `ci`: CI/CD changes

Example:
```
feat: Add custom QC rule support

Allows users to define custom validation rules by subclassing QCRule.
Implement example rule for pH range validation.
```

## Pull Requests

1. Create feature branch: `git checkout -b feature/your-feature`
2. Make changes with tests
3. Ensure all tests pass: `pytest`
4. Format code: `black nanobio_studio/`
5. Lint: `ruff check nanobio_studio/`
6. Push and create PR

## Questions?

Contact: info@expertsgroup.me
