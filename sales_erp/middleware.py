from django.db.models import ProtectedError
from django.contrib import messages
from django.shortcuts import redirect

class ProtectedErrorMiddleware:
    """
    Middleware that catches ProtectedError natively across the entire ERP and 
    displays a user-friendly error message, rather than showing a 500 error page.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        if isinstance(exception, ProtectedError):
            model_name = "item"
            
            # Attempt to intelligently extract the model name from the protected objects
            if len(exception.args) > 1 and exception.args[1]:
                try:
                    # exception.args[1] is typically a set, list or queryset of the protected objects
                    protected_objects = exception.args[1]
                    first_obj = next(iter(protected_objects))
                    model_name = first_obj._meta.verbose_name.title()
                except (AttributeError, IndexError, StopIteration, TypeError):
                    pass
            
            # Show a friendly, generic error
            messages.error(
                request, 
                f"Cannot delete this {model_name} because it is referenced by other historical records "
                "(e.g. Invoices, GRNs, Production data). Please mark it as Inactive instead to preserve system integrity."
            )
            
            # Redirect the user safely back to where they came from
            referer = request.META.get('HTTP_REFERER')
            if referer:
                return redirect(referer)
            
            # Fallback redirect if referer is missing
            return redirect('/')
        return None
