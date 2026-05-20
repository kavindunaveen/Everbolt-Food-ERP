from django.urls import path
from . import views

urlpatterns = [
    path('', views.AnalyticsDashboardView.as_view(), name='analytics_dashboard'),
    path('api/data/', views.DashboardDataAPI.as_view(), name='dashboard_data_api'),
    path('api/confectionery/', views.ConfectioneryAnalyticsAPI.as_view(), name='confectionery_analytics_api'),
    path('api/product-search/', views.ProductSearchAPI.as_view(), name='product_search_api'),
    path('api/product-targets/', views.ProductTargetsAPI.as_view(), name='product_targets_api'),
    path('targets/', views.TargetManagementView.as_view(), name='target_management'),
]
