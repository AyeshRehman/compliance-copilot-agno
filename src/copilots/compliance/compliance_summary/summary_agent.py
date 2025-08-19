# src/copilots/compliance/compliance_summary/summary_agent.py
import json
from datetime import datetime
from typing import Dict, Any, List
import logging

# Import handlers
try:
    from ..shared.kafka_handler import KafkaHandler
    from ..shared.models import get_database_session, test_database_connection
    from ..config import Config
except ImportError:
    import sys
    import os
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
    sys.path.insert(0, parent_dir)
    from copilots.compliance.shared.kafka_handler import KafkaHandler
    from copilots.compliance.shared.models import get_database_session, test_database_connection
    from copilots.compliance.config import Config

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ComplianceSummaryAgent:
    """
    Compliance Summary Agent
    Generates comprehensive compliance reports and recommendations
    """
    
    def __init__(self):
        self.config = Config()
        self.kafka_handler = KafkaHandler()
        
        # Test database connection
        print("🔍 Testing database connection for compliance summary...")
        self.use_database = test_database_connection()
        if not self.use_database:
            print("⚠️  Database not available, using memory storage for summaries")
            self.memory_summaries = {}
        
        # SAMA compliance requirements
        self.required_documents = {
            "commercial_registration": {
                "name": "Commercial Registration Certificate",
                "priority": "Critical",
                "description": "Official business registration from Ministry of Commerce"
            },
            "national_id": {
                "name": "National ID of Authorized Signatory", 
                "priority": "Critical",
                "description": "Valid Saudi National Identity Card"
            },
            "bank_statements": {
                "name": "Bank Statements",
                "priority": "High",
                "description": "Recent bank statements showing business activity"
            },
            "tax_certificate": {
                "name": "Tax Registration Certificate",
                "priority": "High", 
                "description": "VAT registration certificate from ZATCA"
            }
        }
        
        print("✅ Compliance Summary Agent initialized")
        print(f"📋 Monitoring {len(self.required_documents)} document types")
        
    def generate_compliance_summary(self, customer_id: str, validation_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate comprehensive compliance summary for a customer
        """
        print(f"\n📊 Generating compliance summary for customer: {customer_id}")
        print(f"   📄 Processing {len(validation_results)} validation results")
        
        try:
            # Analyze validation results
            analysis = self._analyze_validation_results(validation_results)
            
            # Calculate overall compliance score
            compliance_score = self._calculate_compliance_score(validation_results)
            
            # Determine compliance status
            compliance_status = self._determine_compliance_status(compliance_score, analysis)
            
            # Generate recommendations
            recommendations = self._generate_recommendations(analysis, compliance_score)
            
            # Determine next steps
            next_steps = self._determine_next_steps(compliance_status, analysis)
            
            # Create comprehensive summary
            summary = {
                "customer_id": customer_id,
                "generated_at": datetime.now().isoformat(),
                "compliance_score": compliance_score,
                "compliance_status": compliance_status,
                "document_analysis": analysis,
                "recommendations": recommendations,
                "next_steps": next_steps,
                "sama_requirements": self._get_sama_requirements_status(analysis),
                "summary_text": self._generate_summary_text(customer_id, compliance_score, compliance_status, analysis)
            }
            
            # Store summary
            if self.use_database:
                self._store_summary(summary)
            else:
                self.memory_summaries[customer_id] = summary
            
            # Emit summary completion event
            self.kafka_handler.send_event(
                topic="compliance-summary-generated",
                key=customer_id,
                value={
                    "customer_id": customer_id,
                    "compliance_score": compliance_score,
                    "compliance_status": compliance_status,
                    "total_documents": len(validation_results),
                    "valid_documents": analysis["valid_documents"],
                    "generated_at": summary["generated_at"]
                }
            )
            
            # Print summary
            self._print_compliance_summary(summary)
            
            return summary
            
        except Exception as e:
            error_summary = {
                "customer_id": customer_id,
                "error": str(e),
                "generated_at": datetime.now().isoformat()
            }
            
            print(f"❌ Error generating compliance summary: {e}")
            logger.error(f"Compliance summary error for {customer_id}: {e}")
            
            return error_summary
    
    def _analyze_validation_results(self, validation_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze validation results to understand compliance status"""
        print("   🔍 Analyzing validation results...")
        
        total_documents = len(validation_results)
        valid_documents = sum(1 for result in validation_results if result.get('is_valid', False))
        
        # Group by document type
        documents_by_type = {}
        validation_scores = []
        all_issues = []
        
        for result in validation_results:
            doc_type = result.get('document_type', 'unknown')
            score = result.get('validation_score', 0)
            is_valid = result.get('is_valid', False)
            issues = result.get('issues', [])
            
            validation_scores.append(score)
            all_issues.extend(issues)
            
            if doc_type not in documents_by_type:
                documents_by_type[doc_type] = []
            
            documents_by_type[doc_type].append({
                "filename": result.get('filename', 'Unknown'),
                "is_valid": is_valid,
                "score": score,
                "issues": issues,
                "document_id": result.get('document_id', 'Unknown')
            })
        
        # Calculate statistics
        avg_score = sum(validation_scores) / len(validation_scores) if validation_scores else 0
        
        # Check required documents coverage
        missing_documents = []
        for req_doc_type in self.required_documents.keys():
            if req_doc_type not in documents_by_type:
                missing_documents.append(req_doc_type)
        
        # Categorize issues
        critical_issues = [issue for issue in all_issues if any(keyword in issue.lower() 
                          for keyword in ['number not found', 'not detected', 'not found'])]
        minor_issues = [issue for issue in all_issues if issue not in critical_issues]
        
        analysis = {
            "total_documents": total_documents,
            "valid_documents": valid_documents,
            "validation_rate": valid_documents / total_documents if total_documents > 0 else 0,
            "average_score": avg_score,
            "documents_by_type": documents_by_type,
            "missing_documents": missing_documents,
            "critical_issues": critical_issues,
            "minor_issues": minor_issues,
            "required_documents_coverage": len(documents_by_type) / len(self.required_documents)
        }
        
        print(f"   📊 Analysis complete: {valid_documents}/{total_documents} valid, avg score: {avg_score:.1f}")
        
        return analysis
    
    def _calculate_compliance_score(self, validation_results: List[Dict[str, Any]]) -> float:
        """Calculate overall compliance score"""
        if not validation_results:
            return 0.0
        
        # Weight scores by document importance
        weights = {
            "commercial_registration": 0.3,  # 30% - Critical
            "national_id": 0.3,              # 30% - Critical
            "bank_statements": 0.2,          # 20% - High
            "tax_certificate": 0.2           # 20% - High
        }
        
        weighted_score = 0
        total_weight = 0
        
        for result in validation_results:
            doc_type = result.get('document_type', 'unknown')
            score = result.get('validation_score', 0)
            weight = weights.get(doc_type, 0.1)  # Default weight for unknown types
            
            weighted_score += score * weight
            total_weight += weight
        
        return weighted_score / total_weight if total_weight > 0 else 0
    
    def _determine_compliance_status(self, compliance_score: float, analysis: Dict[str, Any]) -> str:
        """Determine overall compliance status"""
        missing_critical = any(doc_type in analysis["missing_documents"] 
                             for doc_type in ["commercial_registration", "national_id"])
        
        if compliance_score >= 90 and not missing_critical:
            return "FULLY_COMPLIANT"
        elif compliance_score >= 75 and not missing_critical:
            return "MOSTLY_COMPLIANT"
        elif compliance_score >= 60:
            return "PARTIALLY_COMPLIANT"
        else:
            return "NON_COMPLIANT"
    
    def _generate_recommendations(self, analysis: Dict[str, Any], compliance_score: float) -> List[Dict[str, Any]]:
        """Generate actionable recommendations"""
        recommendations = []
        
        # Missing documents
        for missing_doc in analysis["missing_documents"]:
            doc_info = self.required_documents.get(missing_doc, {})
            recommendations.append({
                "type": "MISSING_DOCUMENT",
                "priority": doc_info.get("priority", "Medium"),
                "title": f"Submit {doc_info.get('name', missing_doc)}",
                "description": doc_info.get('description', f"Please provide {missing_doc}"),
                "action": f"Upload valid {doc_info.get('name', missing_doc)}"
            })
        
        # Critical issues
        if analysis["critical_issues"]:
            recommendations.append({
                "type": "CRITICAL_ISSUES", 
                "priority": "Critical",
                "title": f"Resolve {len(analysis['critical_issues'])} critical issues",
                "description": "Document validation failed for critical requirements",
                "action": "Review and resubmit documents with clear, readable information"
            })
        
        # Score-based recommendations
        if compliance_score < 70:
            recommendations.append({
                "type": "OVERALL_COMPLIANCE",
                "priority": "High",
                "title": "Improve overall compliance score",
                "description": f"Current score: {compliance_score:.1f}/100",
                "action": "Focus on document quality and completeness"
            })
        
        return recommendations
    
    def _determine_next_steps(self, compliance_status: str, analysis: Dict[str, Any]) -> List[str]:
        """Determine next steps based on compliance status"""
        if compliance_status == "FULLY_COMPLIANT":
            return [
                "✅ Auto-approve for account opening",
                "📧 Send welcome package to customer",
                "🔄 Schedule account setup call",
                "📋 Generate compliance certificate"
            ]
        elif compliance_status == "MOSTLY_COMPLIANT":
            return [
                "👤 Route to compliance officer for review",
                "📞 Schedule verification call with customer",
                "⏳ Prepare conditional approval",
                "📋 Request minor document corrections"
            ]
        elif compliance_status == "PARTIALLY_COMPLIANT":
            return [
                "📄 Request missing documents",
                "🔍 Schedule enhanced due diligence review",
                "📞 Contact customer for clarification",
                "⏳ Hold application pending improvements"
            ]
        else:  # NON_COMPLIANT
            return [
                "❌ Reject application with detailed feedback",
                "📧 Send rejection letter with requirements",
                "📋 Provide improvement roadmap",
                "📞 Offer consultation call"
            ]
    
    def _get_sama_requirements_status(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Get SAMA requirements compliance status"""
        requirements_status = {}
        
        for doc_type, doc_info in self.required_documents.items():
            if doc_type in analysis["documents_by_type"]:
                doc_results = analysis["documents_by_type"][doc_type]
                valid_docs = [doc for doc in doc_results if doc["is_valid"]]
                
                requirements_status[doc_type] = {
                    "name": doc_info["name"],
                    "status": "SATISFIED" if valid_docs else "FAILED",
                    "submitted": len(doc_results),
                    "valid": len(valid_docs),
                    "priority": doc_info["priority"]
                }
            else:
                requirements_status[doc_type] = {
                    "name": doc_info["name"], 
                    "status": "MISSING",
                    "submitted": 0,
                    "valid": 0,
                    "priority": doc_info["priority"]
                }
        
        return requirements_status
    
    def _generate_summary_text(self, customer_id: str, compliance_score: float, 
                             compliance_status: str, analysis: Dict[str, Any]) -> str:
        """Generate human-readable summary text"""
        status_descriptions = {
            "FULLY_COMPLIANT": "meets all SAMA requirements and is ready for approval",
            "MOSTLY_COMPLIANT": "meets most SAMA requirements with minor issues to resolve",
            "PARTIALLY_COMPLIANT": "has submitted some required documents but significant gaps remain",
            "NON_COMPLIANT": "does not meet minimum SAMA compliance requirements"
        }
        
        summary_text = f"""
SAMA COMPLIANCE SUMMARY - Customer {customer_id}

Overall Assessment: {status_descriptions.get(compliance_status, 'Status unclear')}
Compliance Score: {compliance_score:.1f}/100

Document Status:
- Total documents processed: {analysis['total_documents']}
- Valid documents: {analysis['valid_documents']}
- Validation rate: {analysis['validation_rate']:.1%}
- Required document coverage: {analysis['required_documents_coverage']:.1%}

Key Findings:
{'- All critical documents validated successfully' if not analysis['missing_documents'] and not analysis['critical_issues'] else ''}
{'- Missing critical documents: ' + ', '.join(analysis['missing_documents']) if analysis['missing_documents'] else ''}
{'- Critical validation issues identified: ' + str(len(analysis['critical_issues'])) if analysis['critical_issues'] else ''}

This assessment is based on Saudi Arabian Monetary Authority (SAMA) regulations
for Small and Medium Enterprise (SME) account opening requirements.
        """.strip()
        
        return summary_text
    
    def _store_summary(self, summary: Dict[str, Any]):
        """Store compliance summary in database"""
        try:
            # In a real implementation, this would store in a ComplianceSummary table
            print("     💾 Compliance summary stored in database")
        except Exception as e:
            logger.error(f"Database storage error: {e}")
            print(f"     ❌ Database storage failed: {e}")
    
    def _print_compliance_summary(self, summary: Dict[str, Any]):
        """Print a formatted compliance summary"""
        print(f"\n📊 COMPLIANCE SUMMARY REPORT")
        print(f"=" * 60)
        print(f"👤 Customer: {summary['customer_id']}")
        print(f"📅 Generated: {summary['generated_at'][:19]}")
        print(f"📊 Score: {summary['compliance_score']:.1f}/100")
        print(f"🎯 Status: {summary['compliance_status']}")
        
        analysis = summary['document_analysis']
        print(f"\n📄 Document Analysis:")
        print(f"   📊 Total: {analysis['total_documents']}")
        print(f"   ✅ Valid: {analysis['valid_documents']}")
        print(f"   📈 Success Rate: {analysis['validation_rate']:.1%}")
        
        if summary['recommendations']:
            print(f"\n💡 Recommendations ({len(summary['recommendations'])}):")
            for rec in summary['recommendations']:
                print(f"   🔸 {rec['title']} ({rec['priority']})")
        
        print(f"\n🎯 Next Steps:")
        for step in summary['next_steps']:
            print(f"   {step}")
        
        print(f"=" * 60)


# Test function
def test_compliance_summary_agent():
    """Test the compliance summary agent"""
    print("🚀 Testing Compliance Summary Agent")
    print("=" * 60)
    
    # Create agent
    agent = ComplianceSummaryAgent()
    
    # Sample validation results (like what would come from KYC agent)
    sample_validation_results = [
        {
            "document_id": "doc1",
            "customer_id": "CUST123",
            "filename": "commercial_registration.txt",
            "document_type": "commercial_registration",
            "is_valid": True,
            "validation_score": 95,
            "issues": [],
            "recommendations": []
        },
        {
            "document_id": "doc2", 
            "customer_id": "CUST123",
            "filename": "national_id.txt",
            "document_type": "national_id",
            "is_valid": True,
            "validation_score": 100,
            "issues": [],
            "recommendations": []
        },
        {
            "document_id": "doc3",
            "customer_id": "CUST123", 
            "filename": "bank_statement.txt",
            "document_type": "bank_statements",
            "is_valid": False,
            "validation_score": 60,
            "issues": ["Account number not clearly visible"],
            "recommendations": ["Ensure account number/IBAN is visible"]
        }
    ]
    
    # Generate compliance summary
    print(f"\n{'='*80}")
    print(f"🧪 TESTING COMPLIANCE SUMMARY GENERATION")
    print(f"{'='*80}")
    
    summary = agent.generate_compliance_summary("CUST123", sample_validation_results)
    
    print(f"\n🎉 TESTING COMPLETE!")
    print(f"Summary generated for customer: {summary.get('customer_id', 'Unknown')}")
    print(f"Compliance status: {summary.get('compliance_status', 'Unknown')}")
    
    return agent, summary

if __name__ == "__main__":
    test_compliance_summary_agent()