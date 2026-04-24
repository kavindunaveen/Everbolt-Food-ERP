from django.urls import path
from . import views

urlpatterns = [
    path('grn/', views.GRNListView.as_view(), name='grn_list'),
    path('grn/receive-hub/', views.grn_receive_hub, name='grn_receive_hub'),
    path('grn/receive/<int:po_id>/', views.grn_receive_po, name='grn_receive_po'),
    path('grn/<int:pk>/', views.GRNDetailView.as_view(), name='grn_detail'),
    path('grn/<int:pk>/confirm/', views.confirm_grn_view, name='grn_confirm'),
    path('grn/<int:pk>/cancel/', views.cancel_grn_view, name='grn_cancel'),

    # Purchase Order System
    path('', views.purchase_order_create, name='po_hub'),
    path('pos/', views.PurchaseOrderListView.as_view(), name='po_list'),
    path('pos/new/', views.purchase_order_create, name='po_create_default'),
    path('pos/new/<str:po_type>/', views.purchase_order_create, name='po_create'),
    path('pos/<int:pk>/edit/', views.purchase_order_edit, name='po_edit'),
    path('pos/<int:pk>/', views.PurchaseOrderDetailView.as_view(), name='po_detail'),
    path('pos/<int:pk>/print/', views.PurchaseOrderPrintView.as_view(), name='po_print'),
    path('pos/<int:pk>/confirm/', views.purchase_order_confirm, name='po_confirm'),
    path('pos/<int:pk>/cancel/', views.purchase_order_cancel, name='po_cancel'),
]
