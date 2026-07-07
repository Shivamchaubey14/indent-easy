# celery.py
import os
from celery import Celery
import socket

# Set the default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'shwetDhara_project.settings')

app = Celery('shwetDhara_project')

# Get hostname for unique worker naming
hostname = socket.gethostname()

# Using configuration from Django settings
app.config_from_object('django.conf:settings', namespace='CELERY')

# Set unique node name
app.conf.worker_hostname = f"{hostname}-{os.getpid()}"

# Autodiscover tasks
app.autodiscover_tasks()