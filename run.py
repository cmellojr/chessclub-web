"""Development server entry point."""

import logging

from app import create_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)


def main() -> None:
    """Run the Flask development server."""
    app = create_app()
    app.run(debug=True)


if __name__ == "__main__":
    main()
