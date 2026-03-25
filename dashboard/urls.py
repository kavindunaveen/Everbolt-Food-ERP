from django.urls import path
from . import views

urlpatterns = [
    path('', views.AnalyticsDashboardView.as_view(), name='analytics_dashboard'),
    path('api/data/', views.DashboardDataAPI.as_view(), name='dashboard_data_api'),
]
