from sqlalchemy import create_engine
import os
from dotenv import load_dotenv
import psycopg2

load_dotenv()

DB_HOST = os.getenv('DB_HOST')
DB_PORT = os.getenv('DB_PORT')
DB_NAME = os.getenv('DB_NAME')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')

# Database connection string
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

print("Testing database connection...")
print(f"Connection URL: postgresql://{DB_USER}:****@{DB_HOST}:{DB_PORT}/{DB_NAME}")

# Try direct psycopg2 connection first
print("\nTesting with psycopg2...")
try:
    conn = psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT
    )
    print("✓ psycopg2 connection successful!")
    conn.close()
except Exception as e:
    print(f"✗ psycopg2 connection failed: {str(e)}")

# Then try SQLAlchemy
print("\nTesting with SQLAlchemy...")
try:
    engine = create_engine(DATABASE_URL)
    with engine.connect() as conn:
        print("✓ SQLAlchemy connection successful!")
except Exception as e:
    print(f"✗ SQLAlchemy connection failed: {str(e)}") 