from sales.models import CreditNote
from users.models import User
from sales.services import approve_credit_note
import traceback

try:
    cn = CreditNote.objects.get(pk=18)
    user = User.objects.filter(is_superuser=True).first()
    print("Approving credit note:", cn)
    approve_credit_note(cn, user)
    print("Success!")
except Exception as e:
    print("Error:")
    traceback.print_exc()
