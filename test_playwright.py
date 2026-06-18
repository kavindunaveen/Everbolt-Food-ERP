import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sales_erp.settings")
django.setup()
from django.test import Client
from users.models import User
import threading
from django.core.servers.basehttp import get_internal_wsgi_application
from werkzeug.serving import make_server
import time

admin = User.objects.get(username='admin')
client = Client()
client.force_login(admin)

app = get_internal_wsgi_application()
server = make_server('127.0.0.1', 8081, app)
t = threading.Thread(target=server.serve_forever)
t.daemon = True
t.start()

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    context = browser.new_context()
    
    # login via setting cookie
    session = client.session
    context.add_cookies([{
        'name': 'sessionid',
        'value': session.session_key,
        'domain': '127.0.0.1',
        'path': '/'
    }])
    
    page = context.new_page()
    
    errors = []
    page.on("pageerror", lambda err: errors.append(err))
    page.on("console", lambda msg: print(f"CONSOLE {msg.type}: {msg.text}") if msg.type == 'error' else None)
    
    page.goto('http://127.0.0.1:8081/dashboard/salesperson/')
    page.wait_for_timeout(2000)
    
    print("JS Errors:", errors)
    print("HTML Last Updated Text:", page.locator("#lastUpdated").inner_text())
    
    browser.close()
    server.shutdown()
