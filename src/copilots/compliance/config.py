import os
from dataclasses import dataclass

@dataclass
class Config:
    # Database - using your Docker containers
    POSTGRES_URL = "postgresql://postgres:password@localhost:5432/myapp_dev"
    
    # Redis - using your Docker container
    REDIS_URL = "redis://localhost:6379/0"
    
    # Kafka (we'll add this later)
    KAFKA_BOOTSTRAP_SERVERS = "localhost:9092"
    
    # Pinecone (we'll add this later)
    PINECONE_API_KEY = os.getenv("PINECONE_API_KEY", "")
    PINECONE_ENV = os.getenv("PINECONE_ENV", "")
    PINECONE_INDEX = "compliance-docs"
    
    # File upload settings
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    ALLOWED_EXTENSIONS = {'.pdf', '.txt', '.jpg', '.jpeg', '.png'}
    
    # Agno settings (we'll configure this as we go)
    USE_AGNO = False  # Start False, enable later