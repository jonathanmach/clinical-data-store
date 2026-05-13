from pathlib import Path

from database import SessionLocal, init_db
from fhir_import import import_fhir_bundle
from seed import seed_data, seed_reference_data


def main():
    init_db()
    seed_reference_data()
    print("Database initialized.")
    seed_data()

    total = 0
    for bundle_path in sorted(Path("assets/synthea-fhir-data").glob("*.json")):
        session = SessionLocal()
        try:
            n = import_fhir_bundle(session, bundle_path)
            print(f"Imported {n} records from {bundle_path.name}.")
            total += n
        finally:
            session.close()
    print(f"Total: {total} records imported.")


if __name__ == "__main__":
    main()
