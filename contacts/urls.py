from django.urls import path
from .views import ContactsDashboardView

urlpatterns = [
    path('', ContactsDashboardView.as_view(), name='contacts_dashboard'),
]
