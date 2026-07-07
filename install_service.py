"""
Install as Windows Service (Optional)
"""
import win32serviceutil
import win32service
import win32event
import servicemanager
import socket
import sys
import os

class WhatsAppDesktopService(win32serviceutil.ServiceFramework):
    _svc_name_ = "ShwetdharaWhatsAppSender"
    _svc_display_name_ = "Shwetdhara WhatsApp Message Sender"
    _svc_description_ = "Sends WhatsApp messages from Shwetdhara Milk Advance Sale system"
    
    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        socket.setdefaulttimeout(60)
        self.is_running = True
        
    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        self.is_running = False
        win32event.SetEvent(self.hWaitStop)
        
    def SvcDoRun(self):
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, '')
        )
        
        # Change to project directory
        project_path = r"C:\path\to\your\shwetDhara_project"
        os.chdir(project_path)
        
        # Add to Python path
        sys.path.insert(0, project_path)
        
        # Setup Django
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'shwetDhara_project.settings')
        
        import django
        django.setup()
        
        # Import and run service
        from main_app.whatsapp_desktop_service import WhatsAppDesktopService
        self.main_service = WhatsAppDesktopService()
        self.main_service.run()

if __name__ == '__main__':
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(WhatsAppDesktopService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(WhatsAppDesktopService)