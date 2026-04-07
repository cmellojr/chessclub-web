# Contributing

Thank you for your interest in contributing to **chessclub-web**!

## Getting Started

1. Fork the repository and clone your fork.
2. Install the chessclub library in editable mode:

   ```bash
   pip install -e ../chessclub
   pip install -r requirements.txt
   ```

3. Copy the environment file and configure it:

   ```bash
   cp .env.example .env
   ```

4. Run the development server:

   ```bash
   python run.py
   ```

## Development Workflow

1. Create a branch from `develop`:

   ```bash
   git checkout -b feature/your-feature develop
   ```

2. Make your changes following the project conventions (see below).
3. Run the linter and formatter before committing:

   ```bash
   ruff check --fix .
   ruff format .
   ```

4. Commit with a clear, concise message describing what changed and why.
5. Push your branch and open a pull request against `develop`.

## Code Conventions

- **Style guide:** [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html).
- **Docstrings:** Google convention with `Args:`, `Returns:`, `Raises:` sections.
- **Type annotations:** Required on all function signatures. Use `X | Y` union syntax (Python 3.11+).
- **Linter/formatter:** Ruff — see `pyproject.toml` for rule configuration.
- **Frontend:** Bootstrap 5.3 via CDN + Jinja2 templates. No build steps or JS frameworks.

## Branching Model

- `main` — stable releases, merged from `develop` with `--no-ff`.
- `develop` — integration branch for ongoing work.
- `feature/*` — feature branches created from `develop`.

## Reporting Issues

Open an issue on GitHub with:

- A clear description of the problem or suggestion.
- Steps to reproduce (for bugs).
- Expected vs. actual behavior.

## License

By contributing, you agree that your contributions will be licensed under the
[MIT License](LICENSE).
