"""Create the database tables and the certificate output folder.

Run once before starting the API:  python -m app.init_db
"""

from app import models  # noqa: F401  (importing registers all ORM models)
from app.config import settings
from app.database import Base, engine


def main() -> None:
    """Create all tables and the output directory."""
    print("Creating database tables ...")
    Base.metadata.create_all(bind=engine)
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Done. Certificates will be stored in: {settings.output_dir.resolve()}")


if __name__ == "__main__":
    main()