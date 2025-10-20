# Contributing to Google Drive RAG System

Thank you for your interest in contributing to the Google Drive RAG System! This document provides guidelines for contributing to the project.

## Code of Conduct

By participating in this project, you agree to abide by our Code of Conduct:

- Be respectful and inclusive
- Welcome newcomers and help them learn
- Focus on constructive feedback
- Respect different viewpoints and experiences
- Show empathy towards other community members

## How to Contribute

### Reporting Issues

Before creating a new issue, please:

1. **Search existing issues** to avoid duplicates
2. **Check the troubleshooting section** in README.md
3. **Provide detailed information** including:
   - Python version
   - Operating system
   - Ollama version
   - Full error messages
   - Steps to reproduce

### Suggesting Features

We welcome feature suggestions! Please:

1. Check existing issues for similar requests
2. Clearly describe the feature and its benefits
3. Provide use cases and examples
4. Consider the scope and complexity

### Pull Requests

#### Before You Start

1. Fork the repository
2. Create a feature branch from `main`
3. Ensure you can run the application locally

#### Development Setup

```bash
# Clone your fork
git clone https://github.com/milo/google-drive-rag.git
cd google-drive-rag

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows

# Install development dependencies
pip install -r requirements.txt
pip install pytest black flake8 mypy pre-commit

# Install pre-commit hooks
pre-commit install
```

#### Coding Standards

**Python Style:**
- Follow PEP 8
- Use Black for code formatting: `black week5_assignment.py`
- Use type hints where appropriate
- Maximum line length: 88 characters

**Code Quality:**
- Run linting: `flake8 week5_assignment.py`
- Run type checking: `mypy week5_assignment.py --ignore-missing-imports`
- Ensure imports are organized and unused imports removed

**Documentation:**
- Add docstrings for new functions and classes
- Update README.md if adding new features
- Include inline comments for complex logic

#### Testing

**Manual Testing:**
1. Test basic functionality:
   - Authentication with Google Drive
   - File processing
   - Query functionality
   - Web interface

2. Test edge cases:
   - Encrypted PDFs
   - Large files
   - Empty documents
   - Network interruptions

**Automated Testing:**
```bash
# Run basic import tests
python -c "from week5_assignment import GoogleDriveRAG, FileTracker"

# Run any existing tests
pytest
```

#### Commit Guidelines

**Commit Message Format:**
```
type(scope): brief description

Optional longer description explaining the change
and its motivation.

Fixes #123
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code restructuring without changing functionality
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

**Examples:**
```
feat(auth): add support for service account authentication
fix(pdf): handle encrypted PDF files gracefully
docs(readme): update installation instructions for Windows
```

#### Pull Request Process

1. **Create the PR:**
   - Use a descriptive title
   - Reference related issues
   - Describe what changed and why

2. **PR Description Template:**
   ```markdown
   ## Description
   Brief description of changes

   ## Type of Change
   - [ ] Bug fix
   - [ ] New feature
   - [ ] Documentation update
   - [ ] Code refactoring

   ## Testing
   - [ ] Tested locally
   - [ ] Added/updated tests
   - [ ] All tests pass

   ## Checklist
   - [ ] Code follows style guidelines
   - [ ] Self-reviewed the code
   - [ ] Added documentation
   - [ ] No breaking changes
   ```

3. **Review Process:**
   - Address reviewer feedback
   - Update code and tests as needed
   - Maintain a clean commit history

## Security Guidelines

### Reporting Security Issues

**DO NOT** create public issues for security vulnerabilities. Instead:

1. Email security concerns to [security@example.com]
2. Include detailed information about the vulnerability
3. Allow time for investigation and patching

### Security Best Practices

When contributing:

- Never commit credentials or sensitive data
- Validate all user inputs
- Use secure defaults
- Follow principle of least privilege
- Sanitize file paths and names
- Handle errors gracefully without exposing system information

### Sensitive Files

Never commit:
- `credentials.json`
- `.env` files
- `token.pickle`
- API keys or passwords
- Personal documents or data

## Areas for Contribution

### High Priority
- **Error handling**: Improve robustness and user experience
- **Testing**: Add comprehensive test coverage
- **Documentation**: Improve setup guides and troubleshooting
- **Performance**: Optimize embedding and storage operations

### Medium Priority
- **File formats**: Add support for more document types
- **UI/UX**: Enhance the Gradio interface
- **Monitoring**: Add metrics and health checks
- **Configuration**: Improve settings management

### Advanced Features
- **Batch processing**: Improve large dataset handling
- **Caching**: Add intelligent caching mechanisms
- **Analytics**: Add usage and performance analytics
- **Integration**: Add support for other cloud storage providers

## Resources

### Documentation
- [Python Type Hints](https://docs.python.org/3/library/typing.html)
- [PEP 8 Style Guide](https://pep8.org/)
- [Google Drive API](https://developers.google.com/drive)
- [Ollama Documentation](https://github.com/jmorganca/ollama)
- [ChromaDB Documentation](https://docs.trychroma.com/)

### Tools
- [Black Code Formatter](https://black.readthedocs.io/)
- [Flake8 Linter](https://flake8.pycqa.org/)
- [MyPy Type Checker](https://mypy.readthedocs.io/)
- [Pre-commit Hooks](https://pre-commit.com/)

## Questions?

- Check existing [issues and discussions](https://github.com/milo/google-drive-rag/issues)
- Start a [new discussion](https://github.com/milo/google-drive-rag/discussions)
- Review the [project wiki](https://github.com/milo/google-drive-rag/wiki)

Thank you for contributing to the Google Drive RAG System! 🚀