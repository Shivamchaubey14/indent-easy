# thread_manager.py
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import queue
import time
import logging

logger = logging.getLogger(__name__)

class SMSThreadManager:
    def __init__(self, max_workers=5):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.futures = {}
        self.results = queue.Queue()
        self._cleanup_thread = None
        self._start_cleanup_thread()
    
    def submit_sms(self, mobile_number, unique_code, mpp_name):
        """Submit SMS to thread pool for immediate processing"""
        # Simple SMS sending function (no external dependency)
        def send_sms_task():
            try:
                logger.info(f"[Thread Pool] Sending SMS to {mobile_number}")
                # Simulate SMS sending
                time.sleep(1)
                result = {
                    'success': True,
                    'mobile_number': mobile_number,
                    'unique_code': unique_code,
                    'message': f'SMS sent to {mobile_number}'
                }
                logger.info(f"[Thread Pool] SMS sent to {mobile_number}")
                return result
            except Exception as e:
                logger.error(f"[Thread Pool] SMS failed: {e}")
                return {
                    'success': False,
                    'mobile_number': mobile_number,
                    'error': str(e)
                }
        
        future = self.executor.submit(send_sms_task)
        
        task_id = f"{mobile_number}_{unique_code}_{time.time()}"
        self.futures[task_id] = future
        
        return task_id
    
    def _start_cleanup_thread(self):
        """Start background thread to clean up completed futures"""
        def cleanup_worker():
            while True:
                try:
                    # Check for completed futures every 30 seconds
                    time.sleep(30)
                    completed_ids = []
                    for task_id, future in self.futures.items():
                        if future.done():
                            completed_ids.append(task_id)
                    
                    for task_id in completed_ids:
                        del self.futures[task_id]
                        
                    # Keep only last 100 futures to prevent memory leaks
                    if len(self.futures) > 100:
                        oldest_ids = sorted(self.futures.keys())[:50]
                        for task_id in oldest_ids:
                            del self.futures[task_id]
                            
                except Exception as e:
                    logger.error(f"[THREAD MANAGER] Cleanup error: {e}")
        
        self._cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
        self._cleanup_thread.start()
    
    def shutdown(self):
        """Shutdown the thread pool"""
        self.executor.shutdown(wait=False)

# Global instance
sms_thread_manager = SMSThreadManager(max_workers=5)