# src/copilots/compliance/document_ingestion/agno_agent.py
import hashlib
import io
import os
from datetime import datetime
from typing import Dict, Any, List, Optional
import PyPDF2
import logging

# Agno imports
try:
    from agno import Agent, Workflow
    from agno.knowledge.vector import VectorKnowledge
    AGNO_AVAILABLE = True
    print("🤖 Agno framework loaded successfully")
except ImportError as e:
    print(f"⚠️  Agno not available: {e}")
    AGNO_AVAILABLE = False
    Agent = object  # Fallback base class

# Local imports
try:
    from ..shared.kafka_handler import KafkaHandler
    from ..shared.models import Document, get_database_session, create_tables, test_database_connection
    from ..agno_config import config
except ImportError:
    import sys
    import os
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
    sys.path.insert(0, parent_dir)
    from copilots.compliance.shared.kafka_handler import KafkaHandler
    from copilots.compliance.shared.models import Document, get_database_session, create_tables, test_database_connection
    from copilots.compliance.agno_config import config

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AgnoDocumentIngestionAgent(Agent if AGNO_AVAILABLE else object):
    """
    Enhanced Document Ingestion Agent with Agno Framework
    Features vector storage, intelligent analysis, and workflow orchestration
    """
    
    def __init__(self):
        self.config = config
        
        # Initialize Agno Agent if available
        if AGNO_AVAILABLE and self.config.USE_AGNO:
            try:
                super().__init__(
                    name="AgnoDocumentIngestionAgent",
                    description="AI-powered document ingestion for SAMA compliance",
                    instructions=self._get_agent_instructions(),
                    knowledge=self._setup_knowledge_base(),
                    show_tool_calls=True,
                    markdown=True
                )
                self.agno_enabled = True
                print("🤖 Agno Document Agent initialized with enhanced capabilities")
            except Exception as e:
                print(f"⚠️  Agno initialization failed: {e}")
                print("   Falling back to basic functionality")
                self.agno_enabled = False
        else:
            self.agno_enabled = False
            print("📄 Using basic document agent")
        
        # Initialize supporting components
        self.kafka_handler = KafkaHandler()
        
        # Test database connection
        print("🔍 Testing database connection...")
        if test_database_connection():
            create_tables()
            self.use_database = True
            print("✅ Database ready!")
        else:
            print("⚠️  Database not available, using memory storage")
            self.use_database = False
            self.memory_storage = {}
    
    def _get_agent_instructions(self) -> str:
        """Get instructions for the Agno agent"""
        return """
        You are an expert document processing agent for Saudi Arabian compliance.
        
        Your tasks:
        1. Analyze documents for SAMA compliance requirements
        2. Extract key information accurately
        3. Classify document types (commercial registration, national ID, bank statements, tax certificates)
        4. Assess document quality and completeness
        5. Store documents in vector database for future retrieval
        
        Always be thorough and focus on Saudi regulatory standards.
        """
    
    def _setup_knowledge_base(self):
        """Setup vector knowledge base"""
        if not AGNO_AVAILABLE or not self.config.USE_KNOWLEDGE_RETRIEVAL:
            return None
            
        try:
            # Create data directory if it doesn't exist
            os.makedirs("./data", exist_ok=True)
            
            # Setup ChromaDB vector knowledge
            knowledge = VectorKnowledge(
                vector_db="chroma",
                path=self.config.CHROMA_DB_PATH,
                collection_name="compliance_documents"
            )
            print("📚 Vector knowledge base initialized")
            return knowledge
            
        except Exception as e:
            logger.warning(f"Could not setup knowledge base: {e}")
            print(f"⚠️  Vector database setup failed: {e}")
            return None
    
    def process_document_enhanced(self, file_path: str, customer_id: str = None) -> Dict[str, Any]:
        """
        Enhanced document processing with Agno capabilities
        """
        try:
            print(f"\n🚀 Processing document with Agno: {file_path}")
            
            # Basic document processing
            result = self._basic_document_processing(file_path, customer_id)
            
            if result["status"] != "success":
                return result
            
            # Enhanced processing if Agno is enabled
            if self.agno_enabled:
                print("   🧠 Running enhanced analysis...")
                
                # Enhanced document analysis
                enhanced_analysis = self._run_enhanced_analysis(
                    result["extracted_text"], 
                    result["filename"]
                )
                
                # Add enhanced features to result
                result.update({
                    "enhanced_analysis": enhanced_analysis,
                    "document_type_confidence": enhanced_analysis.get("confidence", 0.8),
                    "quality_assessment": enhanced_analysis.get("quality", 0.7),
                    "agno_enhanced": True
                })
                
                # Store in vector database
                if self.knowledge:
                    self._store_in_vector_knowledge(result)
                    print("   📚 Stored in vector knowledge base")
                
            else:
                print("   📄 Using basic processing")
                result["agno_enhanced"] = False
            
            # Store in database
            if self.use_database:
                self._store_in_database(result)
            else:
                self.memory_storage[result["document_id"]] = result
            
            # Emit enhanced events
            self._emit_enhanced_events(result)
            
            print(f"✅ Document processing complete: {result['document_id']}")
            return result
            
        except Exception as e:
            error_result = {
                "filename": os.path.basename(file_path),
                "status": "error",
                "error": str(e),
                "processed_at": datetime.now().isoformat()
            }
            logger.error(f"Enhanced document processing error: {e}")
            return error_result
    
    def _basic_document_processing(self, file_path: str, customer_id: str = None) -> Dict[str, Any]:
        """Basic document processing (reusing existing logic)"""
        # Validate file
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        filename = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        file_ext = os.path.splitext(file_path)[1].lower()
        
        print(f"   📊 File info: {filename} ({file_size} bytes, {file_ext})")
        
        # Generate document ID
        doc_id = hashlib.md5(f"{file_path}_{customer_id}_{datetime.now().isoformat()}".encode()).hexdigest()
        
        # Extract text
        with open(file_path, 'rb') as file:
            file_content = file.read()
        
        if file_ext == '.pdf':
            extracted_text = self._extract_pdf_text(file_content)
        elif file_ext == '.txt':
            extracted_text = file_content.decode('utf-8')
        else:
            extracted_text = f"Unsupported file type: {file_ext}"
        
        print(f"   📝 Extracted {len(extracted_text)} characters")
        
        return {
            "status": "success",
            "document_id": doc_id,
            "filename": filename,
            "file_type": file_ext.replace('.', ''),
            "customer_id": customer_id,
            "extracted_text": extracted_text,
            "text_length": len(extracted_text),
            "processed_at": datetime.now().isoformat()
        }
    
    def _run_enhanced_analysis(self, text: str, filename: str) -> Dict[str, Any]:
        """Run enhanced document analysis"""
        try:
            # Smart document type classification
            doc_type = self._classify_document_intelligently(text, filename)
            
            # Quality assessment
            quality_score = self._assess_document_quality(text)
            
            # Extract key metadata
            metadata = self._extract_smart_metadata(text, doc_type)
            
            # Compliance insights
            insights = self._generate_compliance_insights(text, doc_type)
            
            return {
                "document_type": doc_type,
                "confidence": self._calculate_confidence(text, filename, doc_type),
                "quality": quality_score,
                "metadata": metadata,
                "insights": insights,
                "analysis_method": "agno_enhanced"
            }
            
        except Exception as e:
            logger.error(f"Enhanced analysis error: {e}")
            return {
                "document_type": self._guess_document_type(filename),
                "confidence": 0.5,
                "quality": 0.5,
                "error": str(e),
                "analysis_method": "fallback"
            }
    
    def _classify_document_intelligently(self, text: str, filename: str) -> str:
        """Intelligent document classification"""
        text_lower = text.lower()
        filename_lower = filename.lower()
        
        # Enhanced classification with content analysis
        classification_scores = {
            "commercial_registration": 0,
            "national_id": 0,
            "bank_statement": 0,
            "tax_certificate": 0
        }
        
        # Commercial registration indicators
        if any(keyword in text_lower for keyword in [
            "commercial registration", "تجاري", "ministry of commerce", 
            "registration number", "company name", "business activity"
        ]):
            classification_scores["commercial_registration"] += 3
        
        if any(keyword in filename_lower for keyword in ["commercial", "registration", "cr"]):
            classification_scores["commercial_registration"] += 2
        
        # National ID indicators
        if any(keyword in text_lower for keyword in [
            "national identity", "هوية وطنية", "identity card", "id number"
        ]):
            classification_scores["national_id"] += 3
        
        if any(keyword in filename_lower for keyword in ["national", "id", "identity"]):
            classification_scores["national_id"] += 2
        
        # Bank statement indicators
        if any(keyword in text_lower for keyword in [
            "bank statement", "account number", "balance", "transaction", "sar"
        ]):
            classification_scores["bank_statement"] += 3
        
        if any(keyword in filename_lower for keyword in ["bank", "statement", "account"]):
            classification_scores["bank_statement"] += 2
        
        # Tax certificate indicators
        if any(keyword in text_lower for keyword in [
            "tax certificate", "vat", "ضريبة", "zatca", "tax registration"
        ]):
            classification_scores["tax_certificate"] += 3
        
        if any(keyword in filename_lower for keyword in ["tax", "vat", "certificate"]):
            classification_scores["tax_certificate"] += 2
        
        # Return the highest scoring classification
        best_match = max(classification_scores.items(), key=lambda x: x[1])
        return best_match[0] if best_match[1] > 0 else "unknown"
    
    def _assess_document_quality(self, text: str) -> float:
        """Assess document quality"""
        quality_score = 0.0
        
        # Length check
        if len(text) > 100:
            quality_score += 0.3
        
        # Content diversity check
        if len(set(text.split())) / len(text.split()) > 0.5:
            quality_score += 0.3
        
        # Number presence (important for IDs, dates, etc.)
        if any(char.isdigit() for char in text):
            quality_score += 0.2
        
        # Special characters (indicates structured content)
        if any(char in text for char in ['-', '/', ':', '(', ')']):
            quality_score += 0.2
        
        return min(quality_score, 1.0)
    
    def _extract_smart_metadata(self, text: str, doc_type: str) -> Dict[str, Any]:
        """Extract intelligent metadata based on document type"""
        import re
        
        metadata = {"extraction_method": "smart_regex"}
        
        # Common patterns
        date_pattern = r'\d{4}[-/]\d{2}[-/]\d{2}|\d{2}[-/]\d{2}[-/]\d{4}'
        number_pattern = r'\b\d{10,}\b'
        
        dates = re.findall(date_pattern, text)
        numbers = re.findall(number_pattern, text)
        
        metadata["dates_found"] = dates[:3]  # Limit to first 3
        metadata["important_numbers"] = numbers[:3]  # Limit to first 3
        
        # Document-specific extraction
        if doc_type == "commercial_registration":
            cr_pattern = r'\b\d{10}\b'
            cr_numbers = re.findall(cr_pattern, text)
            metadata["cr_candidates"] = cr_numbers
        
        elif doc_type == "national_id":
            id_pattern = r'\b[12]\d{9}\b'
            id_numbers = re.findall(id_pattern, text)
            metadata["id_candidates"] = id_numbers
        
        return metadata
    
    def _generate_compliance_insights(self, text: str, doc_type: str) -> List[str]:
        """Generate compliance insights"""
        insights = []
        
        # General insights
        if len(text) < 50:
            insights.append("Document appears to be very short - may be incomplete")
        
        # Document-specific insights
        if doc_type == "commercial_registration":
            if "saudi" in text.lower() or "المملكة" in text:
                insights.append("Saudi jurisdiction indicators found")
            if not any(char.isdigit() for char in text):
                insights.append("No registration numbers detected - document may be incomplete")
        
        elif doc_type == "national_id":
            if any(ord(char) > 127 for char in text):  # Non-ASCII characters
                insights.append("Arabic text detected - good for Saudi ID documents")
        
        elif doc_type == "bank_statement":
            if "sar" in text.lower():
                insights.append("Saudi currency (SAR) detected")
        
        return insights
    
    def _calculate_confidence(self, text: str, filename: str, doc_type: str) -> float:
        """Calculate classification confidence"""
        # Simple confidence calculation based on multiple factors
        confidence = 0.5  # Base confidence
        
        # Filename match increases confidence
        if doc_type in filename.lower():
            confidence += 0.2
        
        # Content length increases confidence
        if len(text) > 200:
            confidence += 0.2
        
        # Structured content increases confidence
        if any(pattern in text for pattern in [':', '-', '/', '(', ')']):
            confidence += 0.1
        
        return min(confidence, 1.0)
    
    def _guess_document_type(self, filename: str) -> str:
        """Fallback document type guessing"""
        filename_lower = filename.lower()
        
        if "commercial" in filename_lower:
            return "commercial_registration"
        elif "national" in filename_lower or "id" in filename_lower:
            return "national_id"
        elif "bank" in filename_lower:
            return "bank_statement"
        elif "tax" in filename_lower or "vat" in filename_lower:
            return "tax_certificate"
        else:
            return "unknown"
    
    def _extract_pdf_text(self, file_content: bytes) -> str:
        """Extract text from PDF"""
        try:
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_content))
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
            return text.strip()
        except Exception as e:
            return f"PDF extraction error: {str(e)}"
    
    def _store_in_vector_knowledge(self, result: Dict[str, Any]):
        """Store document in vector knowledge base"""
        if not self.knowledge:
            return
        
        try:
            doc_id = result["document_id"]
            text = result["extracted_text"]
            
            # Chunk text for better retrieval
            chunks = self._chunk_text(text)
            
            for i, chunk in enumerate(chunks):
                chunk_id = f"{doc_id}_chunk_{i}"
                self.knowledge.upsert([{
                    "id": chunk_id,
                    "text": chunk,
                    "metadata": {
                        "document_id": doc_id,
                        "filename": result["filename"],
                        "customer_id": result["customer_id"],
                        "chunk_index": i,
                        "total_chunks": len(chunks),
                        "document_type": result.get("enhanced_analysis", {}).get("document_type", "unknown"),
                        "quality_score": result.get("enhanced_analysis", {}).get("quality", 0.5),
                        "processed_at": result["processed_at"]
                    }
                }])
            
        except Exception as e:
            logger.error(f"Vector storage error: {e}")
    
    def _chunk_text(self, text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
        """Split text into overlapping chunks"""
        if len(text) <= chunk_size:
            return [text]
        
        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]
            chunks.append(chunk)
            start = end - overlap
        
        return chunks
    
    def _store_in_database(self, doc_data: Dict[str, Any]):
        """Store document in database"""
        try:
            session = get_database_session()
            
            document = Document(
                id=doc_data['document_id'],
                filename=doc_data['filename'],
                file_type=doc_data['file_type'],
                customer_id=doc_data['customer_id'],
                extracted_text=doc_data['extracted_text'],
                text_length=doc_data['text_length'],
                processed=True,
                processing_status='completed'
            )
            
            session.add(document)
            session.commit()
            session.close()
            
            print(f"   💾 Document stored in database")
            
        except Exception as e:
            logger.error(f"Database storage error: {e}")
    
    def _emit_enhanced_events(self, result: Dict[str, Any]):
        """Emit enhanced Kafka events"""
        doc_id = result["document_id"]
        
        # Enhanced document processed event
        self.kafka_handler.send_event(
            topic="document-processed-enhanced",
            key=doc_id,
            value={
                "document_id": doc_id,
                "filename": result["filename"],
                "customer_id": result["customer_id"],
                "processed_at": result["processed_at"],
                "text_length": result["text_length"],
                "agno_enhanced": result.get("agno_enhanced", False),
                "document_type": result.get("enhanced_analysis", {}).get("document_type", "unknown"),
                "confidence": result.get("document_type_confidence", 0.5),
                "quality_score": result.get("quality_assessment", 0.5),
                "status": "success"
            }
        )
    
    def query_knowledge_base(self, query: str, limit: int = 3) -> List[Dict]:
        """Query the vector knowledge base"""
        if not self.knowledge:
            return []
        
        try:
            results = self.knowledge.search(query, limit=limit)
            return results
        except Exception as e:
            logger.error(f"Knowledge base query error: {e}")
            return []


# Test function
def test_agno_document_agent():
    """Test the Agno-enhanced document agent"""
    print("🚀 Testing Agno Document Ingestion Agent")
    print("=" * 60)
    
    # Create agent
    agent = AgnoDocumentIngestionAgent()
    
    # Create test file
    test_files_dir = "test_files"
    os.makedirs(test_files_dir, exist_ok=True)
    
    test_file = os.path.join(test_files_dir, "agno_test_commercial_reg.txt")
    with open(test_file, 'w', encoding='utf-8') as f:
        f.write("""
COMMERCIAL REGISTRATION CERTIFICATE - ENHANCED TEST

Company Name: Agno AI Solutions LLC
Registration Number: 5555444433
Issue Date: 2024-05-01
Expiry Date: 2025-05-01
Business Activity: Artificial Intelligence and Machine Learning Solutions
Location: Prince Mohammed Bin Abdulaziz Road, Riyadh, Saudi Arabia

This certificate confirms that the above company is duly registered
for commercial activities in accordance with the laws of the
Kingdom of Saudi Arabia.

Authorized Capital: 5,000,000 SAR
Paid Capital: 3,000,000 SAR
Legal Form: Limited Liability Company
Business License: TECH-2024-AI-001

Contact Information:
Email: info@agnoai.com.sa
Phone: +966-11-5555444
Website: www.agnoai.com.sa

Issued by: Ministry of Commerce and Investment
Digital Signature: VERIFIED
Validation Code: AGN-2024-CR-5555444433
        """)
    
    print(f"📄 Created enhanced test file: {test_file}")
    
    # Test enhanced processing
    print(f"\n{'='*80}")
    print("🤖 TESTING AGNO-ENHANCED PROCESSING")
    print(f"{'='*80}")
    
    result = agent.process_document_enhanced(test_file, customer_id="AGNO_CUST_001")
    
    print(f"\n📊 ENHANCED PROCESSING RESULT:")
    print(f"   Status: {result['status']}")
    print(f"   Document ID: {result.get('document_id', 'Unknown')[:16]}...")
    print(f"   Agno Enhanced: {result.get('agno_enhanced', False)}")
    print(f"   Text Length: {result.get('text_length', 0)} characters")
    
    if result.get('enhanced_analysis'):
        analysis = result['enhanced_analysis']
        print(f"\n🧠 ENHANCED ANALYSIS:")
        print(f"   Document Type: {analysis.get('document_type', 'Unknown')}")
        print(f"   Confidence: {analysis.get('confidence', 0):.2f}")
        print(f"   Quality Score: {analysis.get('quality', 0):.2f}")
        print(f"   Analysis Method: {analysis.get('analysis_method', 'Unknown')}")
        
        if analysis.get('insights'):
            print(f"   Insights: {len(analysis['insights'])} found")
            for insight in analysis['insights']:
                print(f"     - {insight}")
    
    # Test knowledge base query if available
    if agent.knowledge:
        print(f"\n📚 TESTING KNOWLEDGE BASE QUERY:")
        query_results = agent.query_knowledge_base("commercial registration saudi arabia")
        print(f"   Query results: {len(query_results)} documents found")
    
    print(f"\n🎉 Agno integration test complete!")
    return agent, result

if __name__ == "__main__":
    test_agno_document_agent()