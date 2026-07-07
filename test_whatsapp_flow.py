# File: check_webhook_updates.py
import os
import sys
import django
from datetime import datetime, timedelta

project_root = r"C:\Users\Shwetdhara\Desktop\shwetDhara_Project_v3\shwetDhara_project"
sys.path.insert(0, project_root)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'shwetDhara_project.settings')

try:
    django.setup()
    
    from main_app.models import WhatsAppLog
    from django.utils import timezone
    
    print("🔍 CHECKING WEBHOOK UPDATES")
    print("=" * 60)
    
    current_time = timezone.now()
    
    # Check last 1 hour
    one_hour_ago = current_time - timedelta(hours=1)
    
    print(f"Checking updates since: {one_hour_ago.strftime('%H:%M:%S')}")
    print(f"Current time: {current_time.strftime('%H:%M:%S')}")
    print()
    
    # Count status updates in last hour
    recent_sent = WhatsAppLog.objects.filter(
        status='SENT',
        sent_at__gte=one_hour_ago
    ).count()
    
    recent_delivered = WhatsAppLog.objects.filter(
        status='DELIVERED',
        delivered_at__gte=one_hour_ago
    ).count()
    
    recent_read = WhatsAppLog.objects.filter(
        status='READ',
        read_at__gte=one_hour_ago
    ).count()
    
    print(f"📤 SENT in last hour: {recent_sent}")
    print(f"📨 DELIVERED in last hour: {recent_delivered}")
    print(f"📖 READ in last hour: {recent_read}")
    
    if recent_sent > 0 and recent_delivered == 0 and recent_read == 0:
        print("\n🚨 **CRITICAL ISSUE:**")
        print("   Messages are being SENT but NOT getting delivery/read updates!")
        print("   This means webhook is NOT receiving status updates.")
    
    # Check specific problem message
    print("\n🔍 SPECIFIC PROBLEM MESSAGE:")
    print("-" * 40)
    
    problem_message = WhatsAppLog.objects.filter(
        mobile_number='917518060480',
        sent_at__gte=one_hour_ago,
        status='SENT'
    ).order_by('-sent_at').first()
    
    if problem_message:
        print(f"Mobile: {problem_message.mobile_number}")
        print(f"Sent: {problem_message.sent_at.strftime('%H:%M:%S')}")
        print(f"Status: {problem_message.status}")
        print(f"Message ID: {problem_message.template_message_id}")
        
        time_since_sent = (current_time - problem_message.sent_at).total_seconds() / 60
        print(f"Time since sent: {time_since_sent:.1f} minutes")
        
        if time_since_sent > 5:
            print(f"⚠️  WARNING: Message sent {time_since_sent:.1f} minutes ago but no delivery update!")
    
    # Check webhook activity pattern
    print("\n📊 WEBHOOK ACTIVITY PATTERN (Last 24h):")
    print("-" * 40)
    
    for hours_ago in [1, 3, 6, 12, 24]:
        cutoff = current_time - timedelta(hours=hours_ago)
        
        read_count = WhatsAppLog.objects.filter(
            status='READ',
            read_at__gte=cutoff
        ).count()
        
        delivered_count = WhatsAppLog.objects.filter(
            status='DELIVERED', 
            delivered_at__gte=cutoff
        ).count()
        
        print(f"   Last {hours_ago:2d}h: READ={read_count:3d}, DELIVERED={delivered_count:3d}")
    
    # Manual webhook test
    print("\n🔧 QUICK WEBHOOK TEST:")
    print("-" * 40)
    print("To test if webhook is working, send a test message to:")
    print("   Mobile: 917518060480")
    print("Then check if it gets marked as DELIVERED/READ within 2 minutes")
    
    print("=" * 60)
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()