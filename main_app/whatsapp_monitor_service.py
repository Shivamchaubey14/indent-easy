"""
WhatsApp Real-Time Status Monitor (FIXED VERSION)
Fixed: Replaced updated_at with created_at
"""
import os
import sys
import time
import json
import logging
import threading
from datetime import datetime, timedelta
from django.db import models
from django.db.models import Q, Count, F, ExpressionWrapper, DurationField
from django.utils import timezone

# Add project to path
project_root = r"C:\Users\Shwetdhara\Desktop\shwetDhara_Project_v3\shwetDhara_project"
sys.path.insert(0, project_root)

# Set Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'shwetDhara_project.settings')

import django
django.setup()

from main_app.models import WhatsAppLog, MessageQueue, MPPWithCode, SMSQueue
from django.conf import settings

# Configure logging - SAFE FOR WINDOWS
class SafeLogger:
    """Safe logger that handles Windows console encoding issues"""
    
    def __init__(self, name):
        self.logger = logging.getLogger(name)
        
        # Remove emojis and non-ASCII chars
        self.emoji_map = {
            '🚀': '[ROCKET]', '📱': '[PHONE]', '✅': '[OK]', '❌': '[ERROR]', 
            '⚠️': '[WARN]', '📊': '[CHART]', '📨': '[MAIL]', '👁️': '[READ]', 
            '📵': '[NO-WHATSAPP]', '🚨': '[ALERT]', '🔒': '[LOCK]', '🔍': '[SEARCH]',
            '📖': '[BOOK]', '💡': '[IDEA]', '⏰': '[CLOCK]', '🔄': '[REFRESH]',
            '📈': '[UP]', '📉': '[DOWN]', '📌': '[PIN]', '🎯': '[TARGET]',
            '⚡': '[FLASH]', '🔔': '[BELL]', '🔧': '[TOOL]', '📋': '[CLIPBOARD]',
            '📝': '[WRITE]', '👤': '[PERSON]', '💬': '[CHAT]', '🛑': '[STOP]',
            '🟢': '[GREEN]', '🟡': '[YELLOW]', '🔴': '[RED]', '📞': '[CALL]',
            '📬': '[INBOX]', '📤': '[SEND]', '📥': '[RECEIVE]', '🔍': '[SEARCH]',
            '💾': '[SAVE]', '📅': '[DATE]', '⏳': '[WAIT]', '🎉': '[CELEBRATE]'
        }
    
    def safe_message(self, message):
        """Convert emojis to safe text for Windows"""
        if not isinstance(message, str):
            message = str(message)
        
        for emoji, replacement in self.emoji_map.items():
            message = message.replace(emoji, replacement)
        
        # Also remove any other non-ASCII characters
        message = ''.join(char if ord(char) < 128 else '?' for char in message)
        
        return message
    
    def info(self, message, *args):
        safe_msg = self.safe_message(message)
        self.logger.info(safe_msg, *args)
    
    def warning(self, message, *args):
        safe_msg = self.safe_message(message)
        self.logger.warning(safe_msg, *args)
    
    def error(self, message, *args):
        safe_msg = self.safe_message(message)
        self.logger.error(safe_msg, *args)
    
    def debug(self, message, *args):
        safe_msg = self.safe_message(message)
        self.logger.debug(safe_msg, *args)

# Initialize safe logger
safe_log = SafeLogger(__name__)

class WhatsAppRealTimeMonitor:
    """
    REAL-TIME WhatsApp Monitor (FIXED VERSION)
    Fixed: Replaced updated_at with created_at
    """
    
    def __init__(self):
        self.check_interval = 5  # Check every 5 seconds
        self.update_history = []  # Keep track of recent updates
        self.max_history = 50
        
        safe_log.info("=" * 70)
        safe_log.info("[PHONE] WHATSAPP REAL-TIME STATUS MONITOR STARTED")
        safe_log.info("=" * 70)
        safe_log.info("Mode: MONITOR ONLY - No API calls to WhatsApp")
        safe_log.info("Checks: Every 5 seconds for new status updates")
        safe_log.info("Source: Webhook data only (no external API calls)")
        safe_log.info("=" * 70)
    
    def get_recent_status_updates(self, minutes=2):
        """
        Get recent status updates from webhook data
        """
        try:
            recent_time = timezone.now() - timedelta(minutes=minutes)
            
            # Get all status updates from recent time
            updates = WhatsAppLog.objects.filter(
                Q(read_at__gte=recent_time) |
                Q(delivered_at__gte=recent_time) |
                Q(sent_at__gte=recent_time)
            ).order_by('-created_at')[:20]  # FIXED: changed -updated_at to -created_at
            
            return updates
            
        except Exception as e:
            safe_log.error(f"Error getting recent updates: {e}")
            return WhatsAppLog.objects.none()
    
    def check_new_read_status(self):
        """
        Check for new READ status updates
        """
        try:
            # Get READ messages from last 2 minutes
            recent_time = timezone.now() - timedelta(minutes=2)
            
            new_reads = WhatsAppLog.objects.filter(
                status='READ',
                read_at__gte=recent_time
            ).order_by('-read_at')[:10]
            
            if new_reads.exists():
                safe_log.info(f"[READ] NEW READ MESSAGES ({len(new_reads)}):")
                
                for msg in new_reads:
                    time_ago = (timezone.now() - msg.read_at).total_seconds()
                    
                    # Calculate read time
                    read_time = "unknown"
                    if msg.sent_at:
                        sent_to_read = (msg.read_at - msg.sent_at).total_seconds()
                        if sent_to_read < 60:
                            read_time = f"{sent_to_read:.1f}s"
                        else:
                            read_time = f"{sent_to_read/60:.1f}m"
                    
                    safe_log.info(f"   {msg.mobile_number}: Read {time_ago:.0f}s ago (in {read_time})")
                    safe_log.info(f"      Template ID: {msg.template_message_id[:30]}...")
                    
                    # Store in history
                    self.add_to_history({
                        'type': 'READ',
                        'mobile': msg.mobile_number,
                        'time': msg.read_at,
                        'template_id': msg.template_message_id[:20] if msg.template_message_id else 'N/A'
                    })
            
            return len(new_reads)
            
        except Exception as e:
            safe_log.error(f"Error checking new READ status: {e}")
            return 0
    
    def check_new_delivered_status(self):
        """
        Check for new DELIVERED status updates
        """
        try:
            # Get DELIVERED messages from last 2 minutes
            recent_time = timezone.now() - timedelta(minutes=2)
            
            new_delivered = WhatsAppLog.objects.filter(
                status='DELIVERED',
                delivered_at__gte=recent_time
            ).order_by('-delivered_at')[:10]
            
            if new_delivered.exists():
                safe_log.info(f"[MAIL] NEW DELIVERED MESSAGES ({len(new_delivered)}):")
                
                for msg in new_delivered:
                    time_ago = (timezone.now() - msg.delivered_at).total_seconds()
                    
                    # Calculate delivery time
                    delivery_time = "unknown"
                    if msg.sent_at:
                        sent_to_delivery = (msg.delivered_at - msg.sent_at).total_seconds()
                        if sent_to_delivery < 60:
                            delivery_time = f"{sent_to_delivery:.1f}s"
                        else:
                            delivery_time = f"{sent_to_delivery/60:.1f}m"
                    
                    safe_log.info(f"   {msg.mobile_number}: Delivered {time_ago:.0f}s ago (in {delivery_time})")
                    safe_log.info(f"      Template ID: {msg.template_message_id[:30]}...")
                    
                    # Store in history
                    self.add_to_history({
                        'type': 'DELIVERED',
                        'mobile': msg.mobile_number,
                        'time': msg.delivered_at,
                        'template_id': msg.template_message_id[:20] if msg.template_message_id else 'N/A'
                    })
            
            return len(new_delivered)
            
        except Exception as e:
            safe_log.error(f"Error checking new DELIVERED status: {e}")
            return 0
    
    def check_pending_to_sent(self):
        """
        Check for messages that changed from PENDING to SENT
        """
        try:
            # Get SENT messages from last 2 minutes
            recent_time = timezone.now() - timedelta(minutes=2)
            
            new_sent = WhatsAppLog.objects.filter(
                status='SENT',
                sent_at__gte=recent_time
            ).order_by('-sent_at')[:10]
            
            if new_sent.exists():
                safe_log.info(f"[SEND] NEW SENT MESSAGES ({len(new_sent)}):")
                
                for msg in new_sent:
                    time_ago = (timezone.now() - msg.sent_at).total_seconds()
                    
                    safe_log.info(f"   {msg.mobile_number}: Sent {time_ago:.0f}s ago")
                    safe_log.info(f"      Template ID: {msg.template_message_id[:30]}...")
                    
                    # Store in history
                    self.add_to_history({
                        'type': 'SENT',
                        'mobile': msg.mobile_number,
                        'time': msg.sent_at,
                        'template_id': msg.template_message_id[:20] if msg.template_message_id else 'N/A'
                    })
            
            return len(new_sent)
            
        except Exception as e:
            safe_log.error(f"Error checking new SENT status: {e}")
            return 0
    
    def check_stuck_messages(self):
        """
        Check for messages that are stuck or need attention
        """
        try:
            # Messages sent more than 30 minutes ago but not delivered
            thirty_minutes_ago = timezone.now() - timedelta(minutes=30)
            
            stuck_messages = WhatsAppLog.objects.filter(
                status='SENT',
                sent_at__lt=thirty_minutes_ago,
                delivered_at__isnull=True,
                read_at__isnull=True
            ).order_by('sent_at')[:10]
            
            if stuck_messages.exists():
                safe_log.warning(f"[WARN] STUCK MESSAGES ({len(stuck_messages)}):")
                safe_log.warning("   These were sent but not delivered for 30+ minutes")
                
                for msg in stuck_messages:
                    stuck_time = (timezone.now() - msg.sent_at).total_seconds() / 60
                    safe_log.warning(f"   {msg.mobile_number}: Stuck for {stuck_time:.1f} minutes")
                    safe_log.warning(f"      Sent at: {msg.sent_at.strftime('%H:%M:%S') if msg.sent_at else 'N/A'}")
            
            return len(stuck_messages)
            
        except Exception as e:
            safe_log.error(f"Error checking stuck messages: {e}")
            return 0
    
    def check_webhook_gaps(self):
        """
        Check for gaps in webhook processing
        """
        try:
            # Find messages that should have been processed by webhook
            # but still show as SENT when they should be DELIVERED/READ
            five_minutes_ago = timezone.now() - timedelta(minutes=5)
            
            potential_gaps = WhatsAppLog.objects.filter(
                status='SENT',
                sent_at__lt=five_minutes_ago,
                template_message_id__isnull=False
            ).exclude(template_message_id='').count()
            
            if potential_gaps > 0:
                safe_log.info(f"[CLOCK] Potential webhook gaps: {potential_gaps} messages")
                safe_log.info("   Some messages may not have received status updates")
            
            return potential_gaps
            
        except Exception as e:
            safe_log.error(f"Error checking webhook gaps: {e}")
            return 0
    
    def add_to_history(self, update):
        """Add update to history for tracking"""
        self.update_history.append({
            'timestamp': timezone.now(),
            'update': update
        })
        
        # Keep only recent history
        if len(self.update_history) > self.max_history:
            self.update_history = self.update_history[-self.max_history:]
    
    def show_recent_activity(self):
        """Show recent activity summary"""
        try:
            # Get activity from last 5 minutes
            recent_time = timezone.now() - timedelta(minutes=5)
            
            # Count recent activity
            recent_read = WhatsAppLog.objects.filter(
                status='READ',
                read_at__gte=recent_time
            ).count()
            
            recent_delivered = WhatsAppLog.objects.filter(
                status='DELIVERED',
                delivered_at__gte=recent_time
            ).count()
            
            recent_sent = WhatsAppLog.objects.filter(
                status='SENT',
                sent_at__gte=recent_time
            ).count()
            
            recent_failed = WhatsAppLog.objects.filter(
                status__in=['FAILED', 'NOT_REGISTERED'],
                created_at__gte=recent_time
            ).count()
            
            # Show summary
            if recent_read > 0 or recent_delivered > 0 or recent_sent > 0 or recent_failed > 0:
                safe_log.info(f"[CHART] RECENT ACTIVITY (Last 5 minutes):")
                safe_log.info(f"   [SEND] Sent: {recent_sent}")
                safe_log.info(f"   [MAIL] Delivered: {recent_delivered}")
                safe_log.info(f"   [READ] Read: {recent_read}")
                safe_log.info(f"   [ERROR] Failed: {recent_failed}")
            
        except Exception as e:
            safe_log.error(f"Error showing recent activity: {e}")
    
    def show_dashboard(self):
        """Show real-time dashboard"""
        try:
            # Calculate current time
            current_time = timezone.now()
            
            safe_log.info("=" * 70)
            safe_log.info(f"[CHART] WHATSAPP REAL-TIME DASHBOARD - {current_time.strftime('%H:%M:%S')}")
            safe_log.info("=" * 70)
            
            # Total counts
            total_logs = WhatsAppLog.objects.count()
            sent_logs = WhatsAppLog.objects.filter(status='SENT').count()
            delivered_logs = WhatsAppLog.objects.filter(status='DELIVERED').count()
            read_logs = WhatsAppLog.objects.filter(status='READ').count()
            failed_logs = WhatsAppLog.objects.filter(status__in=['FAILED', 'NOT_REGISTERED']).count()
            
            safe_log.info("[CHART] TOTAL STATS:")
            safe_log.info(f"   Total messages: {total_logs}")
            safe_log.info(f"   Sent: {sent_logs}")
            safe_log.info(f"   Delivered: {delivered_logs} ({delivered_logs/total_logs*100:.1f}% of total)")
            safe_log.info(f"   Read: {read_logs} ({read_logs/delivered_logs*100:.1f}% of delivered)" if delivered_logs > 0 else "   Read: 0")
            safe_log.info(f"   Failed/Not Registered: {failed_logs}")
            
            # Show latest updates
            safe_log.info("-" * 70)
            safe_log.info("[CLOCK] LATEST STATUS UPDATES:")
            
            latest_updates = WhatsAppLog.objects.filter(
                Q(read_at__gte=current_time - timedelta(minutes=10)) |
                Q(delivered_at__gte=current_time - timedelta(minutes=10)) |
                Q(sent_at__gte=current_time - timedelta(minutes=10))
            ).order_by('-created_at')[:5]  # FIXED: changed -updated_at to -created_at
            
            if latest_updates.exists():
                for update in latest_updates:
                    update_type = ""
                    update_time = None
                    
                    if update.read_at:
                        update_type = "READ"
                        update_time = update.read_at
                    elif update.delivered_at:
                        update_type = "DELIVERED"
                        update_time = update.delivered_at
                    elif update.sent_at:
                        update_type = "SENT"
                        update_time = update.sent_at
                    
                    if update_time:
                        time_ago = (current_time - update_time).total_seconds()
                        if time_ago < 60:
                            time_display = f"{time_ago:.0f}s ago"
                        else:
                            time_display = f"{time_ago/60:.1f}m ago"
                        
                        safe_log.info(f"   {update.mobile_number}: {update_type} {time_display}")
            else:
                safe_log.info("   No recent updates")
            
            # Show upcoming/due deliveries
            safe_log.info("-" * 70)
            safe_log.info("[MAIL] EXPECTING DELIVERY UPDATES:")
            
            # Messages sent in last 30 minutes but not delivered
            thirty_minutes_ago = current_time - timedelta(minutes=30)
            expecting_delivery = WhatsAppLog.objects.filter(
                status='SENT',
                sent_at__gte=thirty_minutes_ago,
                delivered_at__isnull=True
            ).order_by('sent_at')[:5]
            
            if expecting_delivery.exists():
                for msg in expecting_delivery:
                    sent_ago = (current_time - msg.sent_at).total_seconds() / 60
                    safe_log.info(f"   {msg.mobile_number}: Sent {sent_ago:.1f} minutes ago")
            else:
                safe_log.info("   No pending deliveries")
            
            safe_log.info("=" * 70)
            
        except Exception as e:
            safe_log.error(f"Error showing dashboard: {e}")
    
    def monitor_specific_number(self, mobile_number):
        """
        Monitor a specific mobile number in real-time
        """
        try:
            # Clean the mobile number
            mobile_clean = ''.join(filter(str.isdigit, str(mobile_number)))
            
            # Get messages for this number
            messages = WhatsAppLog.objects.filter(
                mobile_number__contains=mobile_clean[-10:]  # Last 10 digits
            ).order_by('-created_at')[:5]
            
            safe_log.info(f"[TARGET] MONITORING: {mobile_number}")
            safe_log.info("-" * 70)
            
            if messages.exists():
                for msg in messages:
                    status_icon = {
                        'SENT': '[SEND]',
                        'DELIVERED': '[MAIL]', 
                        'READ': '[READ]',
                        'FAILED': '[ERROR]',
                        'NOT_REGISTERED': '[NO-WHATSAPP]'
                    }.get(msg.status, '[?]')
                    
                    safe_log.info(f"   {status_icon} {msg.status}")
                    safe_log.info(f"      Time: {msg.created_at.strftime('%H:%M:%S')}")
                    
                    if msg.sent_at:
                        sent_ago = (timezone.now() - msg.sent_at).total_seconds()
                        safe_log.info(f"      Sent: {sent_ago:.0f} seconds ago")
                    
                    if msg.delivered_at:
                        safe_log.info(f"      Delivered at: {msg.delivered_at.strftime('%H:%M:%S')}")
                    
                    if msg.read_at:
                        safe_log.info(f"      Read at: {msg.read_at.strftime('%H:%M:%S')}")
                    
                    if msg.template_message_id:
                        safe_log.info(f"      Template ID: {msg.template_message_id[:30]}...")
                    
                    safe_log.info("")
            else:
                safe_log.info("   No messages found for this number")
            
            safe_log.info("-" * 70)
            
        except Exception as e:
            safe_log.error(f"Error monitoring specific number: {e}")
    
    def check_whatsapp_registration_status(self):
        """
        Check MPP WhatsApp registration status based on webhook data
        """
        try:
            # Get MPPs with mobile numbers
            mpps_with_numbers = MPPWithCode.objects.filter(
                sahayak_mobile_number__isnull=False
            ).exclude(sahayak_mobile_number='')
            
            total_mpps = mpps_with_numbers.count()
            
            if total_mpps == 0:
                return
            
            # Count by WhatsApp status from webhook data
            confirmed_whatsapp = 0
            confirmed_not_whatsapp = 0
            
            for mpp in mpps_with_numbers:
                mobile = mpp.sahayak_mobile_number
                if not mobile:
                    continue
                
                # Check if we have successful deliveries
                deliveries = WhatsAppLog.objects.filter(
                    mobile_number__contains=mobile[-10:],  # Last 10 digits
                    status__in=['DELIVERED', 'READ']
                ).exists()
                
                # Check if we have NOT_REGISTERED status
                not_registered = WhatsAppLog.objects.filter(
                    mobile_number__contains=mobile[-10:],
                    status='NOT_REGISTERED'
                ).exists()
                
                if deliveries:
                    confirmed_whatsapp += 1
                elif not_registered:
                    confirmed_not_whatsapp += 1
            
            # Calculate percentages
            whatsapp_percent = (confirmed_whatsapp / total_mpps) * 100 if total_mpps > 0 else 0
            not_whatsapp_percent = (confirmed_not_whatsapp / total_mpps) * 100 if total_mpps > 0 else 0
            
            safe_log.info(f"[PHONE] WHATSAPP REGISTRATION (From Webhook):")
            safe_log.info(f"   Total MPPs with numbers: {total_mpps}")
            safe_log.info(f"   [OK] Confirmed WhatsApp: {confirmed_whatsapp} ({whatsapp_percent:.1f}%)")
            safe_log.info(f"   [ERROR] Not on WhatsApp: {confirmed_not_whatsapp} ({not_whatsapp_percent:.1f}%)")
            
        except Exception as e:
            safe_log.error(f"Error checking registration status: {e}")
    
    def check_message_queue_status(self):
        """
        Check MessageQueue status
        """
        try:
            # WhatsApp queue
            whatsapp_pending = MessageQueue.objects.filter(
                message_type='WHATSAPP',
                status='PENDING'
            ).count()
            
            whatsapp_processing = MessageQueue.objects.filter(
                message_type='WHATSAPP',
                status='PROCESSING'
            ).count()
            
            whatsapp_sent = MessageQueue.objects.filter(
                message_type='WHATSAPP',
                status='SENT'
            ).count()
            
            whatsapp_failed = MessageQueue.objects.filter(
                message_type='WHATSAPP',
                status='FAILED'
            ).count()
            
            # SMS queue
            sms_pending = SMSQueue.objects.filter(
                status='PENDING'
            ).count()
            
            sms_sent = SMSQueue.objects.filter(
                status='SENT'
            ).count()
            
            sms_failed = SMSQueue.objects.filter(
                status='FAILED'
            ).count()
            
            safe_log.info(f"[INBOX] MESSAGE QUEUE STATUS:")
            safe_log.info(f"   WhatsApp: Pending={whatsapp_pending}, Processing={whatsapp_processing}")
            safe_log.info(f"   WhatsApp: Sent={whatsapp_sent}, Failed={whatsapp_failed}")
            safe_log.info(f"   SMS: Pending={sms_pending}, Sent={sms_sent}, Failed={sms_failed}")
            
        except Exception as e:
            safe_log.error(f"Error checking message queue: {e}")
            
# Checking the read analytics of the value             
    def check_read_analytics(self):
        """
        Analyze read patterns and statistics
        """
        try:
            # Get today's read messages
            today = timezone.now().date()
            today_reads = WhatsAppLog.objects.filter(
                status='READ',
                read_at__date=today
            )
            
            total_today = today_reads.count()
            
            if total_today > 0:
                # Calculate average time to read
                read_times = []
                for msg in today_reads:
                    if msg.sent_at and msg.read_at:
                        time_to_read = (msg.read_at - msg.sent_at).total_seconds()
                        read_times.append(time_to_read)
                
                avg_read_time = sum(read_times) / len(read_times) if read_times else 0
                safe_log.info(f"[ANALYTICS] Today's Read Statistics:")
                safe_log.info(f"   Total reads today: {total_today}")
                safe_log.info(f"   Average time to read: {avg_read_time:.1f}s")
                
                # Breakdown by hour
                for hour in range(24):
                    hour_reads = today_reads.filter(
                        read_at__hour=hour
                    ).count()
                    
                    if hour_reads > 0:
                        safe_log.info(f"   Hour {hour:02d}:00 - {hour_reads} reads")
            
            return total_today
            
        except Exception as e:
            safe_log.error(f"Error in check_read_analytics: {e}")
            return 0
    
    def find_unread_delivered_messages(self):
        """
        Find messages that were delivered but not read (potential follow-ups)
        """
        try:
            # Messages delivered more than 1 hour ago but not read
            one_hour_ago = timezone.now() - timedelta(hours=1)
            
            unread_delivered = WhatsAppLog.objects.filter(
                status='DELIVERED',
                delivered_at__lt=one_hour_ago,
                read_at__isnull=True,
                is_read=False
            ).order_by('delivered_at')[:10]
            
            if unread_delivered.exists():
                safe_log.info(f"[FOLLOWUP] {len(unread_delivered)} delivered but unread messages:")
                
                for msg in unread_delivered:
                    delivered_ago = (timezone.now() - msg.delivered_at).total_seconds() / 3600
                    safe_log.info(f"   {msg.mobile_number}: Delivered {delivered_ago:.1f} hours ago")
                    
                    # Could trigger follow-up logic here
                    # self.suggest_follow_up(msg)
            
            return len(unread_delivered)
            
        except Exception as e:
            safe_log.error(f"Error finding unread delivered: {e}")
            return 0
    
    def verify_webhook_connectivity(self):
        """
        Verify webhook is receiving status updates
        """
        try:
            # Check for recent webhook activity
            five_minutes_ago = timezone.now() - timedelta(minutes=5)
            
            recent_webhooks = WhatsAppLog.objects.filter(
                Q(read_at__gte=five_minutes_ago) |
                Q(delivered_at__gte=five_minutes_ago) |
                Q(sent_at__gte=five_minutes_ago)
            ).count()
            
            if recent_webhooks == 0:
                # Check if we have recent sent messages that should have updates
                recent_sent = WhatsAppLog.objects.filter(
                    status='SENT',
                    sent_at__gte=five_minutes_ago,
                    delivered_at__isnull=True
                ).count()
                
                if recent_sent > 0:
                    safe_log.warning(f"[ALERT] {recent_sent} recent sent messages without status updates")
                    safe_log.warning("   Webhook might not be receiving updates")
            
            return recent_webhooks
            
        except Exception as e:
            safe_log.error(f"Error verifying webhook: {e}")
            return 0
    
    # Update the run method to include new checks:
    def run(self):
        """
        Main monitoring loop with enhanced read tracking
        """
        safe_log.info("[ROCKET] Starting Enhanced WhatsApp Monitor with Read Tracking")
        
        cycle_count = 0
        dashboard_count = 0
        
        try:
            while True:
                cycle_count += 1
                dashboard_count += 1
                
                # Core status checks
                new_read = self.check_new_read_status()
                new_delivered = self.check_new_delivered_status()
                new_sent = self.check_pending_to_sent()
                
                # Enhanced checks (every 5 cycles = 25 seconds)
                if cycle_count % 5 == 0:
                    self.find_unread_delivered_messages()
                
                # Analytics (every 10 cycles = 50 seconds)
                if cycle_count % 10 == 0:
                    self.check_read_analytics()
                
                # Webhook health (every 30 cycles = 2.5 minutes)
                if cycle_count % 30 == 0:
                    self.verify_webhook_connectivity()
                    cycle_count = 0
                
                # Dashboard (every 12 cycles = 1 minute)
                if dashboard_count >= 12:
                    self.show_dashboard()
                    dashboard_count = 0
                
                # Monitor specific number if provided
                if hasattr(self, 'monitor_number'):
                    self.monitor_specific_number(self.monitor_number)
                
                safe_log.debug(f"Monitor sleeping for {self.check_interval} seconds...")
                time.sleep(self.check_interval)
                
        except KeyboardInterrupt:
            safe_log.info("\n" + "=" * 70)
            safe_log.info("[STOP] Enhanced Monitor stopped")
            safe_log.info("=" * 70)
        except Exception as e:
            safe_log.error(f"Service error: {e}")
            time.sleep(10)
            self.run()

    
    def run(self):
        """
        Main monitoring loop
        """
        safe_log.info("[ROCKET] Starting WhatsApp Real-Time Monitor")
        safe_log.info("   Monitoring webhook data updates every 5 seconds")
        safe_log.info("   Press Ctrl+C to stop")
        
        cycle_count = 0
        dashboard_count = 0
        
        try:
            while True:
                cycle_count += 1
                dashboard_count += 1
                
                # Check for new status updates
                new_read = self.check_new_read_status()
                new_delivered = self.check_new_delivered_status()
                new_sent = self.check_pending_to_sent()
                
                # Show activity summary
                if new_read > 0 or new_delivered > 0 or new_sent > 0:
                    self.show_recent_activity()
                
                # Show dashboard every 10 cycles (50 seconds)
                if dashboard_count >= 10:
                    self.show_dashboard()
                    dashboard_count = 0
                
                # Check stuck messages every 12 cycles (1 minute)
                if cycle_count % 12 == 0:
                    self.check_stuck_messages()
                
                # Check webhook gaps every 24 cycles (2 minutes)
                if cycle_count % 24 == 0:
                    self.check_webhook_gaps()
                    self.check_whatsapp_registration_status()
                    self.check_message_queue_status()
                    cycle_count = 0
                
                # Monitor specific number if provided
                if hasattr(self, 'monitor_number'):
                    self.monitor_specific_number(self.monitor_number)
                
                safe_log.debug(f"Monitor sleeping for {self.check_interval} seconds...")
                time.sleep(self.check_interval)
                
        except KeyboardInterrupt:
            safe_log.info("\n" + "=" * 70)
            safe_log.info("[STOP] Real-Time Monitor stopped by user")
            safe_log.info("=" * 70)
        except Exception as e:
            safe_log.error(f"Service error: {e}")
            safe_log.info("Restarting monitor in 10 seconds...")
            time.sleep(10)
            self.run()

# ============================================================================
# COMMAND LINE INTERFACE
# ============================================================================

def main():
    """Main entry point with command line options"""
    import argparse
    
    parser = argparse.ArgumentParser(description='WhatsApp Real-Time Status Monitor')
    parser.add_argument('--number', '-n', help='Monitor specific mobile number')
    parser.add_argument('--interval', '-i', type=int, default=5, help='Check interval in seconds')
    parser.add_argument('--dashboard', '-d', action='store_true', help='Show dashboard only once')
    
    args = parser.parse_args()
    
    # Initialize monitor
    monitor = WhatsAppRealTimeMonitor()
    
    # Customize if number provided
    if args.number:
        monitor.monitor_number = args.number
        safe_log.info(f"[TARGET] Will monitor number: {args.number}")
    
    if args.interval:
        monitor.check_interval = args.interval
        safe_log.info(f"[CLOCK] Check interval: {args.interval} seconds")
    
    # If dashboard only mode
    if args.dashboard:
        monitor.show_dashboard()
        return
    
    # Run the monitor
    monitor.run()

if __name__ == "__main__":
    main()