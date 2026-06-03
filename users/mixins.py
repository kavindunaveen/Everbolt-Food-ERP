from django.contrib.auth.mixins import PermissionRequiredMixin
from django.shortcuts import redirect
from django.contrib import messages

class ERPPermissionRequiredMixin(PermissionRequiredMixin):
    """
    A custom PermissionRequiredMixin that catches permission denials
    and redirects the user back to the dashboard (or referring page)
    with a friendly toast notification instead of a hard 403 error page.
    """
    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            # The user is logged in but doesn't have permission.
            messages.error(self.request, "Access Denied: You do not have permission to view or perform this action.")
            
            # Try to redirect to the referring page, unless they came from nowhere
            referer = self.request.META.get('HTTP_REFERER')
            if referer and referer != self.request.build_absolute_uri() and not referer.endswith('/login/'):
                return redirect(referer)
            
            return redirect('main_dashboard')
            
        return super().handle_no_permission()

from django.contrib.auth.mixins import UserPassesTestMixin

class ERPUserPassesTestMixin(UserPassesTestMixin):
    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            messages.error(self.request, "Access Denied: Administrator privileges are required.")
            referer = self.request.META.get('HTTP_REFERER')
            if referer and referer != self.request.build_absolute_uri() and not referer.endswith('/login/'):
                return redirect(referer)
            return redirect('main_dashboard')
        return super().handle_no_permission()
