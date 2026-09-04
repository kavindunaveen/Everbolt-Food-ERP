from django.test import Client
from users.models import User

try:
    c = Client(SERVER_NAME='staging.organicfoodslanka.com')
    # Need to login as superuser
    user = User.objects.filter(is_superuser=True).first()
    if user:
        c.force_login(user)
        
    print("Testing /finance/pending-payments/")
    resp = c.get('/finance/pending-payments/')
    print("Status:", resp.status_code)
    if resp.status_code == 500:
        print("ERROR ON /finance/pending-payments/")
    
    print("Testing /finance/pending-payments/?q=26AUG_EBFR_01490")
    resp2 = c.get('/finance/pending-payments/?q=26AUG_EBFR_01490')
    print("Status:", resp2.status_code)
    
    print("Testing /finance/partial-payments/")
    resp3 = c.get('/finance/partial-payments/')
    print("Status:", resp3.status_code)
    
    print("Testing /finance/")
    resp4 = c.get('/finance/')
    print("Status:", resp4.status_code)
    
except Exception as e:
    import traceback
    traceback.print_exc()
