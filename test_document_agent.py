import sys
import os

# Add src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def main():
    print("🚀 Starting Document Ingestion Agent Test")
    print("=" * 60)
    
    try:
        # Import and test the agent
        from src.copilots.compliance.document_ingestion.simple_agent import test_agent
        
        # Run the test
        agent = test_agent()
        
        print("\n" + "=" * 60)
        print("✅ Test completed successfully!")
        print("Your Document Ingestion Agent is working!")
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Make sure you're in the right directory and have installed dependencies")
        print(f"Current directory: {os.getcwd()}")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        print("Check the error message above for details")

if __name__ == "__main__":
    main()