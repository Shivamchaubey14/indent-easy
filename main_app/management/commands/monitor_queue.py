# main_app/management/commands/monitor_queue.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Q, Count
from main_app.models import MessageQueue

class Command(BaseCommand):
    help = 'Monitor message queue status'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--continuous',
            action='store_true',
            help='Monitor continuously',
        )
        parser.add_argument(
            '--interval',
            type=int,
            default=10,
            help='Interval in seconds',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed message information',
        )
    
    def handle(self, *args, **options):
        continuous = options['continuous']
        interval = options['interval']
        verbose = options['verbose']
        
        def display_stats():
            # Get basic statistics using aggregation
            stats = MessageQueue.objects.aggregate(
                pending=Count('id', filter=Q(status='PENDING')),
                retry=Count('id', filter=Q(status='RETRY')),
                processing=Count('id', filter=Q(status='PROCESSING')),
                sent=Count('id', filter=Q(sent_at__date=timezone.now().date())),
                failed=Count('id', filter=Q(status='FAILED')),
                total=Count('id')
            )
            
            # Display statistics
            self.stdout.write(
                self.style.SUCCESS(
                    f"\n📊 Message Queue Stats - {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"   {'─' * 40}\n"
                    f"   PENDING:    {stats['pending']:>6}\n"
                    f"   RETRY:      {stats['retry']:>6}\n"
                    f"   PROCESSING: {stats['processing']:>6}\n"
                    f"   SENT TODAY: {stats['sent']:>6}\n"
                    f"   FAILED:     {stats['failed']:>6}\n"
                    f"   {'─' * 40}\n"
                    f"   TOTAL:      {stats['total']:>6}"
                )
            )
            
            # Show verbose details if requested
            if verbose:
                self.show_detailed_info()
        
        def show_detailed_info():
            """Display detailed information about queued messages"""
            self.stdout.write("\n📋 Detailed Message Information:")
            self.stdout.write("   " + "─" * 60)
            
            # Show pending messages
            pending_messages = MessageQueue.objects.filter(
                status__in=['PENDING', 'RETRY']
            ).order_by('created_at')[:10]
            
            if pending_messages.exists():
                self.stdout.write("   ⏳ PENDING/RETRY Messages (oldest 10):")
                for msg in pending_messages:
                    age_minutes = (timezone.now() - msg.created_at).total_seconds() / 60
                    self.stdout.write(
                        f"     • {msg.message_type} to {msg.mobile_number} "
                        f"(created {age_minutes:.1f} min ago) "
                        f"- Retry: {msg.retry_count}/{msg.max_retries}"
                    )
            else:
                self.stdout.write("   ✅ No pending messages")
            
            # Show recent failures
            recent_failures = MessageQueue.objects.filter(
                status='FAILED',
                created_at__date=timezone.now().date()
            ).order_by('-created_at')[:5]
            
            if recent_failures.exists():
                self.stdout.write("\n   ❌ Recent FAILURES (today):")
                for msg in recent_failures:
                    error_preview = msg.last_error[:100] + "..." if msg.last_error and len(msg.last_error) > 100 else msg.last_error or "No error details"
                    self.stdout.write(
                        f"     • {msg.message_type} to {msg.mobile_number} "
                        f"({msg.unique_code}) - {error_preview}"
                    )
            
            # Show processing metrics
            self.stdout.write("\n   📈 Processing Metrics:")
            
            # Messages by type
            by_type = MessageQueue.objects.values('message_type').annotate(
                count=Count('id')
            ).order_by('message_type')
            
            for item in by_type:
                self.stdout.write(f"     {item['message_type']}: {item['count']}")
            
            # Success rate today
            today_success = MessageQueue.objects.filter(
                sent_at__date=timezone.now().date()
            ).count()
            
            today_total = MessageQueue.objects.filter(
                created_at__date=timezone.now().date()
            ).count()
            
            if today_total > 0:
                success_rate = (today_success / today_total) * 100
                self.stdout.write(f"\n     Today's Success Rate: {success_rate:.1f}%")
        
        if continuous:
            import time
            self.stdout.write(f"\n🚀 Starting continuous monitoring every {interval} seconds...")
            self.stdout.write("Press Ctrl+C to stop\n")
            
            try:
                while True:
                    display_stats()
                    time.sleep(interval)
            except KeyboardInterrupt:
                self.stdout.write(self.style.WARNING("\n\n⏹️  Monitoring stopped by user"))
        else:
            display_stats()
