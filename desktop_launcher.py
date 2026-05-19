import subprocess
import threading
import time
import webview
import os

# Start Django server in a background thread
def run_django():
    # Use 127.0.0.1:8000 to avoid firewall popups
    subprocess.Popen([
        'python', 'manage.py', 'runserver', '127.0.0.1:8000',
    ], cwd=os.path.dirname(os.path.abspath(__file__)))

threading.Thread(target=run_django, daemon=True).start()
time.sleep(2)  # Wait for server to start

# Open the desktop window
webview.create_window('Hospital POS', 'http://127.0.0.1:8000/', width=1200, height=800)
webview.start()
