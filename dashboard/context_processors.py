from dashboard.models import CompanySettings

def company_settings(request):
    settings_obj, created = CompanySettings.objects.get_or_create(id=1)
    return {'company_settings': settings_obj}
