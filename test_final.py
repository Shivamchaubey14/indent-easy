# test_whatsapp.py
import os
import sys
import django

# Set up Django
project_root = r"C:\Users\Shwetdhara\Desktop\shwetDhara_Project_v3\shwetDhara_project"
sys.path.insert(0, project_root)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'shwetDhara_project.settings')

django.setup()

# Test the WhatsApp functionality
from main_app.tasks_sequential import test_whatsapp_send

if __name__ == "__main__":
    success = test_whatsapp_send()
    if success:
        print("\n🎉 Everything is working! Your system is ready.")
    else:
        print("\n🔧 Check your .env file configuration and restart services.")