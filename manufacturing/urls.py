from django.urls import path
from . import views

urlpatterns = [
    # BOM
    path('bom/', views.BOMListView.as_view(), name='bom_list'),
    path('bom/new/', views.BOMCreateView.as_view(), name='bom_create'),
    path('bom/<int:pk>/', views.BOMDetailView.as_view(), name='bom_detail'),
    path('bom/<int:pk>/edit/', views.BOMUpdateView.as_view(), name='bom_edit'),
    
    # Production
    path('production/', views.ProductionListView.as_view(), name='production_list'),
    path('production/new/', views.ProductionCreateView.as_view(), name='production_create'),
    path('production/<int:pk>/', views.ProductionDetailView.as_view(), name='production_detail'),
    path('production/<int:pk>/edit/', views.ProductionUpdateView.as_view(), name='production_edit'),
    path('production/<int:pk>/confirm/', views.confirm_production_view, name='production_confirm'),
    path('production/<int:pk>/cancel/', views.cancel_production_view, name='production_cancel'),
    
    # AJAX
    path('api/bom/<int:bom_id>/', views.get_bom_details, name='api_bom_details'),
]
