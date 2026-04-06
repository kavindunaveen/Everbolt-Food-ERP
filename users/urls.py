from django.urls import path
from . import views

urlpatterns = [
    path('', views.UserListView.as_view(), name='user_list'),
    path('new/', views.UserCreateView.as_view(), name='user_create'),
    path('<int:pk>/edit/', views.UserUpdateView.as_view(), name='user_edit'),
    path('<int:pk>/delete/', views.UserDeleteView.as_view(), name='user_delete'),
    path('notification/<int:pk>/read/', views.notification_read, name='notification_read'),
]
