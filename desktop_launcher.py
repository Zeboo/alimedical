
import webview

# Replace with your actual Railway app URL
RAILWAY_URL = "https://alimedical-production.up.railway.app/"

webview.create_window('Hospital POS (Online)', RAILWAY_URL, width=1200, height=800)
webview.start()
