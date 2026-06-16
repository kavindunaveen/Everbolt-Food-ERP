from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required, permission_required
from .models import VisitPlan, VisitTask
from users.models import User
import json
import calendar
from datetime import datetime, date, timedelta

@login_required
@permission_required('visits.view_visitplan', raise_exception=True)
def calendar_view(request):
    sales_officers = User.objects.filter(is_active=True, role__name='Sales Officer')
    return render(request, 'visits/calendar.html', {'sales_officers': sales_officers})

@login_required
@permission_required('visits.view_weekly_summary', raise_exception=True)
def weekly_summary_view(request):
    # Determine the week. By default, show the current week (Sunday to Saturday)
    today = date.today()
    # In Python, weekday() is 0 for Monday and 6 for Sunday.
    # If we want Sunday to Saturday:
    # 0=Mon, 1=Tue, ..., 5=Sat, 6=Sun
    if today.weekday() == 6: # Sunday
        start_date = today
    else:
        start_date = today - timedelta(days=today.weekday() + 1)
        
    start_date_str = request.GET.get('start_date')
    if start_date_str:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        
    end_date = start_date + timedelta(days=6)
    
    plans = VisitPlan.objects.filter(date__gte=start_date, date__lte=end_date).select_related('sales_officer', 'task').order_by('sales_officer__first_name', 'date')
    
    # Group by sales officer
    summary = {}
    for plan in plans:
        officer = plan.sales_officer
        if officer not in summary:
            summary[officer] = []
        summary[officer].append(plan)
        
    prev_week = start_date - timedelta(days=7)
    next_week = start_date + timedelta(days=7)

    return render(request, 'visits/summary.html', {
        'summary': summary,
        'start_date': start_date,
        'end_date': end_date,
        'prev_week': prev_week.strftime('%Y-%m-%d'),
        'next_week': next_week.strftime('%Y-%m-%d'),
    })

@login_required
def get_plans(request):
    year = int(request.GET.get('year', datetime.now().year))
    month = int(request.GET.get('month', datetime.now().month))
    
    plans = VisitPlan.objects.filter(date__year=year, date__month=month).select_related('sales_officer', 'task')
    data = []
    for plan in plans:
        data.append({
            'id': plan.id,
            'date': plan.date.isoformat(),
            'sales_officer_id': plan.sales_officer.id,
            'sales_officer_name': plan.sales_officer.get_full_name() or plan.sales_officer.username,
            'description': plan.description,
            'task_id': plan.task.id if hasattr(plan, 'task') else None,
            'tasks_done': plan.task.tasks_done if hasattr(plan, 'task') else "",
            'remarks': plan.task.remarks if hasattr(plan, 'task') else "",
            'is_done': plan.task.is_done if hasattr(plan, 'task') else False,
        })
    return JsonResponse({'status': 'success', 'data': data})

@login_required
@permission_required('visits.add_visitplan', raise_exception=True)
def save_plan(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            plan_id = data.get('plan_id')
            date_str = data.get('date')
            sales_officer_id = data.get('sales_officer_id')
            description = data.get('description')
            
            if plan_id:
                try:
                    plan = VisitPlan.objects.get(id=plan_id)
                    plan.description = description
                    plan.save()
                except VisitPlan.DoesNotExist:
                    return JsonResponse({'status': 'error', 'message': 'Plan not found'}, status=404)
            else:
                plan = VisitPlan.objects.create(
                    date=date_str,
                    sales_officer_id=sales_officer_id,
                    description=description,
                    created_by=request.user
                )
                
            return JsonResponse({'status': 'success', 'plan_id': plan.id})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error'}, status=400)

@login_required
@permission_required('visits.delete_visitplan', raise_exception=True)
def delete_plan(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            plan_id = data.get('plan_id')
            try:
                plan = VisitPlan.objects.get(id=plan_id)
                plan.delete()
                return JsonResponse({'status': 'success'})
            except VisitPlan.DoesNotExist:
                return JsonResponse({'status': 'error', 'message': 'Plan not found'}, status=404)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error'}, status=400)

@login_required
def save_task(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            plan_id = data.get('plan_id')
            tasks_done = data.get('tasks_done')
            remarks = data.get('remarks')
            is_done = data.get('is_done', False)
            
            try:
                plan = VisitPlan.objects.get(id=plan_id)
            except VisitPlan.DoesNotExist:
                return JsonResponse({'status': 'error', 'message': 'Plan not found'}, status=404)
            
            # Security: only the assigned sales officer or an admin can update the task
            if not request.user.is_admin() and plan.sales_officer != request.user:
                return JsonResponse({'status': 'error', 'message': 'Permission denied'}, status=403)
                
            task, created = VisitTask.objects.update_or_create(
                plan=plan,
                defaults={
                    'tasks_done': tasks_done,
                    'remarks': remarks,
                    'is_done': is_done
                }
            )
            return JsonResponse({'status': 'success', 'task_id': task.id})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error'}, status=400)
