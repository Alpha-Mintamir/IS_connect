from sqlalchemy import create_engine, Table, Column, Integer, String, MetaData, BigInteger, DateTime, Text
import os
from dotenv import load_dotenv
from datetime import datetime
import logging

# Create logs directory if it doesn't exist
os.makedirs('logs', exist_ok=True)

# Configure logging
logging.basicConfig(
    filename='logs/db_setup.log',
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load environment variables
logger.info("Loading environment variables...")
load_dotenv()
DB_HOST = os.getenv('DB_HOST')
DB_PORT = os.getenv('DB_PORT')
DB_NAME = os.getenv('DB_NAME')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')

# Validate environment variables
if not all([DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD]):
    logger.error("Missing required database environment variables")
    raise ValueError("Missing required database environment variables")

# Database connection string
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

try:
    # Initialize SQLAlchemy engine
    logger.info("Initializing database engine...")
    engine = create_engine(DATABASE_URL)
    
    # Test connection
    with engine.connect() as conn:
        logger.info("Database connection successful")
    
    # Initialize metadata
    meta = MetaData()
    
    # Define the LinkedIn user table
    logger.info("Creating table definition...")
    linkedin_table = Table(
        'user_linkedin', meta,
        Column('id', Integer, primary_key=True),
        Column('linkedin_url', String, unique=True, nullable=False),
        Column('telegram_user_id', BigInteger, nullable=False),
        Column('full_name', String),
        Column('headline', String),
        Column('location', String),
        Column('current_company', String),
        Column('summary', Text),
        Column('created_at', DateTime, default=datetime.utcnow),
        Column('updated_at', DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    )
    
    # Create the table in the database
    logger.info("Creating tables in database...")
    meta.create_all(engine)
    logger.info("Database tables created successfully")
    print("✓ Database and tables created successfully!")

except Exception as e:
    logger.error(f"Error setting up database: {str(e)}", exc_info=True)
    print(f"✗ Error: {str(e)}")
    raise


