# src/copilots/compliance/document_ingestion/simple_agent.py
import hashlib
import io
import os
from datetime import datetime
from typing import Dict, Any, Optional
import PyPDF2
import logging
from pathlib import Path

try:
    from ..shared.kafka_handler import KafkaHandler
except ImportError:
    # Fallback for when running directly
    import sys
    import os
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
    from copilots.compliance.shared.kafka_handler import KafkaHandler

# Import our models and config
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from copilots.compliance.shared.models import Document, get_database_session, create_tables, test_database_connection
from copilots.compliance.config import Config

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SimpleDocumentIngestionAgent:
    """
    Simple Document Ingestion Agent
    Processes uploaded documents and stores them in the database
    """
    
    def __init__(self):
        self.config = Config()
        self.kafka_handler = KafkaHandler()
        print("🔍 Testing database connection...")
        
        # Test database connection
        print("🔍 Testing database connection...")
        if test_database_connection():
            print("🏗️  Creating database tables...")
            create_tables()
            self.use_database = True
            print("✅ Database ready!")
        else:
            print("⚠️  Database not available, using memory storage")
            self.use_database = False
            self.memory_storage = {}
    
    def process_document(self, file_path: str, customer_id: str = None) -> Dict[str, Any]:
        """
        Process a document file
        
        Args:
            file_path: Path to the document file
            customer_id: Optional customer ID
            
        Returns:
            Dictionary with processing results
        """
        try:
            print(f"📄 Processing document: {file_path}")
            
            # Validate file exists
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")
            
            # Get file info
            filename = os.path.basename(file_path)
            file_size = os.path.getsize(file_path)
            file_ext = Path(file_path).suffix.lower()
            
            print(f"   📊 File info: {filename} ({file_size} bytes, {file_ext})")
            
            # Check file size
            if file_size > self.config.MAX_FILE_SIZE:
                raise ValueError(f"File too large: {file_size} bytes (max: {self.config.MAX_FILE_SIZE})")
            
            # Check file extension
            if file_ext not in self.config.ALLOWED_EXTENSIONS:
                raise ValueError(f"File type not supported: {file_ext}")
            
            # Generate document ID
            doc_id = self._generate_document_id(file_path, customer_id)
            print(f"   🔑 Generated ID: {doc_id}")
            
            # Read file content
            with open(file_path, 'rb') as file:
                file_content = file.read()
            
            # Extract text
            print(f"   📝 Extracting text from {file_ext} file...")
            extracted_text = self._extract_text(file_content, file_ext)
            print(f"   ✅ Extracted {len(extracted_text)} characters")
            
            # Create document record
            doc_data = {
                'id': doc_id,
                'filename': filename,
                'file_type': file_ext.replace('.', ''),
                'customer_id': customer_id,
                'extracted_text': extracted_text,
                'text_length': len(extracted_text),
                'processed': True,
                'processing_status': 'completed',
                'upload_time': datetime.now()
            }
            
            # Store in database or memory
            if self.use_database:
                print(f"   💾 Storing in database...")
                self._store_in_database(doc_data)
            else:
                print(f"   💭 Storing in memory...")
                self.memory_storage[doc_id] = doc_data
            
            # Log success
            logger.info(f"✅ Successfully processed: {filename} (ID: {doc_id})")
            
            # Emit Kafka events
            print("📤 Emitting Kafka events...")
            self.kafka_handler.send_event(
                topic="document-processed",
                key=doc_id,
                value={
                    "document_id": doc_id,
                    "filename": filename,
                    "customer_id": customer_id,
                    "processed_at": doc_data['upload_time'].isoformat(),
                    "text_length": len(extracted_text),
                    "status": "success"
                }
            )

            # Emit event for KYC validation queue
            self.kafka_handler.send_event(
                topic="kyc-validation-requested", 
                key=doc_id,
                value={
                    "document_id": doc_id,
                    "customer_id": customer_id,
                    "filename": filename,
                    "document_type": self._guess_document_type(filename),
                    "requested_at": datetime.now().isoformat()
                }
            )

            # Log success
            logger.info(f"✅ Successfully processed: {filename} (ID: {doc_id})")

            return {
                'status': 'success',
                'document_id': doc_id,
                'filename': filename,
                'file_type': doc_data['file_type'],
                'text_length': len(extracted_text),
                'customer_id': customer_id,
                'processed_at': doc_data['upload_time'].isoformat(),
                'message': 'Document processed successfully'
            }
            
        except Exception as e:
            error_msg = f"Error processing {file_path}: {str(e)}"
            logger.error(error_msg)
            print(f"   ❌ {error_msg}")
            
            return {
                'status': 'error',
                'filename': os.path.basename(file_path) if os.path.exists(file_path) else 'unknown',
                'error': str(e),
                'processed_at': datetime.now().isoformat()
            }
    
    def _generate_document_id(self, file_path: str, customer_id: str = None) -> str:
        """Generate unique document ID"""
        content = f"{file_path}_{customer_id}_{datetime.now().isoformat()}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def _extract_text(self, file_content: bytes, file_ext: str) -> str:
        """Extract text from file based on extension"""
        try:
            if file_ext == '.pdf':
                return self._extract_pdf_text(file_content)
            elif file_ext == '.txt':
                return file_content.decode('utf-8')
            elif file_ext in ['.jpg', '.jpeg', '.png']:
                return self._extract_image_text(file_content)
            else:
                return f"Text extraction not implemented for {file_ext}"
        except Exception as e:
            return f"Text extraction failed: {str(e)}"
    
    def _extract_pdf_text(self, file_content: bytes) -> str:
        """Extract text from PDF file"""
        try:
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_content))
            text = ""
            for page_num, page in enumerate(pdf_reader.pages):
                try:
                    page_text = page.extract_text()
                    text += page_text + "\n"
                    print(f"     📄 Page {page_num + 1}: {len(page_text)} characters")
                except Exception as e:
                    error_text = f"[Error extracting page {page_num + 1}: {e}]\n"
                    text += error_text
                    print(f"     ⚠️  Page {page_num + 1}: Error - {e}")
            return text.strip()
        except Exception as e:
            return f"PDF extraction error: {str(e)}"
    
    def _extract_image_text(self, file_content: bytes) -> str:
        """Extract text from image using OCR (placeholder)"""
        # For now, return placeholder
        # Later we'll add pytesseract OCR
        return f"OCR text extraction not yet implemented. File size: {len(file_content)} bytes. Please install pytesseract for image processing."
    def _guess_document_type(self, filename: str) -> str:
        """Guess document type from filename"""
        filename_lower = filename.lower()
        
        if "commercial" in filename_lower or "registration" in filename_lower:
            return "commercial_registration"
        elif "national" in filename_lower or "id" in filename_lower:
            return "national_id" 
        elif "bank" in filename_lower:
            return "bank_statement"
        elif "tax" in filename_lower:
            return "tax_certificate"
        else:
            return "unknown"

    def _store_in_database(self, doc_data: Dict[str, Any]):
        """Store document data in PostgreSQL database"""
        try:
            session = get_database_session()
            
            # Create Document object
            document = Document(
                id=doc_data['id'],
                filename=doc_data['filename'],
                file_type=doc_data['file_type'],
                customer_id=doc_data['customer_id'],
                extracted_text=doc_data['extracted_text'],
                text_length=doc_data['text_length'],
                processed=doc_data['processed'],
                processing_status=doc_data['processing_status']
            )
            
            # Add to session and commit
            session.add(document)
            session.commit()
            session.close()
            
            logger.info(f"💾 Document stored in database: {doc_data['id']}")
            print(f"     ✅ Stored in PostgreSQL")
            
        except Exception as e:
            logger.error(f"Database storage error: {e}")
            print(f"     ❌ Database error: {e}")
            raise
    def _guess_document_type(self, filename: str) -> str:
        """Guess document type from filename"""
        filename_lower = filename.lower()
        
        if "commercial" in filename_lower or "registration" in filename_lower:
            return "commercial_registration"
        elif "national" in filename_lower or "id" in filename_lower:
            return "national_id" 
        elif "bank" in filename_lower:
            return "bank_statement"
        elif "tax" in filename_lower:
            return "tax_certificate"
        else:
            return "unknown"

    def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve document by ID"""
        if self.use_database:
            return self._get_from_database(doc_id)
        else:
            return self.memory_storage.get(doc_id)
    
    def _get_from_database(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get document from database"""
        try:
            session = get_database_session()
            document = session.query(Document).filter(Document.id == doc_id).first()
            session.close()
            
            if document:
                return {
                    'id': document.id,
                    'filename': document.filename,
                    'file_type': document.file_type,
                    'customer_id': document.customer_id,
                    'extracted_text': document.extracted_text,
                    'text_length': document.text_length,
                    'processed': document.processed,
                    'processing_status': document.processing_status,
                    'upload_time': document.upload_time.isoformat() if document.upload_time else None
                }
            return None
            
        except Exception as e:
            logger.error(f"Database retrieval error: {e}")
            return None
    
    def list_documents(self, customer_id: str = None) -> Dict[str, Any]:
        """List all documents, optionally filtered by customer"""
        if self.use_database:
            return self._list_from_database(customer_id)
        else:
            docs = list(self.memory_storage.values())
            if customer_id:
                docs = [doc for doc in docs if doc.get('customer_id') == customer_id]
            return {
                'total_documents': len(docs),
                'documents': docs
            }
    
    def _list_from_database(self, customer_id: str = None) -> Dict[str, Any]:
        """List documents from database"""
        try:
            session = get_database_session()
            query = session.query(Document)
            
            if customer_id:
                query = query.filter(Document.customer_id == customer_id)
            
            documents = query.all()
            session.close()
            
            doc_list = []
            for doc in documents:
                doc_list.append({
                    'id': doc.id,
                    'filename': doc.filename,
                    'file_type': doc.file_type,
                    'customer_id': doc.customer_id,
                    'text_length': doc.text_length,
                    'processed': doc.processed,
                    'processing_status': doc.processing_status,
                    'upload_time': doc.upload_time.isoformat() if doc.upload_time else None
                })
            
            return {
                'total_documents': len(doc_list),
                'documents': doc_list
            }
            
        except Exception as e:
            logger.error(f"Database list error: {e}")
            return {'total_documents': 0, 'documents': []}


# Test function
def test_agent():
    """Test the document ingestion agent"""
    print("🚀 Testing Document Ingestion Agent")
    print("=" * 50)
    
    # Create agent
    agent = SimpleDocumentIngestionAgent()
    
    # Create test files directory
    test_files_dir = "test_files"
    os.makedirs(test_files_dir, exist_ok=True)
    print(f"📁 Created test directory: {test_files_dir}")
    
    # Create test text file
    test_txt_file = os.path.join(test_files_dir, "commercial_registration.txt")
    print(f"📝 Creating test file: {test_txt_file}")
    
    with open(test_txt_file, 'w', encoding='utf-8') as f:
        f.write("""
COMMERCIAL REGISTRATION CERTIFICATE

Company Name: ABC Trading Company Ltd
Registration Number: 1234567890
Issue Date: 2024-01-15
Expiry Date: 2025-01-15
Business Activity: Import and Export Trading
Location: Riyadh, Saudi Arabia

This certificate confirms that the above company is duly registered
for commercial activities in accordance with the laws of the
Kingdom of Saudi Arabia.

Issued by: Ministry of Commerce
Contact: info@mci.gov.sa
Phone: +966-11-4567890

Additional Information:
- VAT Number: 123456789012345
- Authorized Capital: 1,000,000 SAR
- Paid Capital: 500,000 SAR
- Legal Form: Limited Liability Company
        """)
    
    print("✅ Test file created successfully")
    
    # Test processing
    print(f"\n{'='*50}")
    print("🔄 PROCESSING TEST")
    print(f"{'='*50}")
    
    result = agent.process_document(test_txt_file, customer_id="CUST123")
    
    print(f"\n📊 PROCESSING RESULT:")
    print(f"   Status: {result['status']}")
    if result['status'] == 'success':
        print(f"   Document ID: {result['document_id']}")
        print(f"   Text Length: {result['text_length']} characters")
        print(f"   Customer ID: {result['customer_id']}")
        print(f"   File Type: {result['file_type']}")
    else:
        print(f"   Error: {result['error']}")
    
    # Test retrieval
    if result['status'] == 'success':
        print(f"\n{'='*50}")
        print("🔍 RETRIEVAL TEST")
        print(f"{'='*50}")
        
        doc_id = result['document_id']
        print(f"🔎 Retrieving document: {doc_id}")
        retrieved = agent.get_document(doc_id)
        
        if retrieved:
            print(f"✅ Retrieved successfully:")
            print(f"   Filename: {retrieved['filename']}")
            print(f"   Customer ID: {retrieved['customer_id']}")
            print(f"   Text Length: {retrieved['text_length']}")
            print(f"   Processing Status: {retrieved['processing_status']}")
            print(f"📝 Text preview (first 150 chars):")
            print(f"   '{retrieved['extracted_text'][:150]}...'")
        else:
            print("❌ Document not found in retrieval")
    
    # Test listing
    print(f"\n{'='*50}")
    print("📚 LISTING TEST")
    print(f"{'='*50}")
    
    all_docs = agent.list_documents()
    print(f"📊 Total documents in system: {all_docs['total_documents']}")
    
    if all_docs['documents']:
        print(f"📋 Document list:")
        for i, doc in enumerate(all_docs['documents'], 1):
            print(f"   {i}. {doc['filename']}")
            print(f"      - ID: {doc['id']}")
            print(f"      - Customer: {doc['customer_id']}")
            print(f"      - Status: {doc['processing_status']}")
            print(f"      - Size: {doc['text_length']} chars")
    
    # Test with customer filter
    if all_docs['total_documents'] > 0:
        print(f"\n🔍 Testing customer filter (CUST123):")
        customer_docs = agent.list_documents(customer_id="CUST123")
        print(f"   Documents for CUST123: {customer_docs['total_documents']}")
    
    print(f"\n{'='*50}")
    print("🎉 AGENT TESTING COMPLETE!")
    print(f"{'='*50}")
    
    return agent

if __name__ == "__main__":
    test_agent()