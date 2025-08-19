# src/copilots/compliance/shared/kafka_handler.py
import json
from datetime import datetime
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

class MockKafkaHandler:
    """Mock Kafka handler for testing without actual Kafka setup"""
    
    def __init__(self):
        self.events = []  # Store events in memory for testing
        print("📤 Mock Kafka Handler initialized (events will be stored in memory)")
    
    def send_event(self, topic: str, key: str, value: Dict[Any, Any]):
        """Mock event sending - stores in memory"""
        event = {
            "topic": topic,
            "key": key,
            "value": value,
            "timestamp": datetime.now().isoformat()
        }
        self.events.append(event)
        logger.info(f"📤 Mock event sent to {topic}: {key}")
        print(f"📤 Event: {topic} -> {key}")
        print(f"   📋 Data: {json.dumps(value, indent=2)}")
    
    def get_events(self, topic: str = None) -> list:
        """Get stored events (for testing)"""
        if topic:
            return [e for e in self.events if e["topic"] == topic]
        return self.events
    
    def clear_events(self):
        """Clear stored events"""
        self.events = []
        print("🗑️  Cleared all events")

try:
    from kafka import KafkaProducer, KafkaConsumer
    KAFKA_AVAILABLE = True
except ImportError:
    KAFKA_AVAILABLE = False
    logger.warning("Kafka not installed, using mock handler")

class KafkaHandler:
    """Kafka handler that auto-detects if Kafka is available"""
    
    def __init__(self, bootstrap_servers: str = "localhost:9092", use_mock: bool = None):
        # Auto-detect if we should use mock
        if use_mock is None:
            use_mock = not KAFKA_AVAILABLE
        
        if use_mock or not KAFKA_AVAILABLE:
            self.handler = MockKafkaHandler()
            self.is_mock = True
            print("⚠️  Using Mock Kafka (no real Kafka connection)")
        else:
            try:
                self.producer = KafkaProducer(
                    bootstrap_servers=[bootstrap_servers],
                    value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                    key_serializer=lambda k: k.encode('utf-8') if k else None
                )
                self.is_mock = False
                print("✅ Connected to real Kafka")
                logger.info("✅ Connected to Kafka")
            except Exception as e:
                logger.warning(f"Could not connect to Kafka: {e}, using mock")
                print(f"⚠️  Kafka connection failed: {e}")
                print("   Using Mock Kafka instead")
                self.handler = MockKafkaHandler()
                self.is_mock = True
    
    def send_event(self, topic: str, key: str, value: Dict[Any, Any]):
        """Send event to Kafka or mock"""
        if self.is_mock:
            self.handler.send_event(topic, key, value)
        else:
            try:
                future = self.producer.send(topic, key=key, value=value)
                self.producer.flush()
                logger.info(f"📤 Event sent to Kafka topic {topic}: {key}")
                print(f"📤 Real Kafka event sent: {topic} -> {key}")
            except Exception as e:
                logger.error(f"Failed to send Kafka event: {e}")
                print(f"❌ Kafka send failed: {e}")
    
    def get_events(self, topic: str = None) -> list:
        """Get events (only works with mock)"""
        if self.is_mock:
            return self.handler.get_events(topic)
        else:
            print("⚠️  Event retrieval only available with Mock Kafka")
            return []
    
    def clear_events(self):
        """Clear events (only works with mock)"""
        if self.is_mock:
            self.handler.clear_events()
        else:
            print("⚠️  Event clearing only available with Mock Kafka")