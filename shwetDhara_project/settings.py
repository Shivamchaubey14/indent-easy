import os
from pathlib import Path
import time
from decouple import Config, RepositoryEnv
from datetime import timedelta

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent
config = Config(RepositoryEnv(BASE_DIR / '.env'))

# Force read token directly from .env file (bypass decouple cache)
def read_env_direct(key):
    env_path = BASE_DIR / '.env'
    with open(env_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line.startswith(f'{key}='):
                return line.split('=', 1)[1].strip()
    return ''

WHATSAPP_TOKEN_DIRECT = read_env_direct('WHATSAPP_ACCESS_TOKEN')
print(f"DIRECT READ TOKEN: {WHATSAPP_TOKEN_DIRECT[:25]}...")

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret! (loaded from .env)
SECRET_KEY = config('SECRET_KEY', default='django-insecure-dev-only-change-me')

# SECURITY WARNING: don't run with debug turned on in production!
API_KEY = config('API_KEY')
DEBUG = True
ALLOWED_HOSTS = [
    '192.168.71.99',
    '139.167.46.118',
    '192.168.71.176',
    '127.0.0.1',
    'localhost',
    '0.0.0.0',
    '.ngrok-free.app',
    '147040803788.ngrok-free.app',  # Add this specific one
    '9b2f357e2c51.ngrok-free.app',
    '9216b22ec6fb.ngrok-free.app',
    '27edd4615b02.ngrok-free.app',
    '9908-49-43-115-187.ngrok-free.app',
    'e26d-2401-4900-8620-43ab-9537-3991-9846-eba5.ngrok-free.app',
    '9243-49-43-115-187.ngrok-free.app',
    'c09b-139-167-46-118.ngrok-free.app',
    '8708-49-43-115-187.ngrok-free.app',
    '1a08-139-167-46-118.ngrok-free.app',
    '3214-49-43-115-187.ngrok-free.app',
    '6aca-139-167-46-118.ngrok-free.app',
    'fed1-139-167-46-118.ngrok-free.app',
    'd73e-49-43-115-187.ngrok-free.app',
    'b25c-139-167-46-118.ngrok-free.app',
    'a024-49-43-115-187.ngrok-free.app',
    'lcd-season-christmas-birth.trycloudflare.com',
    'bull-dresses-telephone-irc.trycloudflare.com',
    '77c0-139-167-46-118.ngrok-free.app', 
    'diary-flattery-hurray.ngrok-free.dev',
    '1a29-49-43-115-187.ngrok-free.app', 
    'twiddle-aversion-basically.ngrok-free.dev',
    '02b2-139-167-46-118.ngrok-free.app',
    'f55d-49-43-115-214.ngrok-free.app',
    '7935-139-167-46-118.ngrok-free.app',
    '6287-139-167-46-118.ngrok-free.app',
    'f147-49-43-115-214.ngrok-free.app', 
    '3f39-139-167-46-118.ngrok-free.app',
    'twiddle-aversion-basically.ngrok-free.dev',
    'translate-porridge-comic.ngrok-free.dev'
]
# CSRF_TRUSTED_ORIGINS = [
#     'http://139.167.46.118:1445',
#     'https://*.ngrok-free.app',  # Wildcard for all ngrok URLs
#     'http://*.ngrok-free.app',
#     'https://*.ngrok-free.app',
#     'http://127.0.0.1:8000',
#     'http://localhost:8000',
#     'https://fed1-139-167-46-118.ngrok-free.app/',
# ]

ALLOWED_ORIGINS = ['http://139.167.46.118:1445', 'https://*', 'https://56b6db09c783.ngrok-free.app', 'https://8a6f594ace93.ngrok-free.app', 'https://147040803788.ngrok-free.app', 'https://9b72491672b1.ngrok-free.app', 'https://465a4b025ca5.ngrok-free.app', 'https://0fd1d0ee2407.ngrok-free.app', 'https://9b2f357e2c51.ngrok-free.app', 'https://9216b22ec6fb.ngrok-free.app','https://27edd4615b02.ngrok-free.app', 'https://9908-49-43-115-187.ngrok-free.app', 'https://e26d-2401-4900-8620-43ab-9537-3991-9846-eba5.ngrok-free.app', 'https://9243-49-43-115-187.ngrok-free.app', 'https://c09b-139-167-46-118.ngrok-free.app', 'https://8708-49-43-115-187.ngrok-free.app', 'https://1a08-139-167-46-118.ngrok-free.app', 'https://3214-49-43-115-187.ngrok-free.app', 'https://6aca-139-167-46-118.ngrok-free.app', 'https://fed1-139-167-46-118.ngrok-free.app', 'https://d73e-49-43-115-187.ngrok-free.app', 'https://b25c-139-167-46-118.ngrok-free.app', 'https://a024-49-43-115-187.ngrok-free.app', 'https://lcd-season-christmas-birth.trycloudflare.com', 'https://bull-dresses-telephone-irc.trycloudflare.com', 'https://77c0-139-167-46-118.ngrok-free.app', 'https://diary-flattery-hurray.ngrok-free.dev', 'https://1a29-49-43-115-187.ngrok-free.app', 'https://twiddle-aversion-basically.ngrok-free.dev','https://02b2-139-167-46-118.ngrok-free.app', 'https://f55d-49-43-115-214.ngrok-free.app', 'https://7935-139-167-46-118.ngrok-free.app', 'https://6287-139-167-46-118.ngrok-free.app', 'https://f147-49-43-115-214.ngrok-free.app', 'https://3f39-139-167-46-118.ngrok-free.app', 'https://twiddle-aversion-basically.ngrok-free.dev', 'https://translate-porridge-comic.ngrok-free.dev']  
CSRF_TRUSTED_ORIGINS = ALLOWED_ORIGINS.copy()
                                      


# WhatsApp Business API Configuration
WHATSAPP_ACCESS_TOKEN = config('WHATSAPP_ACCESS_TOKEN', default='')
WHATSAPP_PHONE_NUMBER_ID = config('WHATSAPP_PHONE_NUMBER_ID', default='')

# Optional Webhook settings (for delivery receipts)
WHATSAPP_WEBHOOK_VERIFY_TOKEN = config('WHATSAPP_WEBHOOK_VERIFY_TOKEN', default='your_verify_token')
WHATSAPP_WEBHOOK_SECRET = config('WHATSAPP_WEBHOOK_SECRET', default='your_webhook_secret')

# Application definition
INSTALLED_APPS = [
    'main_app',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_celery_results',
    'django_extensions',
]

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',  # Default backend
    'main_app.auth_backend.EmailBackend',   # Custom backend
]

AUTH_USER_MODEL = 'main_app.CustomUser'

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # Prevents duplicate record creation on retried POSTs carrying an
    # X-Idempotency-Key header. No-op for requests without that header.
    'main_app.idempotency_middleware.IdempotencyMiddleware',
    # Auto-creates this/next month's cycles and keeps today's cycle active
    # (hourly check piggybacked on requests — no scheduler needed).
    'main_app.cycle_auto.CycleAutoMiddleware',
]

ROOT_URLCONF = 'shwetDhara_project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS':  [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'shwetDhara_project.wsgi.application'

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': config('DATABASE_NAME'),
        'USER': config('DATABASE_USER'),
        'PASSWORD': config('DATABASE_PASSWORD'),
        'HOST': config('DATABASE_HOST', default='localhost'),
        'PORT': config('DATABASE_PORT', default='5432'),
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_TZ = False
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'default'

# Enhanced logging configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {funcName} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
            'stream': 'ext://sys.stdout',
        },
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'debug.log'),
            'formatter': 'verbose',
            'encoding': 'utf-8',
        },
        'whatsapp_file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'whatsapp_debug.log'),
            'formatter': 'verbose',
            'encoding': 'utf-8',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'main_app': {
            'handlers': ['console', 'file', 'whatsapp_file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# Celery Configuration
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Asia/Kolkata'
CELERY_WORKER_CONCURRENCY = 1
CELERY_WORKER_HIJACK_ROOT_LOGGER = False
CELERY_WORKER_POOL = 'solo'
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_SOFT_TIME_LIMIT = 45
CELERY_TASK_TIME_LIMIT = 60
CELERY_TASK_MAX_RETRIES = 3
CELERY_TASK_RETRY_DELAY = 30
CELERY_TASK_REJECT_ON_WORKER_LOST = True

# Task Routing
# In settings.py, update CELERY_TASK_ROUTES:
CELERY_TASK_ROUTES = {
    'main_app.tasks_sequential.queue_advance_sale_messages': {
        'queue': 'message_queue'
    },
    'main_app.tasks_sequential.process_message_queue': {
        'queue': 'message_queue'
    },
    'main_app.tasks_sequential.recover_stale_messages': {
        'queue': 'message_queue'
    },
    'main_app.tasks_sequential.restart_message_processing': {
        'queue': 'message_queue'
    },
    'main_app.tasks_sequential.check_and_process_messages': {
        'queue': 'message_queue'
    },
    'main_app.tasks_sequential.clean_old_messages': {
        'queue': 'celery'
    },
}

# Celery Beat Schedule
CELERY_BEAT_SCHEDULE = {
    'recover-stale-messages': {
        'task': 'main_app.tasks_sequential.recover_stale_messages',
        'schedule': timedelta(minutes=5),
    },
    'clean-old-messages': {
        'task': 'main_app.tasks_sequential.clean_old_messages', 
        'schedule': timedelta(hours=24),
    },
    'restart-message-processing': {
        'task': 'main_app.tasks_sequential.restart_message_processing',
        'schedule': timedelta(minutes=1),
    },
    'check-and-process-messages': {
        'task': 'main_app.tasks_sequential.check_and_process_messages',
        'schedule': timedelta(seconds=30),
    },
}

# Cache configuration
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://localhost:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'MAX_ENTRIES': 1000,
        }
    }
}

# Static files
STATIC_URL = '/static/'
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),
]
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Email Settings
# EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
# EMAIL_HOST = "smtp.gmail.com"
# EMAIL_PORT = 587
# EMAIL_USE_TLS = True
# EMAIL_HOST_USER = "shivamc36@gmail.com"
# EMAIL_HOST_PASSWORD = "<app-password-in-.env>"
# DEFAULT_FROM_EMAIL = "shivamc36@gmail.com"
# ADMIN_EMAIL = "shivamc36@gmail.com"

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.gmail.com"  # Replace with your SMTP host
EMAIL_PORT = 587  # Replace with your SMTP port
EMAIL_USE_TLS = True
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='indent@shwetdharamilk.com')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')  # Gmail app password (from .env)
DEFAULT_FROM_EMAIL = config('EMAIL_HOST_USER', default='indent@shwetdharamilk.com')
ADMIN_EMAIL = "indent@shwetdharamilk.com"  # Replace with the admin's email

# Login/Logout URLs
LOGIN_URL = 'login'
LOGOUT_REDIRECT_URL = '/'

# Background Worker Settings
MESSAGE_RETRY_ATTEMPTS = 3
MESSAGE_RETRY_DELAY = 2

# Redis Configuration
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
REDIS_DB = 0
REDIS_URL = 'redis://localhost:6379/1'  # Use DB 1 for locks

# WhatsApp Business API Configuration
print(f"DEBUG TOKEN FROM ENV: {config('WHATSAPP_ACCESS_TOKEN', default='MISSING')[:25]}...")
WHATSAPP_BUSINESS_API = {
    'ACCESS_TOKEN': WHATSAPP_TOKEN_DIRECT,
    'PHONE_NUMBER_ID': config('WHATSAPP_PHONE_NUMBER_ID', default=''),
    'WABA_ID': config('WABA_ID', default=''),
    'API_VERSION': 'v22.0',
    'BASE_URL': 'https://graph.facebook.com',
    'TEMPLATE_NAME': 'shwetdhara_remainder_template',  # Updated to your working template
    'TEMPLATE_LANGUAGE': 'hi',
    'MAX_RETRIES': 3,
    'RETRY_DELAY': 2,
}

TRANSACTION_TIMEOUT = 30  # seconds
MAX_CONCURRENT_TRANSACTIONS = 10

# WhatsApp Settings
# WHATSAPP_SETTINGS = {
#     'USE_WINDOWS_APP': True,
#     'USE_WEB_FALLBACK': True,
#     'AUTO_SEND': True,
#     'RATE_LIMIT_SECONDS': 5,
# }

# # WhatsApp Auto Settings
# WHATSAPP_AUTO = {
#     'ENABLED': True,
#     'USE_WINDOWS_APP': True,
#     'AUTO_SEND': True,
#     'DELAY_BETWEEN_MESSAGES': 5,
#     'MAX_RETRIES': 3,
# }

# Message Service Settings
WHATSAPP_ENABLED = True
SMS_ENABLED = True

# Inventory Settings
INVENTORY_LOCK_TIMEOUT = 30

# Create log files if they don't exist
for log_file in ['debug.log', 'whatsapp_debug.log']:
    log_path = os.path.join(BASE_DIR, log_file)
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    if not os.path.exists(log_path):
        with open(log_path, 'w') as f:
            f.write(f"Log created at {time.strftime('%Y-%m-%d %H:%M:%S')}\n")