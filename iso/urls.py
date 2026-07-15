from django.urls import path
from . import views

urlpatterns = [
    path('', views.CriteriaListView.as_view(), name='iso_criteria_list'),
    path('new/', views.CriteriaCreateView.as_view(), name='iso_criteria_create'),
    path('<int:pk>/edit/', views.CriteriaUpdateView.as_view(), name='iso_criteria_update'),
    path('<int:pk>/delete/', views.CriteriaDeleteView.as_view(), name='iso_criteria_delete'),
    path('<int:criteria_id>/plans/', views.DailyPlanListView.as_view(), name='iso_plan_list'),
    path('<int:criteria_id>/plans/new/', views.DailyPlanCreateView.as_view(), name='iso_plan_create'),
    path('plans/<int:plan_id>/', views.DailyPlanDetailView.as_view(), name='iso_plan_detail'),
]
