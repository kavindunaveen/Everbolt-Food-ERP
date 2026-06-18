class HostRoutingMiddleware:
    """
    Routes requests to the public website URLs if the host is 'organicfoodslanka.com'.
    Otherwise, defaults to the ERP URLs (ROOT_URLCONF).
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        host = request.get_host().split(':')[0].lower()
        
        public_domains = [
            'organicfoodslanka.com', 
            'www.organicfoodslanka.com',
            'website.local' # For local testing via /etc/hosts
        ]
        
        if host in public_domains:
            request.urlconf = 'website.public_urls'
            
        return self.get_response(request)
