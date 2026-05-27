from django.urls import path
from . import views

urlpatterns = [
    path('', views.CustomerListView.as_view(), name='customer_list'),
    path('new/', views.CustomerCreateView.as_view(), name='customer_create'),
    path('<int:pk>/', views.CustomerDetailView.as_view(), name='customer_detail'),
    path('<int:pk>/edit/', views.CustomerUpdateView.as_view(), name='customer_edit'),
    path('<int:pk>/delete/', views.CustomerDeleteView.as_view(), name='customer_delete'),
    path('export/', views.CustomerExportView.as_view(), name='customer_export'),
    # Delivery address AJAX endpoints
    path('<int:pk>/delivery-addresses/', views.customer_delivery_addresses, name='customer_delivery_addresses'),
    path('<int:pk>/delivery-addresses/add/', views.add_delivery_address, name='add_delivery_address'),
    path('<int:pk>/delivery-addresses/<int:addr_pk>/set-default/', views.set_default_delivery_address, name='set_default_delivery_address'),
    path('<int:pk>/delivery-addresses/<int:addr_pk>/delete/', views.delete_delivery_address, name='delete_delivery_address'),
]
