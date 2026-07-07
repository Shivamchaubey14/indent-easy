# whatsapp_api_client.py
import requests
import json
import time
import logging
from django.conf import settings
from django.utils import timezone
from urllib.parse import urljoin

logger = logging.getLogger(__name__)

class WhatsAppBusinessAPI:
    """Meta WhatsApp Business API client for sending template messages"""
    
    def __init__(self):
        # Get credentials from settings
        self.access_token = settings.WHATSAPP_ACCESS_TOKEN
        self.phone_number_id = settings.WHATSAPP_PHONE_NUMBER_ID
        self.base_url = 'https://graph.facebook.com/v18.0'
        
        if not self.access_token:
            raise ValueError("WHATSAPP_ACCESS_TOKEN not configured in settings")
        if not self.phone_number_id:
            raise ValueError("WHATSAPP_PHONE_NUMBER_ID not configured in settings")
        
        self.headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json',
        }
        self.last_request_time = 0
        self.rate_limit_delay = 0.2  # 5 messages per second
    
    def _rate_limit(self):
        """Implement rate limiting to avoid hitting API limits"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - time_since_last)
        self.last_request_time = time.time()
    
    def send_template_message(self, to_number: str, mpp_name: str, product_list: str, unique_code: str):
        """
        Send WhatsApp template message using 'shipment_confirmation_for_sahayak' template
        
        Template format:
        प्रिय सहायक
        
        आपके MPP {{1}} पर निम्न उत्पाद आज डिलीवर होगा:
        {{2}}
        
        आर्डर संख्या: {{3}}
        
        कृपया प्राप्त हुई पर्ची पर विवरण लिख कर ड्राइवर को दें।
        
        धन्यवाद
        श्वेतधारा दुग्ध उत्पादक संस्था
        """
        # Clean and validate phone number
        to_number = self._clean_phone_number(to_number)
        if not to_number:
            return False, None, {'error': 'Invalid phone number format'}
        
        # Prepare the API payload
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_number,
            "type": "template",
            "template": {
                "name": "shipment_confirmation_for_sahayak",  # Your approved template name
                "language": {"code": "hi"},
                "components": [
                    {
                        "type": "body",
                        "parameters": [
                            {"type": "text", "text": mpp_name},      # {{1}} - MPP Name
                            {"type": "text", "text": product_list},  # {{2}} - Product List
                            {"type": "text", "text": unique_code}    # {{3}} - Unique Code
                        ]
                    }
                ]
            }
        }
        
        self._rate_limit()
        
        try:
            url = f"{self.base_url}/{self.phone_number_id}/messages"
            response = requests.post(url, headers=self.headers, json=payload, timeout=30)
            response_data = response.json()
            
            if response.status_code == 200:
                wamid = response_data.get('messages', [{}])[0].get('id')
                logger.info(f"✅ WhatsApp template sent to {to_number}. Message ID: {wamid}")
                return True, wamid, response_data
            else:
                error_msg = response_data.get('error', {}).get('message', 'Unknown error')
                error_code = response_data.get('error', {}).get('code', 0)
                logger.error(f"❌ WhatsApp API error {error_code}: {error_msg}")
                return False, None, response_data
                
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ WhatsApp API request failed: {str(e)}")
            return False, None, {'error': str(e)}
    
    def _clean_phone_number(self, phone_number: str):
        """Convert phone number to WhatsApp format (91XXXXXXXXXX)"""
        if not phone_number:
            return None
        
        # Remove all non-digit characters
        digits = ''.join(filter(str.isdigit, str(phone_number)))
        
        # Handle different formats
        if len(digits) == 10:
            return f"91{digits}"  # Add India country code
        elif len(digits) == 12 and digits.startswith('91'):
            return digits
        elif len(digits) > 12:
            return digits[-12:]  # Take last 12 digits
        else:
            logger.warning(f"⚠️ Unexpected phone format: {phone_number}")
            return None