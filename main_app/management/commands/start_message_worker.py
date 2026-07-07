# main_app/management/commands/start_message_worker.py
from django.core.management.base import BaseCommand
from celery.bin.worker import worker

class Command(BaseCommand):
    help = 'Start dedicated message queue Celery worker'
    
    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🚀 Starting dedicated message queue worker...')
        )
        
        # Start worker with single concurrency for sequential processing
        worker_app = worker.worker(app='shwetDhara_project.celery:app')
        
        options = {
            'queues': ['message_queue'],
            'concurrency': 1,  # Single worker for sequential processing
            'hostname': 'message_worker@%h',
            'loglevel': 'INFO',
            'traceback': True,
        }
        
        worker_app.run(**options)