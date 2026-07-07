import os
import time
import subprocess
import sys

DJANGO_PORT = "8000"
PROJECT_PATH = r"C:\Users\SHIVAM\Desktop\shwetDhara_project"
PYTHON_ENV = r"C:\Users\SHIVAM\.virtualenvs\shwetdhara_project-XyjEUP3y\Scripts\python.exe"

def is_django_running():
    """Checks if Django is already running on the specified port."""
    try:
        output = subprocess.check_output(f'netstat -ano | findstr :{DJANGO_PORT}', shell=True, text=True)
        return bool(output.strip())  # If output exists, Django is running
    except subprocess.CalledProcessError:
        return False  # No output means no process is running

while True:
    if not is_django_running():
        print("Django server is not running. Restarting now...")
        os.chdir(PROJECT_PATH)

        # Open a new command window and run the server
        subprocess.Popen(f'start cmd /k {PYTHON_ENV} manage.py runserver 0.0.0.0:{DJANGO_PORT}', shell=True)
    
    time.sleep(10)  # Check every 10 seconds