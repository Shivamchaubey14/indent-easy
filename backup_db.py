import os
import datetime
import subprocess

# Configuration
db_name = "shwetdhara_db"
db_user = "root"
db_password = "root@123"
backup_dir = "/path/to/backup/directory"

def backup_database():
    # Get the current date
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    
    # Create a folder with the current date
    folder_path = os.path.join(backup_dir, today)
    os.makedirs(folder_path, exist_ok=True)
    
    # Backup file name
    backup_file = os.path.join(folder_path, f"{db_name}_backup.sql")
    
    # Command to backup database
    command = [
        "mysqldump",
        f"--user={db_user}",
        f"--password={db_password}",
        db_name,
        f"--result-file={backup_file}"
    ]
    
    # Run the command
    try:
        subprocess.run(command, check=True)
        print(f"Backup completed successfully. File saved at {backup_file}")
    except subprocess.CalledProcessError as e:
        print(f"Error during backup: {e}")

if __name__ == "__main__":
    backup_database()
