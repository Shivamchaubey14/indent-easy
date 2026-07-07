# main_app/whatsapp_auto.py
import os
import time
import logging
import subprocess
import urllib.parse
import threading
import pyautogui
import pyperclip
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class WhatsAppAutoClient:
    """
    Fully automatic WhatsApp client for Windows Desktop App
    Automatically opens WhatsApp and sends messages without user intervention
    """
    _instance = None
    _lock = threading.Lock()
    _window_lock = threading.Lock()  # Single window access
    _app_ready = False
    
    def __init__(self):
        self.is_app_installed = self._check_app_installed()
        self.whatsapp_process = None
        self.window_position = None
        self.message_queue = []
        self.queue_lock = threading.Lock()
        self.processing = False
        logger.info("WhatsAppAutoClient initialized")
    
    @classmethod
    def get_instance(cls):
        """Singleton pattern - only one WhatsApp instance"""
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
        return cls._instance
    
    def _check_app_installed(self):
        """Check if WhatsApp is installed"""
        try:
            # Common WhatsApp paths on Windows
            possible_paths = [
                os.path.expandvars(r"%LOCALAPPDATA%\WhatsApp\WhatsApp.exe"),
                r"C:\Users\{}\AppData\Local\WhatsApp\WhatsApp.exe".format(os.getlogin()),
                os.path.expandvars(r"%PROGRAMFILES%\WhatsApp\WhatsApp.exe"),
            ]
            
            for path in possible_paths:
                if os.path.exists(path):
                    logger.info(f"WhatsApp found at: {path}")
                    return True
            
            # Check if WhatsApp is in PATH
            try:
                subprocess.run(['where', 'whatsapp'], 
                             capture_output=True, 
                             creationflags=subprocess.CREATE_NO_WINDOW)
                return True
            except:
                pass
                
            logger.warning("WhatsApp not found in standard locations")
            return False
            
        except Exception as e:
            logger.error(f"Error checking WhatsApp: {e}")
            return False
    
    def ensure_app_running(self):
        """Ensure WhatsApp is running and ready"""
        with self._window_lock:
            try:
                # Check if WhatsApp process exists
                result = subprocess.run(
                    ['tasklist', '/FI', 'IMAGENAME eq WhatsApp.exe'],
                    capture_output=True,
                    text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                
                if "WhatsApp.exe" in result.stdout:
                    logger.info("WhatsApp is already running")
                    self._app_ready = True
                    return True
                else:
                    logger.info("Starting WhatsApp...")
                    # Start WhatsApp minimized
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    startupinfo.wShowWindow = subprocess.SW_MINIMIZE
                    
                    self.whatsapp_process = subprocess.Popen(
                        ['whatsapp://'],
                        startupinfo=startupinfo,
                        creationflags=subprocess.CREATE_NO_WINDOW
                    )
                    
                    # Wait for WhatsApp to load
                    time.sleep(5)
                    
                    # Bring WhatsApp to foreground
                    self._bring_to_foreground()
                    
                    # Wait for login/ready
                    time.sleep(3)
                    
                    self._app_ready = True
                    logger.info("WhatsApp started and ready")
                    return True
                    
            except Exception as e:
                logger.error(f"Failed to start WhatsApp: {e}")
                return False
    
    def _bring_to_foreground(self):
        """Bring WhatsApp window to foreground"""
        try:
            # Use PowerShell to bring window to front
            ps_script = '''
            Add-Type @"
              using System;
              using System.Runtime.InteropServices;
              public class Win32 {
                [DllImport("user32.dll")]
                [return: MarshalAs(UnmanagedType.Bool)]
                public static extern bool SetForegroundWindow(IntPtr hWnd);
                
                [DllImport("user32.dll")]
                public static extern IntPtr FindWindow(string className, string windowName);
              }
"@
            $window = [Win32]::FindWindow("Qt5152QWindowIcon", "WhatsApp")
            if ($window -ne [IntPtr]::Zero) {
                [Win32]::SetForegroundWindow($window)
            }
            '''
            
            subprocess.run(['powershell', '-Command', ps_script], 
                          capture_output=True, 
                          creationflags=subprocess.CREATE_NO_WINDOW)
            
            time.sleep(1)
            return True
            
        except Exception as e:
            logger.warning(f"Could not bring window to foreground: {e}")
            # Fallback: use pyautogui to activate window
            try:
                pyautogui.getWindowsWithTitle("WhatsApp")[0].activate()
                time.sleep(1)
                return True
            except:
                return False
    
    def _clean_phone_number(self, phone_number):
        """Clean phone number for WhatsApp"""
        if not phone_number:
            return None
        
        # Remove all non-digit characters
        digits = ''.join(filter(str.isdigit, str(phone_number)))
        
        # Indian number handling
        if digits.startswith('91') and len(digits) == 12:
            return digits  # 91XXXXXXXXXX
        elif len(digits) == 10:
            return '91' + digits  # Add India code
        elif len(digits) == 11 and digits.startswith('0'):
            return '91' + digits[1:]  # Remove leading 0
        
        return digits if len(digits) >= 10 else None
    
    def send_message_auto(self, phone_number, message, unique_code=None):
        """
        Fully automatic message sending
        Opens WhatsApp and sends message without user interaction
        """
        with self._window_lock:  # ONE message at a time
            try:
                # Ensure WhatsApp is ready
                if not self._app_ready:
                    if not self.ensure_app_running():
                        return False
                
                # Clean phone number
                clean_number = self._clean_phone_number(phone_number)
                if not clean_number:
                    logger.error(f"Invalid phone number: {phone_number}")
                    return False
                
                logger.info(f"Preparing to send WhatsApp to {clean_number}")
                
                # Step 1: Open chat with URL
                encoded_message = urllib.parse.quote(message)
                whatsapp_url = f"whatsapp://send?phone={clean_number}&text={encoded_message}"
                
                # Open WhatsApp with the URL
                os.startfile(whatsapp_url)
                time.sleep(2)  # Wait for WhatsApp to open/switch
                
                # Step 2: Ensure window is active
                self._bring_to_foreground()
                time.sleep(1)
                
                # Step 3: Check if we're in the right chat
                # Look for message input box
                time.sleep(1)
                
                # Step 4: Press ENTER to send
                pyautogui.press('enter')
                time.sleep(1)  # Wait for send
                
                # Step 5: Close chat (optional)
                # pyautogui.hotkey('ctrl', 'w')  # Close tab
                # time.sleep(0.5)
                
                logger.info(f"Successfully sent WhatsApp to {clean_number}")
                return True
                
            except Exception as e:
                logger.error(f"Failed to send WhatsApp automatically: {e}")
                
                # Fallback: Try simplified method
                return self._send_fallback(clean_number, message)
    
    def _send_fallback(self, phone_number, message):
        """Fallback sending method"""
        try:
            # Alternative: Use clipboard and keyboard
            pyperclip.copy(message)
            
            # Open WhatsApp URL
            encoded_message = urllib.parse.quote(message)
            whatsapp_url = f"whatsapp://send?phone={phone_number}&text={encoded_message}"
            os.startfile(whatsapp_url)
            time.sleep(3)
            
            # Paste and send
            pyautogui.hotkey('ctrl', 'v')  # Paste
            time.sleep(0.5)
            pyautogui.press('enter')
            time.sleep(1)
            
            logger.info(f"Sent via fallback method to {phone_number}")
            return True
            
        except Exception as e:
            logger.error(f"Fallback method also failed: {e}")
            return False
    
    def send_message_automated_ui(self, phone_number, message):
        """
        Alternative: Direct UI automation (requires WhatsApp already open)
        """
        try:
            # Ensure WhatsApp window is active
            whatsapp_windows = pyautogui.getWindowsWithTitle("WhatsApp")
            if not whatsapp_windows:
                logger.error("WhatsApp window not found")
                return False
            
            window = whatsapp_windows[0]
            window.activate()
            time.sleep(1)
            
            # Search for contact
            pyautogui.hotkey('ctrl', 'f')  # Search shortcut
            time.sleep(0.5)
            
            # Type phone number
            clean_number = self._clean_phone_number(phone_number)
            if clean_number and len(clean_number) == 12:
                # Remove country code for search
                search_number = clean_number[2:]  # Remove 91
                pyautogui.write(search_number)
                time.sleep(1)
                pyautogui.press('enter')
                time.sleep(2)
            
            # Type and send message
            pyautogui.write(message)
            time.sleep(0.5)
            pyautogui.press('enter')
            time.sleep(1)
            
            logger.info(f"Sent via UI automation to {phone_number}")
            return True
            
        except Exception as e:
            logger.error(f"UI automation failed: {e}")
            return False
    
    def close_app(self):
        """Close WhatsApp app"""
        try:
            if self.whatsapp_process:
                self.whatsapp_process.terminate()
                self.whatsapp_process = None
            
            # Kill WhatsApp process
            subprocess.run(['taskkill', '/F', '/IM', 'WhatsApp.exe'],
                          capture_output=True,
                          creationflags=subprocess.CREATE_NO_WINDOW)
            
            self._app_ready = False
            logger.info("WhatsApp closed")
            
        except Exception as e:
            logger.error(f"Error closing WhatsApp: {e}")