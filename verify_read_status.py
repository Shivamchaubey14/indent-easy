"""
Read Status Verification Script
Manually verify and fix read status issues
"""
import os
import sys
import django
from datetime import datetime, timedelta

# Setup Django
project_root = r"C:\Users\Shwetdhara\Desktop\shwetDhara_Project_v3\shwetDhara_project"
sys.path.insert(0, project_root)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'shwetDhara_project.settings')
django.setup()

from django.utils import timezone
from main_app.models import WhatsAppLog
import logging

logger = logging.getLogger(__name__)

class ReadStatusVerifier:
    def __init__(self):
        self.fixed_count = 0
        
    def find_potential_reads(self, hours_back=24):
        """
        Find messages that might be read but not marked as such
        """
        cutoff = timezone.now() - timedelta(hours=hours_back)
        
        # Messages delivered a while ago but not marked read
        potential_reads = WhatsAppLog.objects.filter(
            status='DELIVERED',
            delivered_at__lt=cutoff,
            read_at__isnull=True,
            delivered_at__isnull=False
        ).order_by('-delivered_at')
        
        logger.info(f"Found {potential_reads.count()} potential unmarked reads")
        
        for msg in potential_reads[:20]:  # Check first 20
            delivered_time = msg.delivered_at
            hours_since = (timezone.now() - delivered_time).total_seconds() / 3600
            
            logger.info(f"  - {msg.mobile_number}: Delivered {hours_since:.1f}h ago")
            
            # You could manually verify these with users
            # or implement heuristic logic
        
        return potential_reads.count()
    
    def fix_inconsistent_reads(self):
        """
        Fix inconsistent read statuses
        """
        # Find messages with read_at but status not READ
        inconsistent = WhatsAppLog.objects.filter(
            read_at__isnull=False,
            status__in=['SENT', 'DELIVERED', 'PENDING']
        )
        
        logger.info(f"Found {inconsistent.count()} inconsistent read statuses")
        
        for msg in inconsistent:
            logger.info(f"Fixing: {msg.id} - has read_at {msg.read_at} but status {msg.status}")
            msg.status = 'READ'
            msg.save()
            self.fixed_count += 1
        
        return self.fixed_count
    
    def generate_read_report(self, days=7):
        """
        Generate read statistics report
        """
        cutoff = timezone.now() - timedelta(days=days)
        
        stats = {
            'total_messages': WhatsAppLog.objects.filter(created_at__gte=cutoff).count(),
            'sent_messages': WhatsAppLog.objects.filter(status='SENT', created_at__gte=cutoff).count(),
            'delivered_messages': WhatsAppLog.objects.filter(status='DELIVERED', created_at__gte=cutoff).count(),
            'read_messages': WhatsAppLog.objects.filter(status='READ', created_at__gte=cutoff).count(),
            'read_rate': 0,
            'avg_time_to_read': 0,
        }
        
        if stats['delivered_messages'] > 0:
            stats['read_rate'] = (stats['read_messages'] / stats['delivered_messages']) * 100
        
        # Calculate average time to read
        read_messages = WhatsAppLog.objects.filter(
            status='READ',
            read_at__isnull=False,
            sent_at__isnull=False,
            created_at__gte=cutoff
        )
        
        total_seconds = 0
        count = 0
        
        for msg in read_messages:
            if msg.sent_at and msg.read_at:
                total_seconds += (msg.read_at - msg.sent_at).total_seconds()
                count += 1
        
        if count > 0:
            stats['avg_time_to_read'] = total_seconds / count
        
        logger.info("=" * 60)
        logger.info(f"READ STATUS REPORT (Last {days} days)")
        logger.info("=" * 60)
        logger.info(f"Total Messages: {stats['total_messages']}")
        logger.info(f"Sent: {stats['sent_messages']}")
        logger.info(f"Delivered: {stats['delivered_messages']}")
        logger.info(f"Read: {stats['read_messages']}")
        logger.info(f"Read Rate: {stats['read_rate']:.1f}%")
        logger.info(f"Avg Time to Read: {stats['avg_time_to_read']:.1f} seconds")
        logger.info("=" * 60)
        
        return stats

def main():
    """Command-line interface"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Verify and fix read statuses')
    parser.add_argument('--fix', action='store_true', help='Fix inconsistent read statuses')
    parser.add_argument('--report', action='store_true', help='Generate read statistics report')
    parser.add_argument('--check', action='store_true', help='Check for potential unmarked reads')
    parser.add_argument('--days', type=int, default=7, help='Days for report')
    
    args = parser.parse_args()
    
    verifier = ReadStatusVerifier()
    
    if args.fix:
        fixed = verifier.fix_inconsistent_reads()
        print(f"✅ Fixed {fixed} inconsistent read statuses")
    
    if args.report:
        verifier.generate_read_report(args.days)
    
    if args.check:
        count = verifier.find_potential_reads()
        print(f"🔍 Found {count} potential unmarked reads")

if __name__ == "__main__":
    main()
    