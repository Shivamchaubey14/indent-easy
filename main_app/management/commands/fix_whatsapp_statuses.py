# management/commands/fix_whatsapp_statuses.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Q
from main_app.models import WhatsAppLog

class Command(BaseCommand):
    help = 'Fix WhatsApp status inconsistencies'

    def handle(self, *args, **options):
        self.stdout.write("🔧 Fixing WhatsApp status inconsistencies...")
        
        # Find messages with impossible state transitions
        # NOT_REGISTERED messages that later show as DELIVERED or READ
        problematic_logs = WhatsAppLog.objects.filter(
            Q(status='NOT_REGISTERED') | Q(not_registered=True),
            Q(delivered_at__isnull=False) | Q(read_at__isnull=False)
        )
        
        count = problematic_logs.count()
        if count > 0:
            self.stdout.write(f"❌ Found {count} problematic logs with impossible states")
            
            for log in problematic_logs:
                self.stdout.write(f"   Fixing log {log.id}: {log.mobile_number}")
                # Reset impossible states
                if log.not_registered:
                    log.delivered_at = None
                    log.read_at = None
                    log.is_read = False
                    log.status = 'NOT_REGISTERED'
                    log.completed_at = log.completed_at or log.created_at
                    log.save()
                    self.stdout.write(f"   ✅ Fixed: Marked as NOT_REGISTERED")
        
        # Find FAILED messages that later show as DELIVERED or READ
        failed_but_delivered = WhatsAppLog.objects.filter(
            status='FAILED',
            delivered_at__isnull=False
        )
        
        failed_count = failed_but_delivered.count()
        if failed_count > 0:
            self.stdout.write(f"❌ Found {failed_count} FAILED logs with delivery timestamps")
            
            for log in failed_but_delivered:
                self.stdout.write(f"   Fixing log {log.id}: {log.mobile_number}")
                log.delivered_at = None
                log.save()
                self.stdout.write(f"   ✅ Fixed: Removed delivery timestamp")
        
        # Mark all NOT_REGISTERED/FAILED as terminal
        terminal_logs = WhatsAppLog.objects.filter(
            status__in=['FAILED', 'NOT_REGISTERED'],
            completed_at__isnull=True
        )
        
        terminal_count = terminal_logs.count()
        if terminal_count > 0:
            for log in terminal_logs:
                log.completed_at = log.updated_at or log.created_at
                log.save()
            self.stdout.write(f"✅ Marked {terminal_count} logs as terminal")
        
        self.stdout.write(self.style.SUCCESS("✅ Status fix completed!"))