from django.urls import path
from . import views

urlpatterns = [
    path('', views.UserListView.as_view(), name='user_list'),
    path('profile/', views.ProfileUpdateView.as_view(), name='user_profile'),
    path('new/', views.UserCreateView.as_view(), name='user_create'),
    path('<int:pk>/edit/', views.UserUpdateView.as_view(), name='user_edit'),
    path('<int:pk>/delete/', views.UserDeleteView.as_view(), name='user_delete'),
    
    path('roles/', views.RoleListView.as_view(), name='role_list'),
    path('roles/new/', views.RoleCreateView.as_view(), name='role_create'),
    path('roles/<int:pk>/edit/', views.RoleUpdateView.as_view(), name='role_edit'),
    path('roles/<int:pk>/delete/', views.RoleDeleteView.as_view(), name='role_delete'),
    
    path('notification/<int:pk>/read/', views.notification_read, name='notification_read'),
    path('notification/mark-all-read/', views.mark_all_notifications_read, name='mark_all_notifications_read'),
    path('action-center/', views.action_center, name='action_center'),
    path('filter/save/', views.SaveFilterView.as_view(), name='save_filter'),
    path('filter/<int:pk>/delete/', views.DeleteFilterView.as_view(), name='delete_filter'),
]
