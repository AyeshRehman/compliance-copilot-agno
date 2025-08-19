# src/copilots/compliance/agno_config.py
import os
from dataclasses import dataclass

@dataclass
class AgnoConfig:
    """Enhanced configuration with Agno framework integration"""
    
    # Database - existing
    POSTGRES_URL = "postgresql://postgres:password@localhost:5432/myapp_dev"
    REDIS_URL = "redis://localhost:6379/0"
    KAFKA_BOOTSTRAP_SERVERS = "localhost:9092"
    
    # File processing - existing
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    ALLOWED_EXTENSIONS = {'.pdf', '.txt', '.jpg', '.jpeg', '.png'}
    
    # Agno Framework Settings
    USE_AGNO = True
    AGNO_STORAGE_TYPE = "memory"  # Start with memory for testing
    
    # LLM Configuration (Multiple providers for resilience)
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    
    # Primary LLM settings
    PRIMARY_LLM_PROVIDER = "groq"  # groq or openai
    PRIMARY_LLM_MODEL = "mixtral-8x7b-32768"  # Groq model
    
    # Vector Database Configuration
    VECTOR_DB_TYPE = "chroma"  # Local vector database
    CHROMA_DB_PATH = "./data/chroma_db"
    
    # Agent Configuration
    AGENT_MEMORY_SIZE = 10
    AGENT_MAX_ITERATIONS = 5
    
    # Compliance-specific settings
    SAMA_COMPLIANCE_THRESHOLD = 70
    KNOWLEDGE_CHUNK_SIZE = 1000
    KNOWLEDGE_CHUNK_OVERLAP = 200
    
    # Advanced features
    USE_DOCUMENT_INTELLIGENCE = True
    USE_COMPLIANCE_REASONING = True
    USE_KNOWLEDGE_RETRIEVAL = True
    
    def get_llm_config(self) -> dict:
        """Get LLM configuration"""
        if self.PRIMARY_LLM_PROVIDER == "groq":
            return {
                "provider": "groq",
                "api_key": self.GROQ_API_KEY,
                "model": self.PRIMARY_LLM_MODEL,
                "temperature": 0.1,
                "max_tokens": 2000
            }
        elif self.PRIMARY_LLM_PROVIDER == "openai":
            return {
                "provider": "openai", 
                "api_key": self.OPENAI_API_KEY,
                "model": "gpt-3.5-turbo",
                "temperature": 0.1,
                "max_tokens": 2000
            }
        else:
            raise ValueError(f"Unsupported LLM provider: {self.PRIMARY_LLM_PROVIDER}")
    
    def validate_config(self) -> bool:
        """Validate configuration"""
        if self.USE_AGNO:
            llm_config = self.get_llm_config()
            if not llm_config.get("api_key"):
                print(f"⚠️  Warning: No API key for {self.PRIMARY_LLM_PROVIDER}")
                print("   Will use basic functionality without AI features")
                return False
        return True

# Global config instance
config = AgnoConfig()

# Validation on import
if not config.validate_config():
    print("⚠️  Some Agno features may not work without proper API keys")
    print("   Set environment variables: GROQ_API_KEY or OPENAI_API_KEY")