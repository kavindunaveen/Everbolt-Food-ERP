from django.http import HttpResponsePermanentRedirect
from django.utils.deprecation import MiddlewareMixin
from .models import SEORedirect

class HostRoutingMiddleware:
    """
    Routes requests to the correct app based on subdomain/host.
    For example: erp.organicfoodslanka.com -> sales_erp.urls
    www.organicfoodslanka.com -> website.public_urls
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        host = request.get_host().split(':')[0].lower()
        
        # ERP Hosts
        erp_hosts = ['erp.organicfoodslanka.com', 'staging.organicfoodslanka.com', '178.128.52.97']
        # Local development hosts
        if 'localhost' in host or '127.0.0.1' in host:
            # We'll default local to ERP for dashboard development,
            # unless a specific public port/subdomain is used.
            # But let's allow accessing the public site via 127.0.0.1:8000/public or similar if needed.
            request.urlconf = 'sales_erp.urls'
        elif any(h in host for h in erp_hosts):
            request.urlconf = 'sales_erp.urls'
        else:
            # Main website (organicfoodslanka.com, www.organicfoodslanka.com, etc)
            request.urlconf = 'website.public_urls'
            
        return self.get_response(request)

class WebsiteRedirectMiddleware(MiddlewareMixin):
    """
    Catches 404 responses and checks the SEORedirect model.
    If a matching old_path is found, returns a 301 Permanent Redirect.
    """
    def process_response(self, request, response):
        # Only process if it's a 404 Not Found
        if response.status_code == 404:
            path = request.path
            
            # Check if there is an active SEO Redirect for this exact path
            # Some old URLs might have trailing slashes, some might not. We can check exactly.
            redirect_obj = SEORedirect.objects.filter(old_path=path, is_active=True).first()
            
            if not redirect_obj and path.endswith('/'):
                # Try without trailing slash
                redirect_obj = SEORedirect.objects.filter(old_path=path.rstrip('/'), is_active=True).first()
            elif not redirect_obj and not path.endswith('/'):
                # Try with trailing slash
                redirect_obj = SEORedirect.objects.filter(old_path=path + '/', is_active=True).first()

            if redirect_obj:
                # Return 301 Permanent Redirect
                return HttpResponsePermanentRedirect(redirect_obj.new_path)
                
        return response
