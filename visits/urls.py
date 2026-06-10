from django.urls import path
from . import views

urlpatterns = [
    path('calendar/', views.calendar_view, name='visit_calendar'),
    path('summary/', views.weekly_summary_view, name='visit_summary'),
    
    # AJAX Endpoints
    path('api/plans/', views.get_plans, name='api_get_visit_plans'),
    path('api/plans/save/', views.save_plan, name='api_save_visit_plan'),
    path('api/tasks/save/', views.save_task, name='api_save_visit_task'),
]
