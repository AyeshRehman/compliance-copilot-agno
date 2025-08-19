from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, Float, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import func
from datetime import datetime
from ..config import Config

Base = declarative_base()

class Document(Base):
    __tablename__ = "documents"
    
    id = Column(String(100), primary_key=True)  # Generated hash
    filename = Column(String(255), nullable=False)
    file_type = Column(String(50))
    customer_id = Column(String(100))
    upload_time = Column(DateTime, default=func.now())
    processed = Column(Boolean, default=False)
    extracted_text = Column(Text)
    text_length = Column(Integer)
    processing_status = Column(String(50), default="pending")
    error_message = Column(Text)

class KYCValidation(Base):
    __tablename__ = "kyc_validations"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(String(100), nullable=False)
    customer_id = Column(String(100))
    document_type = Column(String(100))
    is_valid = Column(Boolean, default=False)
    validation_score = Column(Float, default=0.0)
    validated_at = Column(DateTime, default=func.now())
    issues = Column(Text)  # JSON string of issues
    recommendations = Column(Text)  # JSON string of recommendations

class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_name = Column(String(100), nullable=False)
    action = Column(String(200), nullable=False)
    user_id = Column(String(100))
    document_id = Column(String(100))
    timestamp = Column(DateTime, default=func.now())
    details = Column(Text)
    status = Column(String(50))
    session_id = Column(String(100))

# Database connection setup
def get_database_engine():
    """Create database engine"""
    return create_engine(Config.POSTGRES_URL)

def get_database_session():
    """Get database session"""
    engine = get_database_engine()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal()

def create_tables():
    """Create all tables"""
    engine = get_database_engine()
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables created successfully!")

# Test database connection
def test_database_connection():
    """Test if we can connect to the database"""
    try:
        engine = get_database_engine()
        connection = engine.connect()
        connection.close()
        print("✅ Database connection successful!")
        return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False