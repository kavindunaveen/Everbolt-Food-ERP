from django.urls import path
from . import views

urlpatterns = [
    path('', views.SupplierListView.as_view(), name='supplier_list'),
    path('new/', views.SupplierCreateView.as_view(), name='supplier_create'),
    path('<int:pk>/', views.SupplierDetailView.as_view(), name='supplier_detail'),
    path('<int:pk>/edit/', views.SupplierUpdateView.as_view(), name='supplier_update'),
    path('<int:pk>/delete/', views.SupplierDeleteView.as_view(), name='supplier_delete'),
]
