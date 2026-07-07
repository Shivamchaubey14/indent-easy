# apps.py in your main_app
from django.apps import AppConfig
import logging
import threading
import time
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)

class MainAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'main_app'
    
    def ready(self):
        # Start a background thread to check for pending messages
        def background_message_processor():
            """Background thread to process pending messages"""
            time.sleep(10)  # Wait longer for app to fully start
            
            try:
                # Import inside thread to avoid circular imports
                from .models import MessageQueue
                from .tasks_sequential import process_message_queue
                
                # Check for pending messages
                pending_messages = MessageQueue.objects.filter(
                    status='PENDING'
                ).exists()
                
                if pending_messages:
                    logger.info("Found pending messages on startup, starting processor...")
                    # Start the message queue processor
                    process_message_queue.delay()
                else:
                    logger.info("No pending messages found on startup")
                    
            except Exception as e:
                logger.error(f"Error in background message processor: {e}")
        
        # Start the background thread
        thread = threading.Thread(target=background_message_processor, daemon=True)
        thread.start()
        logger.info("Background message processor thread started")