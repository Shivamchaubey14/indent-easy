# whatsapp_desktop_service.py

"""
SIMPLIFIED WHATSAPP DESKTOP SERVICE
Only sends messages, doesn't try to manage status
"""
from django.utils import timezone
import os
import sys
import time
import logging

# CRITICAL: Set your exact path
project_root = r"C:\Users\Shwetdhara\Desktop\shwetDhara_Project_v3\shwetDhara_project"
sys.path.insert(0, project_root)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'shwetDhara_project.settings')

print("🔄 Setting up WhatsApp Desktop Service...")

try:
    import django
    django.setup()
    print("✅ Django setup successful")
except Exception as e:
    print(f"❌ Django setup failed: {e}")
    sys.exit(1)

# Import WhatsApp manager
try:
    from main_app.tasks_sequential import WhatsAppAutoManager
    manager = WhatsAppAutoManager.get_instance()
    print("✅ WhatsApp manager loaded")
except Exception as e:
    print(f"❌ Failed to load WhatsApp manager: {e}")
    sys.exit(1)

# Setup logging
log_file = os.path.join(project_root, 'whatsapp_service.log')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [WhatsApp Service] - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def send_pending_messages():
    """Send all pending WhatsApp messages"""
    try:
        from main_app.models import MessageQueue
        
        # Get PENDING WhatsApp messages
        pending_messages = MessageQueue.objects.filter(
            message_type='WHATSAPP',
            status='PENDING'
        ).order_by('id')[:5]  # Process max 5 at a time
        
        if not pending_messages:
            return 0
        
        print(f"📱 Found {pending_messages.count()} pending messages")
        
        sent_count = 0
        
        for message in pending_messages:
            try:
                logger.info(f"Processing: {message.id} -> {message.mobile_number}")
                
                # Ensure WhatsApp is ready
                if not manager.ensure_whatsapp_ready():
                    logger.error("WhatsApp not ready, skipping...")
                    time.sleep(5)
                    continue
                
                # Send message
                success = manager.send_message_auto(
                    phone_number=message.mobile_number,
                    message=message.message
                )
                
                if success:
                    # Mark as SENT
                    message.status = 'SENT'
                    message.sent_at = timezone.now()
                    message.completed_at = timezone.now()
                    message.save()
                    
                    # Create audit log
                    try:
                        from main_app.models import WhatsAppLog
                        WhatsAppLog.objects.create(
                            mobile_number=message.mobile_number,
                            message=message.message[:500],
                            unique_code=message.unique_code,
                            mpp_name=message.mpp_name,
                            status='SENT',
                            sent_via='WINDOWS_DESKTOP'
                        )
                    except:
                        pass
                    
                    sent_count += 1
                    logger.info(f"✅ Sent to {message.mobile_number}")
                    
                    # Delay between messages
                    time.sleep(3)
                    
                else:
                    # Mark for retry
                    message.status = 'RETRY'
                    message.save()
                    logger.warning(f"↻ Failed, marked for retry: {message.mobile_number}")
                    
            except Exception as e:
                logger.error(f"Error sending message {message.id}: {e}")
                # Mark for retry
                message.status = 'RETRY'
                message.save()
        
        return sent_count
        
    except Exception as e:
        logger.error(f"Error in send_pending_messages: {e}")
        return 0

def main():
    """Main service loop"""
    print("\n" + "=" * 60)
    print("🚀 WHATSAPP DESKTOP SERVICE")
    print("=" * 60)
    print("Status: RUNNING")
    print("Checking for messages every 10 seconds...")
    print("Press Ctrl+C to stop")
    print("=" * 60 + "\n")
    
    logger.info("WhatsApp Desktop Service Started")
    
    total_sent = 0
    
    try:
        while True:
            try:
                # Send pending messages
                sent_now = send_pending_messages()
                
                if sent_now > 0:
                    total_sent += sent_now
                    print(f"📊 Sent {sent_now} messages, Total: {total_sent}")
                else:
                    # No messages, wait
                    time.sleep(10)
                    
            except KeyboardInterrupt:
                print("\n🛑 Service stopped by user")
                break
            except Exception as e:
                print(f"❌ Error in main loop: {e}")
                time.sleep(10)
                
    finally:
        print(f"\n🏁 Service stopped. Total messages sent: {total_sent}")
        logger.info(f"Service stopped. Total messages sent: {total_sent}")

if __name__ == "__main__":
    main()