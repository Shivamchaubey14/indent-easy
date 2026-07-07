# main_app/tasks_sequential.py - CORRECTED VERSION

import threading
import time
import json
import re
import requests
from datetime import timedelta
from celery import shared_task
from django.db import transaction
from django.utils import timezone
from django.conf import settings
import logging
from decouple import config
from .models import MessageQueue, MessageDeliveryLog, AdvanceSale, WhatsAppLog, SMSQueue

logger = logging.getLogger(__name__)

# ============================================================================
# WHATSAPP BUSINESS API CLIENT (FIXED NAME)
# ============================================================================

class WhatsAppBusinessAPIClient:  # This is the correct class name
    """
    WhatsApp Business API client - Updated with working configuration
    """
    _instance = None
    _lock = threading.Lock()
    
    def __init__(self):
        self.config = getattr(settings, 'WHATSAPP_BUSINESS_API', {})
        
        # Get credentials from settings
        self.access_token = self.config.get('ACCESS_TOKEN', '')
        self.phone_number_id = self.config.get('PHONE_NUMBER_ID', '')
        self.template_name = self.config.get('TEMPLATE_NAME', 'shwetdhara_remainder_template')
        self.template_language = self.config.get('TEMPLATE_LANGUAGE', 'hi')
        self.api_version = self.config.get('API_VERSION', 'v22.0')
        self.base_url = self.config.get('BASE_URL', 'https://graph.facebook.com')
        
        # Headers
        self.headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json',
        }
        
        # Rate limiting
        self.last_call_time = None
        self.min_call_interval = 0.1  # 100ms between calls
        
        # Log configuration
        token_display = f"{self.access_token[:20]}..." if self.access_token else "MISSING"
        logger.info(f"WhatsApp API Client Initialized")
        logger.info(f"   Phone Number ID: {self.phone_number_id}")
        logger.info(f"   Template: {self.template_name}")
        logger.info(f"   Language: {self.template_language}")
        logger.info(f"   Token: {token_display}")
        
        if not self.access_token:
            logger.error("ERROR: WHATSAPP_ACCESS_TOKEN is empty in .env file!")
        if not self.phone_number_id:
            logger.error("ERROR: WHATSAPP_PHONE_NUMBER_ID is empty!")
    
    @classmethod
    def get_instance(cls):
        """Singleton pattern"""
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
        return cls._instance
    
    def _format_phone_number(self, phone_number):
        """Format phone number to E.164 format"""
        if not phone_number:
            return None
        
        # Remove all non-digit characters
        digits = ''.join(filter(str.isdigit, str(phone_number)))
        
        if not digits:
            return None
        
        # WhatsApp requires E.164 format with country code
        if len(digits) == 10:
            # Indian number without country code
            return f"91{digits}"
        elif len(digits) == 12 and digits.startswith('91'):
            # Already has Indian country code
            return digits
        elif len(digits) == 11 and digits.startswith('0'):
            # Number with leading zero
            return f"91{digits[1:]}"
        elif len(digits) > 12:
            # Take last 12 digits (in case of extra characters)
            return digits[-12:]
        else:
            # Return as-is, API will validate
            return digits
    
    def _rate_limit(self):
        """Implement rate limiting between API calls"""
        if self.last_call_time:
            elapsed = time.time() - self.last_call_time
            if elapsed < self.min_call_interval:
                sleep_time = self.min_call_interval - elapsed
                time.sleep(sleep_time)
        self.last_call_time = time.time()
    
    def send_template_message(self, phone_number, template_variables):
        """
        Send WhatsApp template message
        Returns: (success, message_id, error_message)
        """
        # Always refresh token from settings (fixes stale singleton token)
        self.config = getattr(settings, 'WHATSAPP_BUSINESS_API', {})
        self.access_token = self.config.get('ACCESS_TOKEN', '')
        self.headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json',
        }

        if not self.access_token or not self.phone_number_id:
            error = "WhatsApp API not configured - check .env file"
            logger.error(f"ERROR: {error}")
            return False, None, error
        
        # Format phone number
        formatted_phone = self._format_phone_number(phone_number)
        if not formatted_phone:
            error = f"Invalid phone number: {phone_number}"
            logger.error(f"ERROR: {error}")
            return False, None, error
        
        # Apply rate limiting
        self._rate_limit()
        
        # Build payload
        payload = {
            "messaging_product": "whatsapp",
            "to": formatted_phone,
            "type": "template",
            "template": {
                "name": self.template_name,
                "language": {
                    "code": self.template_language
                }
            }
        }
        
        # Add body parameters if we have template variables
        if template_variables:
            parameters = []
            
            # Your template expects exactly 3 parameters
            param_count = 3
            for i in range(1, param_count + 1):
                value = template_variables.get(str(i), '')
                if value:
                    parameters.append({
                        "type": "text",
                        "text": str(value)[:1024]  # WhatsApp limit
                    })
                else:
                    # If variable is missing, use placeholder
                    parameters.append({
                        "type": "text",
                        "text": ""  # Empty string for missing variables
                    })
            
            if parameters:
                payload["template"]["components"] = [
                    {
                        "type": "body",
                        "parameters": parameters
                    }
                ]
        
        # API URL
        url = f"{self.base_url}/{self.api_version}/{self.phone_number_id}/messages"
        
        logger.info(f"Sending WhatsApp Template:")
        logger.info(f"   To: {formatted_phone}")
        logger.info(f"   Template: {self.template_name}")
        logger.info(f"   Language: {self.template_language}")
        
        # Debug: Log the payload (truncated for security)
        logger.debug(f"   Payload: {json.dumps(payload, ensure_ascii=False)[:200]}...")
        
        # Send request with retry logic
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    url,
                    headers=self.headers,
                    json=payload,
                    timeout=30
                )
                
                logger.info(f"API Response: HTTP {response.status_code}")
                
                if response.status_code == 200:
                    response_data = response.json()
                    message_id = response_data.get('messages', [{}])[0].get('id')
                    contacts = response_data.get('contacts', [])
                    
                    if contacts:
                        wa_id = contacts[0].get('wa_id', 'unknown')
                        logger.info(f"SUCCESS: WhatsApp sent successfully to {wa_id}")
                    else:
                        logger.info(f"SUCCESS: WhatsApp sent! Message ID: {message_id}")
                    
                    return True, message_id, None
                    
                else:
                    # Handle errors
                    error_data = response.json()
                    error_msg = error_data.get('error', {}).get('message', 'Unknown error')
                    error_code = error_data.get('error', {}).get('code', 'UNKNOWN')
                    
                    logger.error(f"ERROR: WhatsApp API failed: {error_code} - {error_msg}")
                    
                    # Special handling for common errors
                    if response.status_code == 401:
                        logger.error("   ERROR: Token expired or invalid")
                        logger.error("   Update .env file with new token")
                    elif response.status_code == 400:
                        logger.error("   ERROR: Bad request - check template name/variables")
                    elif response.status_code == 404:
                        logger.error("   ERROR: Template not found or not approved")
                    elif response.status_code == 429:  # Rate limit
                        logger.error("   ERROR: Rate limited, waiting 60 seconds")
                        if attempt < max_retries - 1:
                            time.sleep(60)
                            continue
                    
                    # Don't retry on client errors (4xx)
                    if 400 <= response.status_code < 500:
                        break
                    
            except requests.exceptions.Timeout:
                error = "WhatsApp API timeout"
                logger.error(f"ERROR: {error}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (attempt + 1))
                    continue
            except requests.exceptions.ConnectionError:
                error = "Cannot connect to WhatsApp API"
                logger.error(f"ERROR: {error}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (attempt + 1))
                    continue
            except Exception as e:
                error = f"Unexpected error: {str(e)}"
                logger.error(f"ERROR: {error}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (attempt + 1))
                    continue
        
        return False, None, error if 'error' in locals() else "Failed after max retries"

# Global instance
whatsapp_api_client = WhatsAppBusinessAPIClient.get_instance()

# ============================================================================
# CELERY TASKS - ALL REQUIRED TASKS
# ============================================================================

@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def queue_advance_sale_messages(self, advance_sale_id, messages_data):
    """
    Queue messages in database after transaction commits
    """
    try:
        advance_sale = AdvanceSale.objects.get(id=advance_sale_id)
        
        with transaction.atomic():
            # Get next sequence number
            last_msg = MessageQueue.objects.order_by('-sequence_number').first()
            seq_num = (last_msg.sequence_number + 1) if last_msg else 1
            
            messages = []
            
            # Queue SMS messages
            for sms in messages_data.get("sms", []):
                # Remove emojis from SMS
                sms_message = sms["message"]
                sms_message = remove_emojis(sms_message)
                
                msg = MessageQueue(
                    message_type='SMS',
                    advance_sale=advance_sale,
                    unique_code=advance_sale.unique_code,
                    mobile_number=sms["mobile_number"],
                    message=sms_message,
                    mpp_name=sms["mpp_name"],
                    cycle_info=sms["cycle_info"],
                    status='PENDING',
                    sequence_number=seq_num,
                    created_at=timezone.now(),
                    queued_at=timezone.now()
                )
                messages.append(msg)
                seq_num += 1
            
            # Queue WhatsApp messages with template variables
            for wa in messages_data.get("whatsapp", []):
                # Generate template variables
                template_vars = generate_whatsapp_template_variables(
                    mpp_name=wa["mpp_name"],
                    items=messages_data.get("items", []),
                    unique_code=advance_sale.unique_code,
                    cycle=advance_sale.cycle,
                    sale_date=advance_sale.sale_date
                )
                
                # Store as JSON with template info
                message_with_vars = {
                    'template_name': 'shwetdhara_remainder_template',
                    'template_variables': template_vars,
                    'original_message': f"Order shipped to {wa['mpp_name']}"
                }
                
                msg = MessageQueue(
                    message_type='WHATSAPP',
                    advance_sale=advance_sale,
                    unique_code=advance_sale.unique_code,
                    mobile_number=wa["mobile_number"],
                    message=json.dumps(message_with_vars),
                    mpp_name=wa["mpp_name"],
                    cycle_info=wa["cycle_info"],
                    status='PENDING',
                    sequence_number=seq_num,
                    created_at=timezone.now(),
                    queued_at=timezone.now()
                )
                messages.append(msg)
                seq_num += 1
            
            # Bulk create
            if messages:
                MessageQueue.objects.bulk_create(messages)
                logger.info(f"SUCCESS: Queued {len(messages)} messages for advance sale {advance_sale.unique_code}")
            else:
                logger.warning(f"No messages to queue for advance sale {advance_sale.unique_code}")
        
        # Trigger processing
        logger.info("Triggering message queue processing...")
        try:
            process_message_queue.delay()
        except Exception as e:
            logger.error(f"ERROR: Failed to trigger process_message_queue: {e}")
        
        return True
        
    except Exception as exc:
        logger.error(f"ERROR: Failed to queue messages: {exc}", exc_info=True)
        raise self.retry(exc=exc)

@shared_task(bind=True, max_retries=3)
def process_message_queue(self):
    """
    Process messages sequentially - ONE at a time
    """
    message = None
    try:
        with transaction.atomic():
            # Get next pending message
            message = MessageQueue.objects.select_for_update(skip_locked=True).filter(
                status__in=['PENDING', 'RETRY'],
                retry_count__lt=3
            ).order_by('sequence_number', 'created_at').first()
            
            if not message:
                logger.debug("No messages to process")
                return 0
            
            # Mark as processing
            message.mark_processing()
            logger.info(f"Processing {message.message_type} message ID {message.id}")
        
        # Process the message
        start_time = timezone.now()
        success = False
        error_msg = None
        template_message_id = None
        api_response = None
        
        try:
            if message.message_type == 'SMS':
                success, error_msg = send_sms_auto(message)
            elif message.message_type == 'WHATSAPP':
                success, template_message_id, error_msg, api_response = send_whatsapp_template(message)
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error during message sending: {e}")
        
        # Update status
        with transaction.atomic():
            response_time = (timezone.now() - start_time).total_seconds() * 1000
            
            # Create delivery log
            MessageDeliveryLog.objects.create(
                message_queue=message,
                attempt_number=message.retry_count + 1,
                status='SENT' if success else 'FAILED',
                sent_via=message.message_type,
                error_message=error_msg[:500] if error_msg else None,
                response_time_ms=int(response_time)
            )
            
            if success:
                message.mark_sent()
                logger.info(f"SUCCESS: {message.message_type} sent to {message.mobile_number}")
                
                # Create audit logs
                if message.message_type == 'WHATSAPP':
                    # Parse stored message data
                    message_data = {}
                    try:
                        message_data = json.loads(message.message)
                    except:
                        message_data = {'original_message': message.message}
                    
                    WhatsAppLog.objects.create(
                        mobile_number=message.mobile_number,
                        message=message_data.get('original_message', '')[:500],
                        unique_code=message.unique_code,
                        mpp_name=message.mpp_name,
                        status='SENT',
                        sent_via='META_API',
                        template_name=message_data.get('template_name'),
                        template_message_id=template_message_id,
                        template_variables=message_data.get('template_variables'),
                        api_response=api_response,
                        sent_at = timezone.now()
                    )
                elif message.message_type == 'SMS':
                    SMSQueue.objects.create(
                        mobile_number=message.mobile_number,
                        unique_code=message.unique_code,
                        mpp_name=message.mpp_name,
                        status='SENT',
                        sent_at=timezone.now()
                    )
            else:
                if message.retry_count < 2:
                    message.mark_for_retry(f"Delivery failed: {error_msg}")
                    logger.warning(f"Marked for retry (attempt {message.retry_count + 1})")
                else:
                    message.mark_failed(f"Max retries exceeded: {error_msg}")
                    logger.error(f"ERROR: {message.message_type} failed after max retries")
        
        # Check for more messages
        with transaction.atomic():
            remaining_count = MessageQueue.objects.filter(
                status__in=['PENDING', 'RETRY'],
                retry_count__lt=3
            ).count()
            
            if remaining_count > 0:
                logger.info(f"{remaining_count} messages remaining, continuing...")
                process_message_queue.apply_async(countdown=2, queue='message_queue')
            else:
                logger.info("All messages processed!")
        
        return 1 if success else 0
        
    except Exception as exc:
        logger.error(f"ERROR in process_message_queue: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=60)

# Update the send_whatsapp_template function to properly create logs:

def send_whatsapp_template(message):
    """
    Send WhatsApp message using Business API template
    """
    try:
        # Parse stored message data
        message_data = {}
        try:
            message_data = json.loads(message.message)
        except json.JSONDecodeError:
            message_data = {'original_message': message.message}
        
        # Get template variables
        template_vars = message_data.get('template_variables')
        
        if not template_vars:
            # Generate template variables
            advance_sale = message.advance_sale
            items = []
            
            try:
                if advance_sale:
                    items = [{'stockItem': advance_sale.stock_item, 'quantity': advance_sale.quantity}]
            except:
                items = [{'stockItem': 'Products', 'quantity': 1}]
            
            template_vars = generate_whatsapp_template_variables(
                mpp_name=message.mpp_name,
                items=items,
                unique_code=message.unique_code,
                cycle=advance_sale.cycle if advance_sale else None,
                sale_date=advance_sale.sale_date if advance_sale else None
            )
        
        # Send via WhatsApp Business API
        success, message_id, error_msg = whatsapp_api_client.send_template_message(
            phone_number=message.mobile_number,
            template_variables=template_vars
        )
        
        # Prepare API response data for logging
        api_response_data = {
            'template_name': message_data.get('template_name', 'shwetdhara_remainder_template'),
            'variables_used': template_vars,
            'timestamp': timezone.now().isoformat(),
            'success': success,
            'message_id': message_id,
            'error': error_msg
        }
        
        # Create WhatsAppLog with ADVANCE_SALE purpose
        if success and message.advance_sale and message_id:
            whatsapp_log = WhatsAppLog.objects.create(
                mobile_number=message.mobile_number,
                message=message_data.get('original_message', '')[:500],
                unique_code=message.unique_code,
                mpp_name=message.mpp_name,
                status='SENT',
                sent_via='META_API',
                template_name=message_data.get('template_name'),
                template_message_id=message_id,  # Store the message ID for webhook matching
                template_variables=message_data.get('template_variables'),
                api_response=api_response_data,
                sent_at=timezone.now(),
                purpose='ADVANCE_SALE',
                advance_sale=message.advance_sale
            )
            logger.info(f"✅ Created WhatsAppLog ID {whatsapp_log.id} with message_id: {message_id}")
        elif not success and message.advance_sale:
            # Log failed attempt immediately
            whatsapp_log = WhatsAppLog.objects.create(
                mobile_number=message.mobile_number,
                message=message_data.get('original_message', '')[:500],
                unique_code=message.unique_code,
                mpp_name=message.mpp_name,
                status='FAILED',
                sent_via='META_API',
                template_name=message_data.get('template_name'),
                error_message=error_msg,
                api_response=api_response_data,
                sent_at=timezone.now(),
                purpose='ADVANCE_SALE',
                advance_sale=message.advance_sale
            )
            logger.error(f"❌ Created FAILED WhatsAppLog ID {whatsapp_log.id}")
        
        return success, message_id, error_msg, api_response_data
        
    except Exception as e:
        error_msg = f"Error in send_whatsapp_template: {str(e)}"
        logger.error(error_msg)
        return False, None, error_msg, None

def send_sms_auto(message):
    """Send SMS automatically"""
    try:
        # TODO: Implement actual SMS gateway
        # For now, simulate sending
        logger.info(f"[SMS] Simulating send to {message.mobile_number}")
        logger.info(f"[SMS Message]: {message.message[:100]}...")
        
        # Simulate API delay
        time.sleep(1)
        
        # Simulate 95% success rate for testing
        import random
        if random.random() < 0.95:
            return True, None
        else:
            return False, "Simulated SMS failure"
            
    except Exception as e:
        logger.error(f"SMS auto error: {e}")
        return False, str(e)

@shared_task
def recover_stale_messages():  # ADD THIS FUNCTION
    """Recover messages stuck in PROCESSING state"""
    try:
        stale_time = timezone.now() - timedelta(minutes=5)
        
        stale_messages = MessageQueue.objects.filter(
            status='PROCESSING',
            processing_started_at__lt=stale_time
        )
        
        stale_count = stale_messages.count()
        
        if stale_count > 0:
            logger.warning(f"Recovering {stale_count} stale messages")
            
            updated_count = 0
            for message in stale_messages:
                with transaction.atomic():
                    message_ref = MessageQueue.objects.select_for_update().get(id=message.id)
                    if message_ref.status == 'PROCESSING':
                        message_ref.mark_for_retry('Recovered from stale processing state')
                        updated_count += 1
            
            logger.info(f"SUCCESS: Recovered {updated_count}/{stale_count} stale messages")
            
            # Trigger processing if we recovered any
            if updated_count > 0:
                process_message_queue.apply_async(queue='message_queue')
        
        return stale_count
    except Exception as e:
        logger.error(f"ERROR: Recovery error: {e}")
        return 0
    
@shared_task
def cleanup_old_read_statuses():
    """
    Clean up old read status data
    """
    try:
        cutoff = timezone.now() - timedelta(days=90)  # 90 days retention
        
        old_reads = WhatsAppLog.objects.filter(
            status='READ',
            read_at__lt=cutoff
        )
        
        count = old_reads.count()
        
        if count > 0:
            # Archive or delete old read records
            # For now, just log
            logger.info(f"Found {count} old read messages (older than 90 days)")
            # old_reads.delete()  # Uncomment to actually delete
        
        return count
    except Exception as e:
        logger.error(f"Error in cleanup: {e}")
        return 0

@shared_task
def send_read_status_report():
    """
    Send daily read status report
    """
    try:
        from django.core.mail import send_mail
        
        yesterday = timezone.now() - timedelta(days=1)
        start_date = yesterday.replace(hour=0, minute=0, second=0)
        end_date = yesterday.replace(hour=23, minute=59, second=59)
        
        # Get read statistics for yesterday
        reads = WhatsAppLog.objects.filter(
            status='READ',
            read_at__range=(start_date, end_date)
        )
        
        total_reads = reads.count()
        
        if total_reads > 0:
            # Calculate average time to read
            total_seconds = 0
            valid_count = 0
            
            for msg in reads:
                if msg.sent_at and msg.read_at:
                    total_seconds += (msg.read_at - msg.sent_at).total_seconds()
                    valid_count += 1
            
            avg_time = total_seconds / valid_count if valid_count > 0 else 0
            
            # Prepare email
            subject = f"WhatsApp Read Report - {yesterday.date()}"
            message = f"""
            WhatsApp Read Status Report for {yesterday.date()}
            ================================================
            
            Total Messages Read: {total_reads}
            Average Time to Read: {avg_time:.1f} seconds
            
            Breakdown:
            """
            
            # Add hourly breakdown
            for hour in range(24):
                hour_reads = reads.filter(read_at__hour=hour).count()
                if hour_reads > 0:
                    message += f"\n  {hour:02d}:00 - {hour_reads} reads"
            
            # Send email
            # send_mail(
            #     subject,
            #     message,
            #     'noreply@yourdomain.com',
            #     ['admin@yourdomain.com'],
            #     fail_silently=True
            # )
            
            logger.info(f"📧 Read report prepared: {total_reads} reads yesterday")
        
        return total_reads
        
    except Exception as e:
        logger.error(f"Error sending read report: {e}")
        return 0

@shared_task
def clean_old_messages():  # ADD THIS FUNCTION
    """Clean old messages (retention)"""
    try:
        cutoff_date = timezone.now() - timedelta(days=30)
        
        # Get count before deletion
        to_delete = MessageQueue.objects.filter(
            status__in=['SENT', 'FAILED'],
            created_at__lt=cutoff_date
        )
        count = to_delete.count()
        
        if count > 0:
            logger.info(f"Cleaning {count} old messages (older than 30 days)")
            
            # Delete in batches to avoid huge transactions
            batch_size = 1000
            deleted_total = 0
            
            while True:
                batch = to_delete[:batch_size]
                if not batch.exists():
                    break
                    
                deleted_count, _ = batch.delete()
                deleted_total += deleted_count
                logger.info(f"  Deleted {deleted_total}/{count} so far...")
                
                if deleted_count < batch_size:
                    break
            
            logger.info(f"SUCCESS: Cleaned {deleted_total} old messages")
            return deleted_total
        else:
            logger.debug("No old messages to clean")
            return 0
            
    except Exception as e:
        logger.error(f"ERROR: Cleanup error: {e}")
        return 0

@shared_task
def restart_message_processing():  # ADD THIS FUNCTION
    """Restart message processing if it's stalled"""
    try:
        # Check if there are pending messages but no processing task
        pending_count = MessageQueue.objects.filter(
            status__in=['PENDING', 'RETRY'],
            retry_count__lt=3
        ).count()
        
        processing_count = MessageQueue.objects.filter(
            status='PROCESSING',
            processing_started_at__gte=timezone.now() - timedelta(minutes=5)
        ).count()
        
        if pending_count > 0 and processing_count == 0:
            logger.info(f"Restarting processing for {pending_count} pending messages")
            process_message_queue.apply_async(queue='message_queue')
            return pending_count
        else:
            logger.debug(f"No restart needed: {pending_count} pending, {processing_count} processing")
            return 0
            
    except Exception as e:
        logger.error(f"Error in restart_message_processing: {e}")
        return 0

@shared_task
def check_and_process_messages():  # ADD THIS FUNCTION
    """
    Check if there are pending messages and start processing
    """
    try:
        pending_count = MessageQueue.objects.filter(
            status__in=['PENDING', 'RETRY'],
            retry_count__lt=3
        ).count()
        
        if pending_count > 0:
            logger.info(f"Found {pending_count} pending messages, starting processor...")
            
            try:
                process_message_queue.apply_async(queue='message_queue')
                logger.info(f"SUCCESS: Triggered process_message_queue!")
                return pending_count
            except Exception as e:
                logger.error(f"ERROR: Failed to trigger process_message_queue: {e}")
                return 0
        else:
            logger.debug("No pending messages found")
            return 0
            
    except Exception as e:
        logger.error(f"Error checking messages: {e}")
        return 0

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def remove_emojis(text):
    """Remove emojis from text"""
    if not text:
        return text
    
    try:
        emoji_pattern = re.compile("["
            u"\U0001F600-\U0001F64F"
            u"\U0001F300-\U0001F5FF"
            u"\U0001F680-\U0001F6FF"
            u"\U0001F1E0-\U0001F1FF"
            u"\U00002702-\U000027B0"
            u"\U000024C2-\U0001F251"
            "]+", flags=re.UNICODE)
        
        return emoji_pattern.sub(r'', text)
    except Exception as e:
        logger.warning(f"Error removing emojis: {e}")
        return text

def generate_whatsapp_template_variables(mpp_name, items, unique_code, cycle=None, sale_date=None):
    """
    Generate template variables for WhatsApp template
    WITHOUT UOM in product list
    """
    from datetime import datetime
    
    # Variable 1: MPP Name (already includes code from prepare_messages_for_queue)
    mpp_display = str(mpp_name)[:100] if mpp_name else ""
    
    # Variable 2: Product List - WITHOUT UOM
    product_details = []
    for item in items:
        product_name = item.get('stockItem', 'Unknown Product')
        quantity = item.get('quantity', 0)
        
        # Clean product name - remove extra spaces
        product_name = product_name.strip()
        
        # JUST show product name and quantity (NO UOM)
        product_details.append(f"{product_name} - {quantity}")
    
    product_list = ", ".join(product_details)
    if len(product_list) > 500:
        product_list = product_list[:497] + "..."
    
    # Variable 3: Order Number
    # Just show the order number without "Order No:" prefix
    order_info = f"{unique_code}"
    
    print(f"📋 Generated WhatsApp variables:")
    print(f"   1. MPP: {mpp_display}")
    print(f"   2. Products: {product_list}")
    print(f"   3. Order: {order_info}")
    
    return {
        '1': mpp_display,      # MPP Name with code
        '2': product_list,     # Product List WITHOUT UOM
        '3': order_info        # Just the order number
    }
    
    
# Add to tasks_sequential.py after imports
from django.core.cache import cache

def prevent_duplicate_processing(message_id):
    """
    Prevent duplicate processing of the same message
    """
    cache_key = f"processing_msg_{message_id}"
    if cache.get(cache_key):
        return False  # Already being processed
    cache.set(cache_key, True, 300)  # Lock for 5 minutes
    return True

def clear_processing_lock(message_id):
    """Clear processing lock"""
    cache_key = f"processing_msg_{message_id}"
    cache.delete(cache_key)
    
def _is_mpp_number(self, phone_number):
    """Check if phone number belongs to an MPP before sending"""
    try:
        from .models import MPPWithCode
        
        # Format phone number
        formatted = self._format_phone_number(phone_number)
        if not formatted:
            return False
        
        # Remove country code
        clean_number = formatted
        if clean_number.startswith('91') and len(clean_number) > 10:
            clean_number = clean_number[2:]
        elif len(clean_number) > 10:
            clean_number = clean_number[-10:]
        
        # Check if MPP exists
        return MPPWithCode.objects.filter(
            sahayak_mobile_number__contains=clean_number
        ).exists()
        
    except Exception as e:
        logger.error(f"Error checking MPP number: {e}")
        return False


# ============================================================================
# INDENT (PURCHASE REQUISITION) HOD NOTIFICATIONS
# ============================================================================

@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def send_indent_hod_email(self, batch_requisition_number, employee_name, hod_email, items):
    """
    Send the "new indent" notification email to a single HOD in the background.

    Dispatched (one task per HOD) from ``main_app.views.createIndent`` so the
    user's request returns immediately after the requisitions are saved,
    instead of blocking on synchronous SMTP. One task per HOD means a failure
    for one recipient retries independently without re-sending to the others.

    Args:
        batch_requisition_number: e.g. "REQ0123" (shared by all items in the indent)
        employee_name: name shown in the email signature
        hod_email: the single HOD recipient address
        items: list of dicts, each with item_name / quantity / location /
               remark / expected_delivery_date
    """
    from django.core.mail import EmailMessage

    if not hod_email or not items:
        logger.warning(
            f"send_indent_hod_email: nothing to send for {batch_requisition_number} "
            f"(email={hod_email!r}, items={len(items or [])})"
        )
        return {"sent": 0, "recipient": hod_email}

    try:
        # Build HTML table rows for the email body
        table_rows = ""
        for i, item in enumerate(items):
            table_rows += f"""
            <tr>
                <td>{i + 1}</td>
                <td>{item.get('item_name', '')}</td>
                <td>{item.get('quantity', '')}</td>
                <td>{item.get('location', '')}</td>
                <td>{item.get('remark', '')}</td>
                <td>{item.get('expected_delivery_date', '')}</td>
            </tr>
            """

        subject = f"New Indent Submitted - {batch_requisition_number}"
        body = f"""
        <p>Dear HOD,</p>
        <p>An indent has been submitted with the following details:</p>
        <table border="1" cellpadding="5" cellspacing="0">
            <thead>
                <tr>
                    <th>S.No</th>
                    <th>Item Name</th>
                    <th>Quantity</th>
                    <th>Location</th>
                    <th>Remarks</th>
                    <th>Expected Delivery Date</th>
                </tr>
            </thead>
            <tbody>
                {table_rows}
            </tbody>
        </table>
        <p>Regards,</p>
        <p>{employee_name}</p>"""

        email = EmailMessage(
            subject=subject,
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[hod_email],
        )
        email.content_subtype = "html"
        email.send()

        logger.info(
            f"Indent {batch_requisition_number}: notification sent to HOD {hod_email}"
        )
        return {"sent": 1, "recipient": hod_email}

    except Exception as exc:
        logger.error(
            f"Indent {batch_requisition_number}: failed to email HOD {hod_email}: {exc}"
        )
        # Retry just this recipient; other HODs are unaffected (separate tasks).
        raise self.retry(exc=exc)

