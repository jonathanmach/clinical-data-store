from database import init_db
from seed import seed_data, seed_reference_data


def main():
    init_db()
    seed_reference_data()
    print("Database initialized.")
    seed_data()



if __name__ == "__main__":
    main()
