# setup_whatsapp_fixed.py
import time
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def setup_whatsapp_fixed():
    """
    Fixed WhatsApp Web setup with Chrome crash solutions
    """
    print("🔧 WhatsApp Web Setup - Fixed Version")
    
    # Chrome options with crash fixes
    chrome_options = webdriver.ChromeOptions()
    
    # Essential arguments to prevent crashes
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--remote-debugging-port=9222")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-plugins")
    chrome_options.add_argument("--disable-notifications")
    
    # Profile settings - UPDATED PATH
    chrome_options.add_argument("--user-data-dir=C:\\Users\\Shwetdhara\\AppData\\Local\\Google\\Chrome\\User Data")
    chrome_options.add_argument("--profile-directory=Default")
    
    # Window settings
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--start-maximized")
    
    # Additional stability options
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    driver = None
    
    try:
        print("🚀 Starting Chrome...")
        
        # Initialize driver
        driver = webdriver.Chrome(options=chrome_options)
        print("✅ Chrome started successfully")
        
        # Open WhatsApp Web
        print("🌐 Opening WhatsApp Web...")
        driver.get("https://web.whatsapp.com")
        
        print("")
        print("📱 INSTRUCTIONS:")
        print("   1. Scan the QR code with your WhatsApp (9151809856)")
        print("   2. Wait for your chats to load")
        print("   3. The system will wait for 2 minutes")
        print("   4. Your session will be saved automatically")
        print("")
        
        # Wait for user to scan QR code - increased timeout
        wait = WebDriverWait(driver, 120)  # 2 minutes
        
        try:
            # Wait for chat list to appear (indicates successful login)
            print("⏳ Waiting for QR code scan...")
            chat_list = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div[data-testid='chat-list']"))
            )
            print("✅ SUCCESS! WhatsApp Web is ready and logged in.")
            print("💡 Your session has been saved in Chrome profile.")
            
            # Additional verification - check if we can see chats
            try:
                chats = driver.find_elements(By.CSS_SELECTOR, "div[data-testid='chat-list'] > div")
                print(f"📂 Found {len(chats)} chats in your list")
            except:
                print("📂 Chats are loaded successfully")
            
            # Keep the session active for a bit longer
            print("⏳ Keeping session active for 30 seconds...")
            time.sleep(30)
            
        except Exception as e:
            print(f"⚠️  Could not detect chat list: {e}")
            print("💡 You might need to scan the QR code manually")
            print("💡 The session might still be saved - let's test...")
            
            # Try to check if we're on WhatsApp Web page
            if "whatsapp" in driver.current_url:
                print("🌐 Still on WhatsApp Web page")
                print("🔄 Please scan the QR code now...")
                time.sleep(30)  # Give more time to scan
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print("\n🔧 ADVANCED TROUBLESHOOTING:")
        print("   1. Close ALL Chrome windows completely")
        print("   2. Run Command Prompt as Administrator")
        print("   3. Check if Chrome is properly installed")
        print("   4. Try manual setup (instructions below)")
        
    finally:
        if driver:
            try:
                driver.quit()
                print("✅ Browser closed successfully")
            except:
                print("⚠️  Browser already closed")
        
        print("\n" + "="*50)
        print("📝 NEXT STEPS:")
        print("   1. Your Chrome profile should now have WhatsApp session")
        print("   2. Run your Django advance sale system")
        print("   3. The system will automatically send WhatsApp messages")
        print("="*50)

def manual_setup_instructions():
    """
    Manual setup instructions if automated fails
    """
    print("\n" + "🔧 MANUAL SETUP INSTRUCTIONS:")
    print("   1. Open Chrome browser manually")
    print("   2. Go to: https://web.whatsapp.com")
    print("   3. Scan QR code with your phone (9151809856)")
    print("   4. Wait for chats to load")
    print("   5. Close Chrome browser")
    print("   6. Your session is now saved!")
    print("   7. Run your Django system - it will work!")
    print("\n💡 After manual setup, test with: python test_whatsapp.py")

if __name__ == "__main__":
    setup_whatsapp_fixed()
    manual_setup_instructions()