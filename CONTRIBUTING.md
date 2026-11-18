# Contributing to Crypto Investment Manager

Thank you for your interest in contributing to Crypto Investment Manager!

## Development Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/harctik/Crypto-Investment-Manager.git
   cd Crypto-Investment-Manager
   ```

2. **Create and activate a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   pip install pytest pytest-cov flake8
   ```

4. **Run the test suite**
   ```bash
   pytest tests/ -v
   ```

## Pull Request Guidelines

- Ensure all existing and new unit tests pass before submitting.
- Follow PEP 8 style guidelines.
- Add descriptive commit messages adhering to Conventional Commits (e.g. `feat:`, `fix:`, `docs:`).
- Document new quantitative models or API integrations in the README.

