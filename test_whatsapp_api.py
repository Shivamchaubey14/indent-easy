# test_whatsapp_api.py
import os
import sys

project_root = r"C:\Users\Shwetdhara\Desktop\shwetDhara_Project_v3\shwetDhara_project"
sys.path.insert(0, project_root)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'shwetDhara_project.settings')

import django
django.setup()

from django.conf import settings
from decouple import Config, RepositoryEnv
import requests
import json
import time

# Load secrets from .env (never hardcode credentials in the repo)
_env = Config(RepositoryEnv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')))

print("🚀 WhatsApp Business API - TEST SCRIPT")
print("=" * 60)
print("📞 USING PROVEN WORKING CONFIGURATION")
print("=" * 60)

# ============================================
# HARDCODED CONFIGURATION (PROVEN WORKING)
# ============================================
WHATSAPP_CONFIG = {
    'ACCESS_TOKEN': _env('WHATSAPP_ACCESS_TOKEN', default=''),
    'PHONE_NUMBER_ID': _env('WHATSAPP_PHONE_NUMBER_ID', default='961336113724236'),
    'WABA_ID': _env('WABA_ID', default='2125104024924662'),
    'API_VERSION': _env('API_VERSION', default='v22.0'),
    'BASE_URL': _env('BASE_URL', default='https://graph.facebook.com'),
    'TEMPLATE_NAME': _env('TEMPLATE_NAME', default='shwetdhara_remainder_template'),
    'TEMPLATE_LANGUAGE': _env('TEMPLATE_LANGUAGE', default='hi'),
    'BUSINESS_NAME': _env('BUSINESS_NAME', default='shwetdhara milk producer company organisation'),
}

# Test phone numbers (Use WhatsApp-enabled numbers)
TEST_NUMBERS = [
    '917388150906',    # Your personal number
    '919569061304',# Test number
    '918052827676',
]

print(f"📋 Configuration Loaded:")
print(f"   • Phone ID: {WHATSAPP_CONFIG['PHONE_NUMBER_ID']}")
print(f"   • WABA ID: {WHATSAPP_CONFIG['WABA_ID']}")
print(f"   • Template: {WHATSAPP_CONFIG['TEMPLATE_NAME']}")
print(f"   • Language: {WHATSAPP_CONFIG['TEMPLATE_LANGUAGE']}")
print(f"   • Category: UTILITY (No opt-in required)")
print()

# ============================================
# TEST FUNCTIONS
# ============================================

def test_api_connection():
    """Test basic API connection"""
    print("🔧 Test 1: API Connection Test")
    print("-" * 40)
    
    headers = {'Authorization': f'Bearer {WHATSAPP_CONFIG["ACCESS_TOKEN"]}'}
    url = f"{WHATSAPP_CONFIG['BASE_URL']}/{WHATSAPP_CONFIG['API_VERSION']}/{WHATSAPP_CONFIG['PHONE_NUMBER_ID']}"
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        print(f"   URL: {url}")
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ SUCCESS! API is accessible")
            print(f"   • Display Number: {data.get('display_phone_number', 'N/A')}")
            print(f"   • Verified Name: {data.get('verified_name', 'N/A')}")
            return True
        else:
            error_data = response.json()
            print(f"❌ FAILED: {error_data.get('error', {}).get('message', 'Unknown error')}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ CONNECTION ERROR: {str(e)}")
        return False

def check_templates():
    """Check available templates"""
    print("\n🔧 Test 2: Template Verification")
    print("-" * 40)
    
    headers = {'Authorization': f'Bearer {WHATSAPP_CONFIG["ACCESS_TOKEN"]}'}
    url = f"{WHATSAPP_CONFIG['BASE_URL']}/{WHATSAPP_CONFIG['API_VERSION']}/{WHATSAPP_CONFIG['WABA_ID']}/message_templates"
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            templates = response.json().get('data', [])
            print(f"✅ Found {len(templates)} templates")
            
            # Find our template
            target_template = WHATSAPP_CONFIG['TEMPLATE_NAME']
            found = False
            
            for template in templates:
                if template.get('name') == target_template:
                    print(f"✅ Template '{target_template}' found:")
                    print(f"   • Language: {template.get('language')}")
                    print(f"   • Category: {template.get('category')}")
                    print(f"   • Status: {template.get('status')}")
                    
                    # Check if it's UTILITY category
                    if template.get('category') == 'UTILITY':
                        print(f"   • ✅ UTILITY category (No opt-in required)")
                    else:
                        print(f"   • ⚠️  {template.get('category')} category (Check opt-in requirements)")
                    
                    found = True
                    break
            
            if not found:
                print(f"❌ Template '{target_template}' NOT FOUND")
                print("   Available templates:")
                for template in templates[:10]:  # Show first 10
                    print(f"   - {template.get('name')} [{template.get('category')}] - {template.get('status')}")
            
            return found
            
        else:
            print(f"❌ Could not fetch templates: HTTP {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ ERROR: {str(e)}")
        return False

def send_test_message(phone_number, template_name=None):
    """Send a test message"""
    if template_name is None:
        template_name = WHATSAPP_CONFIG['TEMPLATE_NAME']
    
    print(f"\n🔧 Test 3: Sending to {phone_number}")
    print("-" * 40)
    
    headers = {
        'Authorization': f'Bearer {WHATSAPP_CONFIG["ACCESS_TOKEN"]}',
        'Content-Type': 'application/json'
    }
    
    url = f"{WHATSAPP_CONFIG['BASE_URL']}/{WHATSAPP_CONFIG['API_VERSION']}/{WHATSAPP_CONFIG['PHONE_NUMBER_ID']}/messages"
    
    # Build request body based on template
    if template_name == 'hello_world':
        # Simple hello_world template (no parameters)
        body = {
            "messaging_product": "whatsapp",
            "to": phone_number,
            "type": "template",
            "template": {
                "name": "hello_world",
                "language": {
                    "code": "en_US"
                }
            }
        }
    else:
        # Your custom template (with 3 parameters)
        body = {
            "messaging_product": "whatsapp",
            "to": phone_number,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {
                    "code": WHATSAPP_CONFIG['TEMPLATE_LANGUAGE']
                },
                "components": [
                    {
                        "type": "body",
                        "parameters": [
                            {
                                "type": "text",
                                "text": "ACHRAURA"  # MPP Name
                            },
                            {
                                "type": "text",
                                "text": "1. CF-25KG, 2. CF-50KG"  # Order Details
                            },
                            {
                                "type": "text",
                                "text": "2345"  # Delivery Number
                            }
                        ]
                    }
                ]
            }
        }
    
    try:
        print(f"   Template: {template_name}")
        print(f"   Phone: {phone_number}")
        print(f"   URL: {url}")
        
        response = requests.post(url, headers=headers, json=body, timeout=30)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            message_id = data.get('messages', [{}])[0].get('id', 'N/A')
            print(f"✅ SUCCESS! Message sent")
            print(f"   • Message ID: {message_id}")
            return {"success": True, "message_id": message_id}
        else:
            error_data = response.json()
            error_code = error_data.get('error', {}).get('code', 'N/A')
            error_message = error_data.get('error', {}).get('message', 'Unknown error')
            
            print(f"❌ FAILED: {error_message}")
            print(f"   • Error Code: {error_code}")
            
            # Handle specific errors
            if error_code == 133010:
                print(f"   • Issue: Phone number {phone_number} doesn't have WhatsApp")
            elif error_code == 132001:
                print(f"   • Issue: Template parameter mismatch or doesn't exist")
            elif error_code == 100:
                print(f"   • Issue: Permission error - check token permissions")
            
            return {"success": False, "error": error_message, "code": error_code}
            
    except requests.exceptions.RequestException as e:
        print(f"❌ CONNECTION ERROR: {str(e)}")
        return {"success": False, "error": str(e)}

def send_delivery_notification(phone_number, mpp_name, order_details, delivery_number):
    """Send actual delivery notification"""
    print(f"\n📦 Sending Delivery Notification to {phone_number}")
    print("-" * 40)
    
    headers = {
        'Authorization': f'Bearer {WHATSAPP_CONFIG["ACCESS_TOKEN"]}',
        'Content-Type': 'application/json'
    }
    
    url = f"{WHATSAPP_CONFIG['BASE_URL']}/{WHATSAPP_CONFIG['API_VERSION']}/{WHATSAPP_CONFIG['PHONE_NUMBER_ID']}/messages"
    
    body = {
        "messaging_product": "whatsapp",
        "to": phone_number,
        "type": "template",
        "template": {
            "name": WHATSAPP_CONFIG['TEMPLATE_NAME'],
            "language": {
                "code": WHATSAPP_CONFIG['TEMPLATE_LANGUAGE']
            },
            "components": [
                {
                    "type": "body",
                    "parameters": [
                        {
                            "type": "text",
                            "text": mpp_name
                        },
                        {
                            "type": "text",
                            "text": order_details
                        },
                        {
                            "type": "text",
                            "text": delivery_number
                        }
                    ]
                }
            ]
        }
    }
    
    try:
        print(f"   MPP: {mpp_name}")
        print(f"   Order: {order_details}")
        print(f"   Delivery No: {delivery_number}")
        
        response = requests.post(url, headers=headers, json=body, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            message_id = data.get('messages', [{}])[0].get('id', 'N/A')
            print(f"✅ SUCCESS! Delivery notification sent")
            print(f"   • Message ID: {message_id}")
            return {"success": True, "message_id": message_id}
        else:
            error_data = response.json()
            error_message = error_data.get('error', {}).get('message', 'Unknown error')
            print(f"❌ FAILED: {error_message}")
            return {"success": False, "error": error_message}
            
    except requests.exceptions.RequestException as e:
        print(f"❌ ERROR: {str(e)}")
        return {"success": False, "error": str(e)}

def bulk_test():
    """Run comprehensive tests"""
    print("\n" + "=" * 60)
    print("🧪 COMPREHENSIVE TEST SUITE")
    print("=" * 60)
    
    results = {
        'api_connection': False,
        'template_check': False,
        'test_messages': [],
        'delivery_notifications': []
    }
    
    # Test 1: API Connection
    results['api_connection'] = test_api_connection()
    
    # Test 2: Template Check
    results['template_check'] = check_templates()
    
    # Test 3: Send test messages
    print("\n🔧 Test 3: Sending Test Messages")
    print("-" * 40)
    
    for phone_number in TEST_NUMBERS:
        print(f"\n📱 Testing with: {phone_number}")
        
        # First test with hello_world
        print("   Step 1: Testing hello_world...")
        result1 = send_test_message(phone_number, 'hello_world')
        results['test_messages'].append({
            'phone': phone_number,
            'template': 'hello_world',
            **result1
        })
        
        # Wait 2 seconds between messages
        time.sleep(2)
        
        # Then test with your template
        print("   Step 2: Testing your template...")
        result2 = send_test_message(phone_number, WHATSAPP_CONFIG['TEMPLATE_NAME'])
        results['test_messages'].append({
            'phone': phone_number,
            'template': WHATSAPP_CONFIG['TEMPLATE_NAME'],
            **result2
        })
        
        # Wait 2 seconds
        time.sleep(2)
    
    # Test 4: Send actual delivery notification
    print("\n🔧 Test 4: Sending Delivery Notifications")
    print("-" * 40)
    
    delivery_data = [
        {
            'phone': TEST_NUMBERS[0],
            'mpp': 'ACHRAURA',
            'order': '1. CF-25KG, 2. CF-50KG',
            'delivery_no': '2345'
        }
    ]
    
    for delivery in delivery_data:
        result = send_delivery_notification(
            delivery['phone'],
            delivery['mpp'],
            delivery['order'],
            delivery['delivery_no']
        )
        results['delivery_notifications'].append({
            'phone': delivery['phone'],
            **result
        })
        
        # Wait 2 seconds
        time.sleep(2)
    
    return results

def print_summary(results):
    """Print test summary"""
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)
    
    print(f"\n🔗 API Connection: {'✅ PASS' if results['api_connection'] else '❌ FAIL'}")
    print(f"📋 Template Check: {'✅ PASS' if results['template_check'] else '❌ FAIL'}")
    
    print(f"\n📱 Test Messages Results:")
    for msg in results['test_messages']:
        status = '✅' if msg.get('success') else '❌'
        print(f"   {status} {msg['phone']} - {msg['template']}")
        if not msg.get('success'):
            print(f"     Error: {msg.get('error', 'Unknown')}")
    
    print(f"\n📦 Delivery Notifications:")
    for notif in results['delivery_notifications']:
        status = '✅' if notif.get('success') else '❌'
        print(f"   {status} {notif['phone']}")
        if notif.get('success'):
            print(f"     Message ID: {notif.get('message_id')}")
    
    # Overall status
    all_tests_passed = (
        results['api_connection'] and
        results['template_check'] and
        all(msg.get('success') for msg in results['test_messages'])
    )
    
    print("\n" + "=" * 60)
    if all_tests_passed:
        print("🎉 ALL TESTS PASSED! Your WhatsApp API is ready for production!")
    else:
        print("⚠️  Some tests failed. Check the errors above.")
    print("=" * 60)

# ============================================
# DJANGO SETTINGS INTEGRATION
# ============================================

def check_django_settings():
    """Check if Django settings are properly configured"""
    print("\n🔍 Checking Django Settings Integration")
    print("-" * 40)
    
    try:
        # Try to get settings
        config = getattr(settings, 'WHATSAPP_BUSINESS_API', {})
        
        if config:
            print("✅ WHATSAPP_BUSINESS_API found in Django settings")
            print(f"   Settings keys: {list(config.keys())}")
            
            # Compare with our hardcoded config
            print("\n📊 Configuration Comparison:")
            print("   Hardcoded vs Django Settings")
            print("   ----------------------------")
            
            for key in WHATSAPP_CONFIG:
                django_value = config.get(key, 'NOT SET')
                hardcoded_value = WHATSAPP_CONFIG[key]
                match = django_value == hardcoded_value
                status = '✅' if match else '⚠️'
                print(f"   {status} {key}:")
                print(f"     Hardcoded: {hardcoded_value}")
                print(f"     Django: {django_value}")
                
        else:
            print("⚠️  WHATSAPP_BUSINESS_API not found in Django settings")
            print("\n💡 Add this to your settings.py:")
            print("""
WHATSAPP_BUSINESS_API = {
    'ACCESS_TOKEN': config('WHATSAPP_ACCESS_TOKEN', default=''),
    'PHONE_NUMBER_ID': config('WHATSAPP_PHONE_NUMBER_ID', default=''),
    'WABA_ID': config('WHATSAPP_WABA_ID', default=''),
    'API_VERSION': 'v22.0',
    'BASE_URL': 'https://graph.facebook.com',
    'TEMPLATE_NAME': 'shwetdhara_remainder_template',
    'TEMPLATE_LANGUAGE': 'hi',
}
""")
            
    except Exception as e:
        print(f"❌ Error checking Django settings: {str(e)}")

# ============================================
# MAIN EXECUTION
# ============================================

if __name__ == "__main__":
    print("\n🔧 Available Tests:")
    print("   1. Quick connection test")
    print("   2. Template verification")
    print("   3. Send test message")
    print("   4. Send delivery notification")
    print("   5. Run all tests (comprehensive)")
    print("   6. Check Django settings")
    
    try:
        choice = input("\nEnter test number (1-6): ").strip()
        
        if choice == '1':
            test_api_connection()
        elif choice == '2':
            check_templates()
        elif choice == '3':
            phone = input("Enter phone number (91XXXXXXXXXX): ").strip()
            send_test_message(phone)
        elif choice == '4':
            phone = input("Enter phone number (91XXXXXXXXXX): ").strip()
            mpp = input("Enter MPP name: ").strip() or "ACHRAURA"
            order = input("Enter order details: ").strip() or "1. CF-25KG, 2. CF-50KG"
            delivery_no = input("Enter delivery number: ").strip() or "2345"
            send_delivery_notification(phone, mpp, order, delivery_no)
        elif choice == '5':
            results = bulk_test()
            print_summary(results)
        elif choice == '6':
            check_django_settings()
        else:
            print("❌ Invalid choice")
            
    except KeyboardInterrupt:
        print("\n\n👋 Test cancelled by user")
    
    print("\n" + "=" * 60)
    print("✅ Test script completed")
    print("=" * 60)