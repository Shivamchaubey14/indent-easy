# main_app/celery_beat_schedule.py
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    # Process message queue every 10 seconds
    'process-message-queue': {
        'task': 'main_app.tasks_sequential.process_message_queue',
        'schedule': 10.0,  # seconds
        'options': {'queue': 'message_queue'}
    },
    
    # Recover stale messages every 2 minutes
    'recover-stale-messages': {
        'task': 'main_app.tasks_sequential.recover_stale_messages',
        'schedule': 120.0,  # 2 minutes
        'options': {'queue': 'message_queue'}
    },
    
    # Clean old messages daily at 3 AM
    'clean-old-messages': {
        'task': 'main_app.tasks_sequential.clean_old_messages',
        'schedule': crontab(hour=3, minute=0),
        'options': {'queue': 'message_queue'}
    },
}