# main_app/tasks.py - SIMPLE VERSION

from .tasks_sequential import (
    queue_advance_sale_messages,
    process_message_queue,
    recover_stale_messages,
    clean_old_messages,
    restart_message_processing,
    check_and_process_messages,
    send_indent_hod_email
)

# Export all tasks
__all__ = [
    'queue_advance_sale_messages',
    'process_message_queue',
    'recover_stale_messages',
    'clean_old_messages',
    'restart_message_processing',
    'check_and_process_messages',
    'send_indent_hod_email'
]