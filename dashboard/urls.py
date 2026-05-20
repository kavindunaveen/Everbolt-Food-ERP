from django.urls import path
from . import views

urlpatterns = [
    path('', views.AnalyticsDashboardView.as_view(), name='analytics_dashboard'),
    path('api/data/', views.DashboardDataAPI.as_view(), name='dashboard_data_api'),
    path('api/confectionery/', views.ConfectioneryAnalyticsAPI.as_view(), name='confectionery_analytics_api'),
]
