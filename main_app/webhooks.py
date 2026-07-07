"""
Complete WhatsApp Webhook Handler - FIXED VERSION with proper terminal status handling
"""
from datetime import timedelta
import json
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.db import transaction
from django.db.models import Q
from django.conf import settings

from .models import WhatsAppLog, MessageQueue, MPPWithCode, AdvanceSale
import logging

# Setup logger
logger = logging.getLogger(__name__)

@csrf_exempt
def whatsapp_webhook(request):
    """
    Complete WhatsApp webhook handler for verification and callbacks
    """
    if request.method == 'GET':
        return handle_webhook_verification(request)
    elif request.method == 'POST':
        return handle_webhook_callback(request)
    else:
        return HttpResponse('Method not allowed', status=405)


def handle_webhook_verification(request):
    """
    Handle WhatsApp webhook verification challenge
    """
    mode = request.GET.get('hub.mode')
    token = request.GET.get('hub.verify_token')
    challenge = request.GET.get('hub.challenge')
    
    logger.info(f"Webhook Verification Request:")
    logger.info(f"   Mode: {mode}")
    
    expected_token = getattr(settings, 'WHATSAPP_WEBHOOK_VERIFY_TOKEN', None)
    
    if mode == 'subscribe' and token == expected_token:
        logger.info("✅ Webhook verified successfully!")
        return HttpResponse(challenge, content_type='text/plain', status=200)
    else:
        logger.error("❌ Webhook verification failed!")
        return HttpResponse('Verification failed', status=403)


def handle_webhook_callback(request):
    """
    Handle WhatsApp webhook callback with delivery status updates
    """
    try:
        # Get raw body
        body = request.body.decode('utf-8')
        data = json.loads(body)
        
        logger.info("📩 WhatsApp Webhook Received")
        
        # Process the webhook data
        process_webhook_data(data)
        
        # Always return 200 OK to WhatsApp
        return JsonResponse({'status': 'ok'}, status=200)
        
    except json.JSONDecodeError as e:
        logger.error(f"❌ JSON decode error: {str(e)}")
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error(f"❌ Webhook processing error: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return JsonResponse({'error': 'Internal server error'}, status=500)


def process_webhook_data(data):
    """
    Process webhook data and update message statuses
    """
    for entry in data.get('entry', []):
        for change in entry.get('changes', []):
            field = change.get('field')
            value = change.get('value', {})
            
            logger.info(f"📋 Processing field: {field}")
            
            # Incoming messages
            if 'messages' in value:
                handle_incoming_messages(value)

            # Status updates (sent / delivered / read)
            if 'statuses' in value:
                handle_message_statuses(value)
            
            elif field == 'message_template_status_update':
                handle_template_status_update(value)
            
            else:
                logger.info(f"ℹ️ Unhandled field: {field}")


def handle_message_statuses(value):
    """
    Handle message status updates (delivered, read, failed, etc.)
    """
    statuses = value.get('statuses', [])
    
    for status in statuses:
        message_id = status.get('id')
        status_type = status.get('status', '').lower()
        timestamp = status.get('timestamp')
        recipient_id = status.get('recipient_id', '')
        errors = status.get('errors', [])
        
        logger.info(f"📨 Processing status update:")
        logger.info(f"   Message ID: {message_id}")
        logger.info(f"   Status: {status_type}")
        logger.info(f"   Recipient: {recipient_id}")
        
        if errors:
            logger.info(f"   Error details: {json.dumps(errors, indent=2)}")
        
        # Convert timestamp to datetime
        try:
            status_time = timezone.datetime.fromtimestamp(int(timestamp), tz=timezone.utc)
        except:
            status_time = timezone.now()
        
        # Find and update the WhatsAppLog
        update_whatsapp_log_status(message_id, status_type, status_time, errors, recipient_id)


def update_whatsapp_log_status(message_id, status_type, status_time, errors=None, recipient_id=None):
    """
    UPDATED: Proper status handling with terminal state protection
    """
    try:
        logger.info(f"🔄 Processing status update: {status_type.upper()} for message {message_id}")
        
        # CRITICAL: Only look for exact message_id match
        logs = WhatsAppLog.objects.filter(
            template_message_id=message_id,
            purpose='ADVANCE_SALE'
        )
        
        if not logs.exists():
            # For READ status, require exact match only
            if status_type == 'read':
                logger.warning(f"🚫 READ ignored – no exact message_id match for {message_id}")
                return
            
            # For other statuses, try alternative but with strict rules
            logs = find_advance_sale_log_strict(message_id, status_time, status_type, recipient_id)
            
            if not logs.exists():
                logger.warning(f"⚠️ Ignoring webhook: No matching ADVANCE_SALE message found for {message_id}")
                return
        
        for log in logs:
            logger.info(f"✅ Found ADVANCE_SALE log ID {log.id}")
            logger.info(f"   Mobile: {log.mobile_number}")
            logger.info(f"   Current status: {log.status}")
            logger.info(f"   Advance Sale: {log.advance_sale.unique_code if log.advance_sale else 'None'}")
            
            # Check if message is in terminal state (NO UPDATES ALLOWED)
            if log.is_terminal_status():
                logger.warning(f"🚫 Message in terminal status {log.status}, ignoring update to {status_type.upper()}")
                continue
            
            # Handle FAILED status specially (always allowed, terminal)
            if status_type == 'failed':
                handle_failed_status(log, status_time, errors, message_id, recipient_id)
                log.save()
                continue
            
            # Check if status update is valid
            if not log.can_update_to_status(status_type.upper()):
                logger.warning(f"⚠️ Status update not allowed: {log.status} → {status_type.upper()}")
                continue
            
            # Handle different status types
            if status_type == 'read':
                handle_read_status(log, status_time, message_id)
            elif status_type == 'delivered':
                handle_delivered_status(log, status_time)
            elif status_type == 'sent':
                handle_sent_status(log, status_time)
            else:
                logger.info(f"ℹ️ Unhandled status type: {status_type}")
            
            # Save the log
            log.save()
            
            # Update MessageQueue if applicable
            update_message_queue_status(log, status_type, status_time)
            
        logger.info(f"✅ Status update {status_type.upper()} processed successfully")
    
    except Exception as e:
        logger.error(f"❌ Error in update_whatsapp_log_status: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())


def find_advance_sale_log_strict(message_id, status_time, status_type, recipient_id=None):
    """
    STRICT alternative search ONLY for non-terminal SENT messages
    """
    logs = WhatsAppLog.objects.filter(
        purpose='ADVANCE_SALE',
        status='SENT',  # ONLY look for SENT messages
        not_registered=False  # NOT registered numbers
    )
    
    # If we have recipient_id, use it for matching
    if recipient_id:
        clean_recipient = clean_phone_number(recipient_id)
        if clean_recipient:
            logs = logs.filter(mobile_number__contains=clean_recipient[-10:])
    
    # Very narrow time window for SENT -> DELIVERED transitions
    time_window_start = status_time - timedelta(minutes=2)
    time_window_end = status_time + timedelta(minutes=2)
    
    logs = logs.filter(
        sent_at__range=(time_window_start, time_window_end)
    ).order_by('-sent_at')[:5]
    
    if logs.exists():
        logger.info(f"✅ Strict fallback found {logs.count()} logs")
    
    return logs


def handle_failed_status(log, status_time, errors, message_id, recipient_id):
    """
    Handle FAILED status with special handling for NOT_REGISTERED
    """
    error_code = None
    if errors and len(errors) > 0:
        error_code = errors[0].get('code')
    
    # Check for "Message undeliverable" (not registered on WhatsApp)
    if error_code == 131026:
        log.status = 'NOT_REGISTERED'
        log.not_registered = True
        log.error_message = 'Number not registered on WhatsApp'
        log.completed_at = status_time
        logger.error(f"❌ NOT REGISTERED ON WHATSAPP: {log.mobile_number}")
        logger.error(f"   Error 131026: Message undeliverable")
        logger.error(f"   Advance Sale: {log.advance_sale.unique_code if log.advance_sale else 'None'}")
        
        # Mark MessageQueue as failed
        update_message_queue_status(log, 'failed', status_time)
    else:
        log.status = 'FAILED'
        log.error_message = extract_error_message(errors)
        log.completed_at = status_time
        logger.error(f"❌ Message failed: {log.error_message}")
        logger.error(f"   Advance Sale: {log.advance_sale.unique_code if log.advance_sale else 'None'}")


def handle_read_status(log, status_time, message_id):
    """
    Handle READ status - requires strict validation
    """
    # Check if already read
    if log.is_read:
        logger.info(f"📖 Message already marked as read at {log.read_at}")
        return
    
    # Additional validation for READ
    if not log.template_message_id:
        logger.warning(f"⚠️ READ rejected - no template_message_id in log {log.id}")
        return
    
    # Message must have been delivered first (except rare cases)
    if not log.delivered_at:
        logger.warning(f"⚠️ READ without delivery for log {log.id}")
        # Still accept in some cases
    
    # Mark as read
    log.mark_as_read(status_time)
    log.completed_at = status_time  # READ is terminal
    
    # Log the read event
    logger.info(f"✅✅✅ ADVANCE SALE MESSAGE READ CONFIRMED!")
    logger.info(f"   MPP: {log.mpp_name}")
    logger.info(f"   Mobile: {log.mobile_number}")
    logger.info(f"   Advance Sale: {log.advance_sale.unique_code if log.advance_sale else 'None'}")
    logger.info(f"   Read at: {status_time}")
    
    if log.sent_at:
        time_to_read = (status_time - log.sent_at).total_seconds()
        logger.info(f"   Time to read: {time_to_read:.1f} seconds")
    
    # Trigger post-read actions
    trigger_post_read_actions(log)


def handle_delivered_status(log, status_time):
    """Handle DELIVERED status"""
    log.status = 'DELIVERED'
    log.delivered_at = status_time
    logger.info(f"📨 Advance sale message delivered to {log.mobile_number}")
    logger.info(f"   Advance Sale: {log.advance_sale.unique_code if log.advance_sale else 'None'}")


def handle_sent_status(log, status_time):
    """Handle SENT status"""
    log.status = 'SENT'
    log.sent_at = status_time
    logger.info(f"📤 Advance sale message sent to {log.mobile_number}")
    logger.info(f"   Advance Sale: {log.advance_sale.unique_code if log.advance_sale else 'None'}")


def trigger_post_read_actions(log):
    """
    Trigger actions after message is read
    """
    try:
        logger.info(f"📊 Read confirmation for advance sale {log.unique_code}")
        logger.info(f"   MPP: {log.mpp_name}")
        logger.info(f"   Mobile: {log.mobile_number}")
        
        # You can add business logic here
        
    except Exception as e:
        logger.error(f"Error in post-read actions: {e}")


def extract_error_message(errors):
    """Extract error message from errors array"""
    if not errors or len(errors) == 0:
        return "Unknown error"
    
    error_data = errors[0]
    error_code = error_data.get('code', 0)
    error_msg = error_data.get('message', 'Unknown error')
    
    return f"Error {error_code}: {error_msg}"


def update_message_queue_status(log, status_type, status_time):
    """
    Update MessageQueue entries based on WhatsAppLog update
    """
    try:
        if log.unique_code:
            queue_items = MessageQueue.objects.filter(
                unique_code=log.unique_code,
                message_type='WHATSAPP'
            )
            
            for item in queue_items:
                if status_type == 'sent':
                    item.status = 'SENT'
                    item.sent_at = status_time
                elif status_type == 'delivered':
                    item.status = 'DELIVERED'
                    item.completed_at = status_time
                elif status_type in ['failed', 'not_registered']:
                    item.status = 'FAILED'
                    item.last_error = log.error_message
                    item.completed_at = status_time
                
                item.save()
                logger.info(f"   📋 Updated MessageQueue ID {item.id} to {item.status}")
    
    except Exception as e:
        logger.error(f"   ⚠️ Error updating MessageQueue: {str(e)}")


def handle_incoming_messages(value):
    """
    Handle incoming messages from users
    """
    messages = value.get('messages', [])
    
    for message in messages:
        message_id = message.get('id')
        from_number = message.get('from', '')
        message_type = message.get('type', '')
        timestamp = message.get('timestamp')
        
        logger.info(f"📥 Incoming Message from {from_number}:")
        logger.info(f"   Type: {message_type}")
        logger.info(f"   Message ID: {message_id}")
        
        # Clean the phone number
        clean_number = clean_phone_number(from_number)
        
        # Create log for incoming message
        try:
            # Convert timestamp to datetime
            try:
                msg_time = timezone.datetime.fromtimestamp(int(timestamp), tz=timezone.utc)
            except:
                msg_time = timezone.now()
            
            # Create log entry
            WhatsAppLog.objects.create(
                mobile_number=clean_number,
                message=f"Incoming {message_type} message",
                status='RECEIVED',
                sent_via='USER',
                api_response=message,
                created_at=msg_time,
                purpose='GENERAL'
            )
            
            logger.info(f"   ✅ Logged incoming message from {clean_number}")
        
        except Exception as e:
            logger.error(f"   ⚠️ Error logging incoming message: {str(e)}")


def handle_template_status_update(value):
    """
    Handle template status updates
    """
    event = value.get('event', '')
    message_template_id = value.get('message_template_id', '')
    previous_category = value.get('previous_category', '')
    new_category = value.get('new_category', '')
    
    logger.info(f"📋 Template Status Update:")
    logger.info(f"   Event: {event}")
    logger.info(f"   Template ID: {message_template_id}")
    logger.info(f"   Previous: {previous_category}")
    logger.info(f"   New: {new_category}")


def clean_phone_number(phone_number):
    """
    Clean phone number by removing country code
    """
    if not phone_number:
        return ''
    
    phone_str = str(phone_number).strip()
    
    # Remove +91 or 91 prefix
    if phone_str.startswith('+91'):
        return phone_str[3:]
    elif phone_str.startswith('91'):
        return phone_str[2:]
    else:
        return phone_str