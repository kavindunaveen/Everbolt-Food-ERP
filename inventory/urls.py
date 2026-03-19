from django.urls import path
from . import views

urlpatterns = [
    path('', views.ProductListView.as_view(), name='product_list'),
    path('api/<int:pk>/', views.ProductDetailAPIView.as_view(), name='product_api'),
    path('new/', views.ProductCreateView.as_view(), name='product_create'),
    path('<int:pk>/edit/', views.ProductUpdateView.as_view(), name='product_edit'),
    path('<int:pk>/delete/', views.ProductDeleteView.as_view(), name='product_delete'),
    
    # Stock Adjustments
    path('adjustments/', views.StockAdjustmentListView.as_view(), name='adjustment_list'),
    path('adjustments/new/', views.StockAdjustmentCreateView.as_view(), name='adjustment_create'),
    path('adjustments/<int:pk>/', views.StockAdjustmentDetailView.as_view(), name='adjustment_detail'),
    path('adjustments/<int:pk>/confirm/', views.confirm_adjustment_view, name='adjustment_confirm'),
    path('adjustments/<int:pk>/cancel/', views.cancel_adjustment_view, name='adjustment_cancel'),
    
    # Reports
    path('stock-summary/', views.StockSummaryView.as_view(), name='stock_summary'),
    path('stock-ledger/', views.StockLedgerView.as_view(), name='stock_ledger'),
]
