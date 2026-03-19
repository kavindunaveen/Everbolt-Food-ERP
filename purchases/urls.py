from django.urls import path
from . import views

urlpatterns = [
    path('grn/', views.GRNListView.as_view(), name='grn_list'),
    path('grn/new/', views.GRNCreateView.as_view(), name='grn_create'),
    path('grn/<int:pk>/', views.GRNDetailView.as_view(), name='grn_detail'),
    path('grn/<int:pk>/edit/', views.GRNUpdateView.as_view(), name='grn_update'),
    path('grn/<int:pk>/confirm/', views.confirm_grn_view, name='grn_confirm'),
    path('grn/<int:pk>/cancel/', views.cancel_grn_view, name='grn_cancel'),
]
