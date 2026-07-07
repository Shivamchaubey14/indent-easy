# force_process.py
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'shwetDhara_project.settings')
django.setup()

from main_app.tasks_sequential import process_message_queue
from main_app.models import MessageQueue
import time

print("🚨 FORCING MESSAGE PROCESSING")
print("=" * 60)

# Check pending messages
pending = MessageQueue.objects.filter(status='PENDING').count()
print(f"📊 Pending messages: {pending}")

if pending == 0:
    print("✅ No pending messages")
    exit()

print("\n🚀 Starting processing...")

# Trigger processing multiple times (one message at a time)
for i in range(pending):
    print(f"\n🔄 Processing message {i+1} of {pending}...")
    
    # Call directly (bypass Celery for reliability)
    try:
        process_message_queue()
        print(f"✅ Message {i+1} processed")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    time.sleep(5)  # Rate limiting

print("\n🎯 Processing complete!")
print("\n📊 Final Status:")
for msg in MessageQueue.objects.all():
    print(f"  {msg.id}: {msg.message_type} -> {msg.status}")