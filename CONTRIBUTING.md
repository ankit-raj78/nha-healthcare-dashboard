# Contributing to NHA Healthcare Facilities Dashboard

Thank you for your interest in contributing to this project! This document provides guidelines for contributing to the NHA Healthcare Facilities Dashboard.

## 🚀 Getting Started

### Prerequisites
- Python 3.9 or higher
- Git
- Basic knowledge of Streamlit and pandas

### Setting Up Development Environment

1. **Fork the repository**
   ```bash
   # Fork on GitHub, then clone your fork
   git clone https://github.com/YOUR_USERNAME/nha-healthcare-dashboard.git
   cd nha-healthcare-dashboard
   ```

2. **Create virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt  # If available
   ```

4. **Create a branch for your feature**
   ```bash
   git checkout -b feature/your-feature-name
   ```

## 📋 Code Standards

### Python Style Guide
- Follow PEP 8 style guidelines
- Use type hints for function parameters and return values
- Maximum line length: 88 characters (Black formatter standard)
- Use descriptive variable and function names

### Code Formatting
We use Black for code formatting:
```bash
black .
```

### Linting
We use flake8 for linting:
```bash
flake8 .
```

### Documentation
- Include docstrings for all functions and classes
- Use Google-style docstrings
- Update README.md if you add new features
- Comment complex logic

## 🔧 Project Structure

When contributing, please follow the established project structure:

```
streamlit/
├── dashboard.py              # Main entry point
├── app/                      # Core application logic
├── components/               # Reusable UI components
├── utils/                    # Utility functions
├── config/                   # Configuration files
├── tests/                    # Unit tests
└── data/                     # Data files
```

## 🧪 Testing

### Writing Tests
- Write unit tests for new functions
- Place tests in the `tests/` directory
- Use pytest for testing framework
- Aim for good test coverage

### Running Tests
```bash
pytest tests/ -v
```

## 📝 Commit Guidelines

### Commit Message Format
```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

### Types
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

### Examples
```
feat(search): add natural language search capability
fix(map): resolve marker clustering performance issue
docs(readme): update installation instructions
```

## 🔍 Pull Request Process

1. **Create a feature branch** from `main`
2. **Make your changes** following the code standards
3. **Write or update tests** for your changes
4. **Update documentation** if necessary
5. **Run the test suite** to ensure everything passes
6. **Format your code** with Black
7. **Create a pull request** with a clear description

### Pull Request Template
When creating a PR, please include:

- **Description**: What does this PR do?
- **Type of Change**: Bug fix, new feature, documentation, etc.
- **Testing**: How was this tested?
- **Screenshots**: If applicable
- **Checklist**: 
  - [ ] Code follows style guidelines
  - [ ] Self-review completed
  - [ ] Tests added/updated
  - [ ] Documentation updated

## 🐛 Reporting Issues

### Bug Reports
When reporting bugs, please include:
- **Description**: Clear description of the issue
- **Steps to Reproduce**: Detailed steps
- **Expected Behavior**: What should happen
- **Actual Behavior**: What actually happens
- **Environment**: OS, Python version, browser
- **Screenshots**: If applicable

### Feature Requests
When suggesting features:
- **Description**: Clear description of the feature
- **Use Case**: Why is this feature needed?
- **Proposed Solution**: How should it work?
- **Alternatives**: Other solutions considered

## 🎯 Areas for Contribution

### High Priority
- Performance optimization for large datasets
- Additional chart types and visualizations
- Enhanced search capabilities
- Mobile responsiveness
- Data validation and error handling

### Medium Priority
- Additional data export formats
- User preferences and settings
- Dashboard customization options
- Advanced filtering options

### Good First Issues
- Documentation improvements
- Code cleanup and refactoring
- Adding unit tests
- UI/UX enhancements

## 📊 Development Workflow

1. **Choose an issue** or propose a new feature
2. **Discuss** the approach in the issue comments
3. **Fork and clone** the repository
4. **Create a branch** for your work
5. **Develop** following the guidelines
6. **Test** your changes thoroughly
7. **Submit** a pull request

## 🔒 Security

If you discover a security vulnerability, please email us directly instead of creating a public issue.

## 📄 License

By contributing, you agree that your contributions will be licensed under the same license as the project.

## 🤝 Community

- Be respectful and inclusive
- Help other contributors
- Share knowledge and best practices
- Provide constructive feedback

## 📞 Getting Help

If you need help:
1. Check existing documentation
2. Search existing issues
3. Create a new issue with the "question" label
4. Join community discussions

Thank you for contributing to making healthcare data more accessible and actionable! 🏥✨
