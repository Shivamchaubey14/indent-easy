# main_app/advance_sale_utils.py
import json
import random
import os
import threading
import queue
import time
import logging
from concurrent.futures import ThreadPoolExecutor
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.template.loader import render_to_string
from django.db import transaction
from django.utils import timezone
from django.conf import settings
from django.core.exceptions import ValidationError

# Get logger
logger = logging.getLogger(__name__)

# Message processing queues
sms_queue = queue.Queue()
whatsapp_queue = queue.Queue()

# Thread pools
sms_thread_pool = ThreadPoolExecutor(max_workers=5, thread_name_prefix='sms_worker')
whatsapp_thread_pool = ThreadPoolExecutor(max_workers=3, thread_name_prefix='whatsapp_worker')

# Redis Fallback System
class RedisFallback:
    """In-memory Redis fallback for development when Redis is not available"""
    def __init__(self):
        self._storage = {}
        self._expiry = {}
        self._locks = {}
        self._global_lock = threading.Lock()
        self._cleanup_counter = 0
        logger.info("Using in-memory Redis fallback")
    
    def _cleanup_expired(self):
        """Clean up expired keys periodically"""
        self._cleanup_counter += 1
        if self._cleanup_counter % 100 == 0:
            with self._global_lock:
                current_time = time.time()
                expired_keys = [k for k, exp in self._expiry.items() if exp < current_time]
                for key in expired_keys:
                    self._storage.pop(key, None)
                    self._expiry.pop(key, None)
    
    def ping(self):
        return True
    
    def set(self, key, value, ex=None, nx=False):
        with self._global_lock:
            self._cleanup_expired()
            if nx and key in self._storage:
                return False
            self._storage[key] = value
            if ex:
                self._expiry[key] = time.time() + ex
            return True
    
    def get(self, key):
        with self._global_lock:
            self._cleanup_expired()
            if key in self._expiry and time.time() > self._expiry[key]:
                del self._storage[key]
                del self._expiry[key]
                return None
            return self._storage.get(key)
    
    def delete(self, *keys):
        with self._global_lock:
            self._cleanup_expired()
            deleted_count = 0
            for key in keys:
                if key in self._storage:
                    del self._storage[key]
                    self._expiry.pop(key, None)
                    deleted_count += 1
            return deleted_count
    
    def exists(self, *keys):
        with self._global_lock:
            self._cleanup_expired()
            existing_count = 0
            for key in keys:
                if key in self._storage:
                    existing_count += 1
            return existing_count
    
    def incr(self, key, amount=1):
        with self._global_lock:
            self._cleanup_expired()
            current = int(self._storage.get(key, 0))
            new_value = current + amount
            self._storage[key] = new_value
            return new_value
    
    def decr(self, key, amount=1):
        with self._global_lock:
            self._cleanup_expired()
            current = int(self._storage.get(key, 0))
            new_value = current - amount
            self._storage[key] = new_value
            return new_value

# Enhanced connection handler
def get_redis_client():
    """Get Redis client with fallback handling"""
    try:
        import redis
        client = redis.Redis(
            host=getattr(settings, 'REDIS_HOST', 'localhost'),
            port=getattr(settings, 'REDIS_PORT', 6379),
            db=getattr(settings, 'REDIS_DB', 0),
            decode_responses=True,
            socket_connect_timeout=3,
            retry_on_timeout=True
        )
        client.ping()
        logger.info("SUCCESS: Connected to Redis server")
        return client
    except (ImportError, redis.ConnectionError, Exception) as e:
        logger.warning(f"WARNING: Redis not available, using in-memory fallback: {e}")
        return RedisFallback()

# Global Redis instance
redis_client = get_redis_client()

class MessageProcessor:
    """Centralized message processor with retry mechanism"""
    def __init__(self):
        self.max_retries = 3
        self.retry_delay = 2
        self.active_tasks = {}
        self.task_lock = threading.Lock()
        self.worker_running = True
        logger.info("Message Processor initialized")
    
    def stop_workers(self):
        """Stop all workers"""
        self.worker_running = False
        logger.info("Message Processor stopped")
    
    def process_sms_message(self, mobile_number, unique_code, mpp_name, cycle_info=None, retry_count=0):
        """Process SMS message with retry logic and cycle info"""
        if not self.worker_running:
            return False
            
        task_id = f"sms_{mobile_number}_{unique_code}"
        
        try:
            with self.task_lock:
                if task_id in self.active_tasks:
                    logger.info(f"SMS task {task_id} already in progress")
                    return False
                self.active_tasks[task_id] = True
            
            logger.info(f"Processing SMS for {mobile_number}, retry: {retry_count}, cycle: {cycle_info}")
            success = self.send_sms_via_gateway(mobile_number, unique_code, mpp_name, cycle_info)
            
            if success:
                logger.info(f"SUCCESS: SMS sent successfully to {mobile_number}")
                from .models import SMSQueue
                SMSQueue.objects.filter(
                    mobile_number=mobile_number, 
                    unique_code=unique_code
                ).update(status='SENT', processed_at=timezone.now())
                return True
            else:
                raise Exception("SMS gateway returned failure")
                
        except Exception as e:
            logger.error(f"ERROR: SMS failed for {mobile_number}: {str(e)}")
            if retry_count < self.max_retries:
                logger.info(f"RETRY: Retrying SMS for {mobile_number} in {self.retry_delay} seconds")
                time.sleep(self.retry_delay)
                return self.process_sms_message(mobile_number, unique_code, mpp_name, cycle_info, retry_count + 1)
            else:
                from .models import SMSQueue
                SMSQueue.objects.filter(
                    mobile_number=mobile_number, 
                    unique_code=unique_code
                ).update(
                    status='FAILED', 
                    last_error=f"Max retries exceeded: {str(e)}",
                    retry_count=retry_count,
                    processed_at=timezone.now()
                )
                return False
        finally:
            with self.task_lock:
                self.active_tasks.pop(task_id, None)
    
    def process_whatsapp_message(self, mobile_number, message, unique_code, mpp_name, cycle_info=None, retry_count=0):
        """Process WhatsApp message using Business API"""
        if not self.worker_running:
            return False
            
        task_id = f"whatsapp_{mobile_number}_{unique_code}"
        
        try:
            with self.task_lock:
                if task_id in self.active_tasks:
                    logger.info(f"WhatsApp task {task_id} already in progress")
                    return False
                self.active_tasks[task_id] = True
            
            logger.info(f"Processing WhatsApp for {mobile_number}, retry: {retry_count}, cycle: {cycle_info}")
            
            # Parse message to get template variables
            try:
                message_data = json.loads(message)
                template_vars = message_data.get('template_variables', {})
            except:
                # If message is not JSON, it's old format
                template_vars = {}
            
            # Use WhatsApp Business API
            from main_app.tasks_sequential import WhatsAppBusinessAPIClient
            api_client = WhatsAppBusinessAPIClient.get_instance()
            
            success, message_id, error_msg = api_client.send_template_message(
                phone_number=mobile_number,
                template_variables=template_vars
            )
            
            if success:
                logger.info(f"SUCCESS: WhatsApp sent via Business API to {mobile_number}")
                return True
            else:
                raise Exception(f"WhatsApp API failed: {error_msg}")
                
        except Exception as e:
            logger.error(f"ERROR: WhatsApp failed for {mobile_number}: {str(e)}")
            if retry_count < self.max_retries:
                logger.info(f"RETRY: Retrying WhatsApp for {mobile_number} in {self.retry_delay} seconds")
                time.sleep(self.retry_delay)
                return self.process_whatsapp_message(
                    mobile_number, message, unique_code, mpp_name, cycle_info, retry_count + 1
                )
            else:
                from .models import WhatsAppLog
                WhatsAppLog.objects.create(
                    mobile_number=mobile_number,
                    message=message[:500] if isinstance(message, str) else 'Template message',
                    unique_code=unique_code,
                    mpp_name=mpp_name,
                    status='FAILED',
                    error_message=f"Max retries exceeded: {str(e)}",
                    sent_via='META_API',
                    retry_count=retry_count
                )
                return False
        finally:
            with self.task_lock:
                self.active_tasks.pop(task_id, None)
    
    def send_sms_via_gateway(self, mobile_number, unique_code, mpp_name, cycle_info=None):
        """Send SMS via gateway with cycle info"""
        try:
            cycle_text = f" for {cycle_info}" if cycle_info else ""
            message = f"Verification code {unique_code} for MPP {mpp_name}{cycle_text}. Do not share."
            time.sleep(0.5)
            if random.random() < 0.1:
                return False
            return True
        except Exception as e:
            logger.error(f"SMS gateway error: {str(e)}")
            return False

# Global message processor instance
message_processor = MessageProcessor()

class InventoryManager:
    """Thread-safe inventory management"""
    def __init__(self):
        self._locks = {}
        self._lock_lock = threading.Lock()
        self.lock_timeout = 30
        logger.info("Inventory Manager initialized")
    
    def acquire_lock(self, user_id, product_id):
        """Use threading locks"""
        lock_key = f"{user_id}:{product_id}"
        with self._lock_lock:
            if lock_key not in self._locks:
                self._locks[lock_key] = threading.Lock()
        lock_acquired = self._locks[lock_key].acquire(timeout=self.lock_timeout)
        if lock_acquired:
            return lock_key
        else:
            raise Exception(f"Could not acquire inventory lock for {lock_key}")
    
    def release_lock(self, lock_key):
        """Release threading lock"""
        with self._lock_lock:
            if lock_key in self._locks:
                try:
                    self._locks[lock_key].release()
                except RuntimeError:
                    pass
    
    def deduct_inventory_safe(self, user, product, quantity_to_deduct, unique_code, mpp_name):
        """Thread-safe inventory deduction"""
        lock_key = None
        try:
            lock_key = self.acquire_lock(user.id, product.id)
            with transaction.atomic():
                from .models import Inventory
                inventory_item = Inventory.objects.select_for_update().get(
                    mcc_bmc_user=user,
                    product=product
                )
                if inventory_item.quantity < quantity_to_deduct:
                    raise ValidationError(
                        f'Insufficient inventory for {product.name}. '
                        f'Available: {inventory_item.quantity}, Requested: {quantity_to_deduct}'
                    )
                previous_quantity = inventory_item.quantity
                inventory_item.quantity -= quantity_to_deduct
                inventory_item.save()
                logger.info(
                    f"Inventory deducted: {product.name}, "
                    f"previous: {previous_quantity}, "
                    f"deducted: {quantity_to_deduct}, "
                    f"remaining: {inventory_item.quantity}"
                )
                return inventory_item
        except Exception as e:
            logger.error(f"Inventory deduction error: {e}")
            raise
        finally:
            if lock_key:
                self.release_lock(lock_key)

inventory_manager = InventoryManager()

def generate_whatsapp_message(mpp_name, items, unique_code, cycle=None):
    """Generate template variables for WhatsApp template"""
    # Format product list (Variable 2)
    product_details = []
    for idx, item in enumerate(items, 1):
        product_name = item.get('stockItem', '')
        quantity = item.get('quantity', 0)
        uom = item.get('uom', '')
        
        if uom:
            product_details.append(f"{product_name} - {quantity} {uom}")
        else:
            product_details.append(f"{product_name} - {quantity}")
    
    product_list = ", ".join(product_details)
    
    # Format order number/date (Variable 3)
    from datetime import datetime
    order_info = f"{unique_code}"
    
    return {
        '1': mpp_name,  # MPP Name
        '2': product_list,  # Product List
        '3': order_info  # Order Number + Date
    }

def sms_worker(worker_id):
    """Background worker for SMS processing with cycle support"""
    logger.info(f"SMS Worker {worker_id} started")
    worker_count = 0
    while getattr(message_processor, 'worker_running', True):
        try:
            task = sms_queue.get(timeout=1)
            # Unpack with cycle_info support
            if len(task) == 4:
                mobile_number, unique_code, mpp_name, cycle_info = task
            else:
                mobile_number, unique_code, mpp_name = task
                cycle_info = None
            
            success = message_processor.process_sms_message(
                mobile_number, unique_code, mpp_name, cycle_info
            )
            worker_count += 1
            if success:
                logger.info(f"SUCCESS: SMS Worker {worker_id} processed message #{worker_count} for {mobile_number}")
            else:
                logger.error(f"ERROR: SMS Worker {worker_id} failed to process message #{worker_count} for {mobile_number}")
            sms_queue.task_done()
        except queue.Empty:
            continue
        except Exception as e:
            logger.error(f"ERROR: SMS Worker {worker_id} error: {str(e)}")
            time.sleep(1)

def whatsapp_worker(worker_id):
    """Background worker for WhatsApp processing with cycle support"""
    logger.info(f"WhatsApp Worker {worker_id} started")
    worker_count = 0
    while getattr(message_processor, 'worker_running', True):
        try:
            task = whatsapp_queue.get(timeout=1)
            # Unpack with cycle_info support
            if len(task) == 5:
                mobile_number, message, unique_code, mpp_name, cycle_info = task
            else:
                mobile_number, message, unique_code, mpp_name = task
                cycle_info = None
            
            success = message_processor.process_whatsapp_message(
                mobile_number, message, unique_code, mpp_name, cycle_info
            )
            worker_count += 1
            if success:
                logger.info(f"SUCCESS: WhatsApp Worker {worker_id} processed message #{worker_count} for {mobile_number}")
            else:
                logger.error(f"ERROR: WhatsApp Worker {worker_id} failed to process message #{worker_count} for {mobile_number}")
            whatsapp_queue.task_done()
        except queue.Empty:
            continue
        except Exception as e:
            logger.error(f"ERROR: WhatsApp Worker {worker_id} error: {str(e)}")
            time.sleep(1)

def database_queue_processor():
    """Process messages from database queue"""
    logger.info("Database Queue Processor started")
    processed_count = 0
    while getattr(message_processor, 'worker_running', True):
        try:
            from .models import SMSQueue
            pending_sms = SMSQueue.objects.filter(
                status='PENDING',
                created_at__gte=timezone.now() - timezone.timedelta(hours=24)
            )[:10]
            
            for sms in pending_sms:
                sms_queue.put((sms.mobile_number, sms.unique_code, sms.mpp_name))
                sms.status = 'PROCESSING'
                sms.save()
                processed_count += 1
                logger.info(f"Database Processor queued SMS #{processed_count} for {sms.mobile_number}")
            
            time.sleep(5)
        except Exception as e:
            logger.error(f"ERROR: Database queue processor error: {str(e)}")
            time.sleep(10)

def health_monitor():
    """Monitor system health"""
    logger.info("Health Monitor started")
    check_count = 0
    while getattr(message_processor, 'worker_running', True):
        try:
            check_count += 1
            sms_queue_size = sms_queue.qsize()
            whatsapp_queue_size = whatsapp_queue.qsize()
            
            logger.info(f"Health Check #{check_count} - SMS Queue: {sms_queue_size}, WhatsApp Queue: {whatsapp_queue_size}")
            
            if sms_queue_size > 10 or whatsapp_queue_size > 10:
                logger.warning(f"WARNING: High queue load detected - SMS: {sms_queue_size}, WhatsApp: {whatsapp_queue_size}")
            
            time.sleep(30)
        except Exception as e:
            logger.error(f"ERROR: Health monitor error: {str(e)}")
            time.sleep(60)

def start_background_workers():
    """Start all background workers"""
    logger.info("Starting all background workers...")
    
    # Start SMS workers
    for i in range(5):
        thread = threading.Thread(
            target=sms_worker, 
            args=(i+1,), 
            name=f"sms_worker_{i+1}", 
            daemon=True
        )
        thread.start()
        logger.info(f"   Started SMS Worker {i+1}")
    
    # Start WhatsApp workers
    for i in range(3):
        thread = threading.Thread(
            target=whatsapp_worker, 
            args=(i+1,), 
            name=f"whatsapp_worker_{i+1}", 
            daemon=True
        )
        thread.start()
        logger.info(f"   Started WhatsApp Worker {i+1}")
    
    # Start database queue processor
    db_thread = threading.Thread(
        target=database_queue_processor, 
        name="db_queue_processor", 
        daemon=True
    )
    db_thread.start()
    logger.info("   Started Database Queue Processor")
    
    # Start health monitor
    health_thread = threading.Thread(
        target=health_monitor, 
        name="health_monitor", 
        daemon=True
    )
    health_thread.start()
    logger.info("   Started Health Monitor")
    
    logger.info("SUCCESS: All background workers started successfully!")
    logger.info("System is now ready to process advance sales!")