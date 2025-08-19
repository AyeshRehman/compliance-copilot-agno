# src/copilots/compliance/kyc_validation/validation_agent.py
import re
import json
from datetime import datetime
from typing import Dict, Any, List
import logging

# Import handlers
try:
    from ..shared.kafka_handler import KafkaHandler
    from ..shared.models import KYCValidation, get_database_session, test_database_connection
    from ..config import Config
except ImportError:
    import sys
    import os
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
    sys.path.insert(0, parent_dir)
    from copilots.compliance.shared.kafka_handler import KafkaHandler
    from copilots.compliance.shared.models import KYCValidation, get_database_session, test_database_connection
    from copilots.compliance.config import Config

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class KYCValidationAgent:
    """
    KYC Validation Agent for SAMA Compliance
    Validates documents against Saudi regulatory requirements
    """
    
    def __init__(self):
        self.config = Config()
        self.kafka_handler = KafkaHandler()
        
        # Test database connection
        print("🔍 Testing database connection for KYC validation...")
        self.use_database = test_database_connection()
        if not self.use_database:
            print("⚠️  Database not available, validation results will be logged only")
        
        # SAMA compliance requirements for SME KYC
        self.required_documents = [
            "commercial_registration",
            "national_id", 
            "bank_statements",
            "tax_certificate"
        ]
        
        print("✅ KYC Validation Agent initialized")
        print(f"📋 Required document types: {', '.join(self.required_documents)}")
        
    def validate_kyc_document(self, document_id: str, extracted_text: str, 
                            filename: str, customer_id: str = None) -> Dict[str, Any]:
        """
        Main validation function for KYC documents
        """
        print(f"\n🔍 Starting KYC validation for: {filename}")
        print(f"   📄 Document ID: {document_id}")
        print(f"   👤 Customer ID: {customer_id}")
        
        try:
            # Determine document type
            doc_type = self._identify_document_type(filename, extracted_text)
            print(f"   📝 Detected document type: {doc_type}")
            
            # Run validation based on document type
            validation_result = self._run_validation(doc_type, extracted_text, filename)
            
            # Create complete result
            result = {
                "document_id": document_id,
                "customer_id": customer_id,
                "filename": filename,
                "document_type": doc_type,
                "is_valid": validation_result["is_valid"],
                "validation_score": validation_result["score"],
                "issues": validation_result["issues"],
                "recommendations": validation_result["recommendations"],
                "validated_at": datetime.now().isoformat(),
                "validation_details": validation_result.get("details", {})
            }
            
            # Store validation result
            if self.use_database:
                self._store_validation_result(result)
            
            # Emit validation completion event
            self.kafka_handler.send_event(
                topic="kyc-validation-completed",
                key=document_id,
                value=result
            )
            
            # Print validation summary
            self._print_validation_summary(result)
            
            return result
            
        except Exception as e:
            error_result = {
                "document_id": document_id,
                "customer_id": customer_id,
                "filename": filename,
                "is_valid": False,
                "error": str(e),
                "validated_at": datetime.now().isoformat()
            }
            
            print(f"❌ Validation error: {e}")
            logger.error(f"KYC validation error for {document_id}: {e}")
            
            return error_result
    
    def _identify_document_type(self, filename: str, text: str) -> str:
        """Identify document type from filename and content"""
        filename_lower = filename.lower()
        text_lower = text.lower()
        
        # Check filename first
        if "commercial" in filename_lower or "registration" in filename_lower:
            return "commercial_registration"
        elif "national" in filename_lower or "id" in filename_lower:
            return "national_id"
        elif "bank" in filename_lower or "statement" in filename_lower:
            return "bank_statements"
        elif "tax" in filename_lower or "vat" in filename_lower:
            return "tax_certificate"
        
        # Check content
        if any(keyword in text_lower for keyword in ["commercial registration", "تجاري", "ministry of commerce"]):
            return "commercial_registration"
        elif any(keyword in text_lower for keyword in ["national id", "هوية", "identity card"]):
            return "national_id"
        elif any(keyword in text_lower for keyword in ["bank statement", "account", "بنك"]):
            return "bank_statements"
        elif any(keyword in text_lower for keyword in ["tax certificate", "vat", "ضريبة"]):
            return "tax_certificate"
        
        return "unknown"
    
    def _run_validation(self, doc_type: str, text: str, filename: str) -> Dict[str, Any]:
        """Run specific validation based on document type"""
        print(f"   🔍 Running {doc_type} validation rules...")
        
        if doc_type == "commercial_registration":
            return self._validate_commercial_registration(text)
        elif doc_type == "national_id":
            return self._validate_national_id(text)
        elif doc_type == "bank_statements":
            return self._validate_bank_statements(text)
        elif doc_type == "tax_certificate":
            return self._validate_tax_certificate(text)
        else:
            return {
                "is_valid": False,
                "score": 0,
                "issues": [f"Unknown document type: {doc_type}"],
                "recommendations": ["Please provide a supported document type"],
                "details": {"supported_types": self.required_documents}
            }
    
    def _validate_commercial_registration(self, text: str) -> Dict[str, Any]:
        """Validate commercial registration certificate against SAMA requirements"""
        issues = []
        recommendations = []
        details = {}
        score = 0
        
        print("     📋 Checking commercial registration requirements...")
        
        # Check for CR number (10 digits)
        cr_pattern = r'\b\d{10}\b'
        cr_match = re.search(cr_pattern, text)
        if cr_match:
            score += 25
            details["cr_number"] = cr_match.group()
            print(f"     ✅ CR Number found: {cr_match.group()}")
        else:
            issues.append("Commercial Registration number (10 digits) not found")
            recommendations.append("Ensure CR number is clearly visible in the document")
            print("     ❌ CR Number not found")
        
        # Check for company name
        company_indicators = ["company", "corp", "ltd", "llc", "شركة"]
        if any(indicator in text.lower() for indicator in company_indicators):
            score += 25
            print("     ✅ Company indicators found")
        else:
            issues.append("Company name or business entity indicators not clear")
            recommendations.append("Ensure company name is clearly visible")
            print("     ❌ Company indicators not found")
        
        # Check for dates (issue/expiry)
        date_patterns = [r'\d{4}-\d{2}-\d{2}', r'\d{2}/\d{2}/\d{4}', r'\d{1,2}[-/]\d{1,2}[-/]\d{4}']
        dates_found = []
        for pattern in date_patterns:
            dates_found.extend(re.findall(pattern, text))
        
        if dates_found:
            score += 20
            details["dates_found"] = dates_found
            print(f"     ✅ Dates found: {dates_found}")
        else:
            issues.append("Issue date or expiry date not clearly identified")
            recommendations.append("Ensure document dates are visible")
            print("     ❌ No dates found")
        
        # Check for Saudi Arabia indicators
        saudi_indicators = ['saudi', 'السعودية', 'kingdom', 'المملكة', 'riyadh', 'jeddah', 'الرياض']
        found_indicators = [ind for ind in saudi_indicators if ind in text.lower()]
        if found_indicators:
            score += 30
            details["saudi_indicators"] = found_indicators
            print(f"     ✅ Saudi indicators found: {found_indicators}")
        else:
            issues.append("Document jurisdiction unclear - should be from Saudi Arabia")
            recommendations.append("Verify document is issued by Saudi authorities")
            print("     ❌ Saudi indicators not found")
        
        return {
            "is_valid": score >= 70,
            "score": score,
            "issues": issues,
            "recommendations": recommendations,
            "details": details
        }
    
    def _validate_national_id(self, text: str) -> Dict[str, Any]:
        """Validate Saudi National ID"""
        issues = []
        recommendations = []
        details = {}
        score = 0
        
        print("     📋 Checking National ID requirements...")
        
        # Check for Saudi ID pattern (10 digits starting with 1 or 2)
        id_pattern = r'\b[12]\d{9}\b'
        id_match = re.search(id_pattern, text)
        if id_match:
            score += 40
            details["national_id"] = id_match.group()
            print(f"     ✅ Valid Saudi National ID found: {id_match.group()}")
        else:
            issues.append("Valid Saudi National ID number (10 digits, starts with 1 or 2) not found")
            recommendations.append("Ensure National ID number is clearly visible")
            print("     ❌ Valid Saudi National ID not found")
        
        # Check for Arabic text
        arabic_pattern = r'[\u0600-\u06FF]+'
        if re.search(arabic_pattern, text):
            score += 30
            print("     ✅ Arabic text detected")
        else:
            issues.append("Arabic text not detected - may not be official Saudi document")
            recommendations.append("Ensure document contains Arabic text")
            print("     ❌ Arabic text not found")
        
        # Check for identity-related keywords
        id_keywords = ['identity', 'national', 'هوية', 'وطنية', 'card', 'بطاقة']
        found_keywords = [kw for kw in id_keywords if kw in text.lower()]
        if found_keywords:
            score += 30
            details["identity_keywords"] = found_keywords
            print(f"     ✅ Identity keywords found: {found_keywords}")
        else:
            issues.append("Identity document keywords not found")
            print("     ❌ Identity keywords not found")
        
        return {
            "is_valid": score >= 70,
            "score": score,
            "issues": issues,
            "recommendations": recommendations,
            "details": details
        }
    
    def _validate_bank_statements(self, text: str) -> Dict[str, Any]:
        """Validate bank statements"""
        issues = []
        recommendations = []
        details = {}
        score = 0
        
        print("     📋 Checking bank statement requirements...")
        
        # Check for bank indicators
        bank_keywords = ['bank', 'بنك', 'account', 'حساب', 'statement', 'كشف', 'balance', 'رصيد']
        found_keywords = [kw for kw in bank_keywords if kw in text.lower()]
        if found_keywords:
            score += 30
            details["bank_keywords"] = found_keywords
            print(f"     ✅ Bank keywords found: {found_keywords}")
        else:
            issues.append("Bank statement indicators not found")
            print("     ❌ Bank keywords not found")
        
        # Check for account numbers or IBAN
        account_patterns = [r'\bSA\d{22}\b', r'\b\d{10,20}\b']
        accounts_found = []
        for pattern in account_patterns:
            accounts_found.extend(re.findall(pattern, text))
        
        if accounts_found:
            score += 35
            details["account_numbers"] = accounts_found[:2]  # Limit for privacy
            print(f"     ✅ Account numbers found: {len(accounts_found)} accounts")
        else:
            issues.append("Account number or IBAN not found")
            recommendations.append("Ensure account number/IBAN is visible")
            print("     ❌ Account numbers not found")
        
        # Check for Saudi currency
        currency_patterns = ['SAR', 'SR', 'ريال', 'رس']
        found_currency = [curr for curr in currency_patterns if curr in text]
        if found_currency:
            score += 35
            details["currency"] = found_currency
            print(f"     ✅ Saudi currency found: {found_currency}")
        else:
            issues.append("Saudi currency (SAR) not detected")
            recommendations.append("Ensure statement shows SAR currency")
            print("     ❌ Saudi currency not found")
        
        return {
            "is_valid": score >= 70,
            "score": score,
            "issues": issues,
            "recommendations": recommendations,
            "details": details
        }
    
    def _validate_tax_certificate(self, text: str) -> Dict[str, Any]:
        """Validate tax certificate"""
        issues = []
        recommendations = []
        details = {}
        score = 0
        
        print("     📋 Checking tax certificate requirements...")
        
        # Check for tax keywords
        tax_keywords = ['tax', 'ضريبة', 'vat', 'ضريبة القيمة المضافة', 'certificate', 'شهادة']
        found_keywords = [kw for kw in tax_keywords if kw in text.lower()]
        if found_keywords:
            score += 40
            details["tax_keywords"] = found_keywords
            print(f"     ✅ Tax keywords found: {found_keywords}")
        else:
            issues.append("Tax certificate indicators not found")
            print("     ❌ Tax keywords not found")
        
        # Check for VAT number (15 digits)
        vat_pattern = r'\b\d{15}\b'
        vat_match = re.search(vat_pattern, text)
        if vat_match:
            score += 35
            details["vat_number"] = vat_match.group()
            print(f"     ✅ VAT number found: {vat_match.group()}")
        else:
            issues.append("15-digit VAT registration number not found")
            recommendations.append("Ensure VAT number is clearly visible")
            print("     ❌ VAT number not found")
        
        # Check for certificate validity
        validity_keywords = ['valid', 'issued', 'expiry', 'صالح', 'صادر']
        if any(kw in text.lower() for kw in validity_keywords):
            score += 25
            print("     ✅ Validity indicators found")
        else:
            issues.append("Certificate validity information unclear")
            print("     ❌ Validity indicators not found")
        
        return {
            "is_valid": score >= 70,
            "score": score,
            "issues": issues,
            "recommendations": recommendations,
            "details": details
        }
    
    def _store_validation_result(self, result: Dict[str, Any]):
        """Store validation result in database"""
        try:
            session = get_database_session()
            
            validation = KYCValidation(
                document_id=result["document_id"],
                customer_id=result["customer_id"],
                document_type=result["document_type"],
                is_valid=result["is_valid"],
                validation_score=result["validation_score"],
                issues=json.dumps(result["issues"]),
                recommendations=json.dumps(result["recommendations"])
            )
            
            session.add(validation)
            session.commit()
            session.close()
            
            print("     💾 Validation result stored in database")
            
        except Exception as e:
            logger.error(f"Database storage error: {e}")
            print(f"     ❌ Database storage failed: {e}")
    
    def _print_validation_summary(self, result: Dict[str, Any]):
        """Print a nice summary of validation results"""
        print(f"\n📊 VALIDATION SUMMARY")
        print(f"=" * 40)
        print(f"📄 Document: {result['filename']}")
        print(f"📝 Type: {result['document_type']}")
        print(f"✅ Valid: {'YES' if result['is_valid'] else 'NO'}")
        print(f"📊 Score: {result['validation_score']}/100")
        
        if result['issues']:
            print(f"\n❌ Issues Found ({len(result['issues'])}):")
            for i, issue in enumerate(result['issues'], 1):
                print(f"   {i}. {issue}")
        
        if result['recommendations']:
            print(f"\n💡 Recommendations ({len(result['recommendations'])}):")
            for i, rec in enumerate(result['recommendations'], 1):
                print(f"   {i}. {rec}")
        
        print(f"=" * 40)


# Test function
def test_kyc_agent():
    """Test the KYC validation agent"""
    print("🚀 Testing KYC Validation Agent")
    print("=" * 50)
    
    # Create agent
    agent = KYCValidationAgent()
    
    # Test documents
    test_documents = [
        {
            "filename": "commercial_registration.txt",
            "text": """
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
            """,
            "customer_id": "CUST123"
        },
        {
            "filename": "national_id.txt", 
            "text": """
NATIONAL IDENTITY CARD
هوية وطنية

ID Number: 1098765432
Name: Ahmed Mohammed Al-Saudi
Date of Birth: 1985-03-20
Nationality: Saudi Arabian
Issue Date: 2020-01-01
Expiry Date: 2030-01-01
            """,
            "customer_id": "CUST123"
        }
    ]
    
    # Test each document
    results = []
    for i, doc in enumerate(test_documents, 1):
        print(f"\n{'='*60}")
        print(f"TEST {i}: {doc['filename']}")
        print(f"{'='*60}")
        
        doc_id = f"test_doc_{i}"
        result = agent.validate_kyc_document(
            document_id=doc_id,
            extracted_text=doc['text'],
            filename=doc['filename'],
            customer_id=doc['customer_id']
        )
        results.append(result)
    
    # Overall summary
    print(f"\n{'='*60}")
    print(f"🎉 KYC TESTING COMPLETE!")
    print(f"{'='*60}")
    print(f"📊 Overall Results:")
    valid_docs = sum(1 for r in results if r['is_valid'])
    print(f"   ✅ Valid documents: {valid_docs}/{len(results)}")
    print(f"   📊 Average score: {sum(r['validation_score'] for r in results)/len(results):.1f}/100")
    
    return agent, results

if __name__ == "__main__":
    test_kyc_agent()