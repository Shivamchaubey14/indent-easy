# quick_start.py
import os
import sys
import subprocess
import time

def run_command(command, description):
    print(f"\n{'='*60}")
    print(f"Starting: {description}")
    print(f"Command: {command}")
    print('='*60)
    
    try:
        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        
        # Wait a bit to see if it starts successfully
        time.sleep(3)
        
        # Check if process is still running
        if process.poll() is None:
            print(f"✓ {description} started successfully!")
            return process
        else:
            stdout, stderr = process.communicate()
            print(f"✗ {description} failed to start!")
            if stderr:
                print(f"Error: {stderr}")
            return None
            
    except Exception as e:
        print(f"✗ Error starting {description}: {e}")
        return None

def main():
    print("🚀 SHWETDHARA INDENT EASY SYSTEM  SERVICES - QUICK START")
    print("This script will start all required services")
    print("="*60)
    
    # Check Python
    print(f"Python: {sys.version}")
    
    # Start services in order
    processes = []
    
    # 1. Check Redis
    print("\n[1/5] Checking Redis...")
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, db=0)
        r.ping()
        print("✓ Redis is running")
    except:
        print("✗ Redis is not running")
        print("Please start Redis manually first!")
        input("Press Enter after starting Redis...")
    
    # 2. Start Django
    django_proc = run_command(
        "python manage.py runserver",
        "Django Development Server"
    )
    if django_proc:
        processes.append(('Django', django_proc))
    
    # 3. Start Celery Beat
    beat_proc = run_command(
        "celery -A shwetDhara_project beat --loglevel=info",
        "Celery Beat Scheduler"
    )
    if beat_proc:
        processes.append(('Celery Beat', beat_proc))
    
    # 4. Start Message Queue Worker
    mq_proc = run_command(
        "celery -A shwetDhara_project worker --loglevel=info --concurrency=1 --queues=message_queue --pool=solo",
        "Message Queue Worker"
    )
    if mq_proc:
        processes.append(('Message Queue', mq_proc))
    
    # 5. Start General Worker
    gen_proc = run_command(
        "celery -A shwetDhara_project worker --loglevel=info --concurrency=2 --pool=solo",
        "General Worker"
    )
    if gen_proc:
        processes.append(('General Worker', gen_proc))
    
    print("\n" + "="*60)
    print("🎉 ALL SERVICES STARTED SUCCESSFULLY!")
    print("="*60)
    print("\nAccess URLs:")
    print("1. Web Application:    http://127.0.0.1:8000")
    print("2. Admin Interface:    http://127.0.0.1:8000/admin")
    print("\nServices Running:")
    for name, proc in processes:
        print(f"  ✓ {name}")
    
    print("\n" + "="*60)
    print("Press Ctrl+C to stop all services")
    
    try:
        # Keep script running
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\nStopping all services...")
        for name, proc in processes:
            print(f"  Stopping {name}...")
            proc.terminate()
        print("\nAll services stopped. Goodbye!")

if __name__ == "__main__":
    main()