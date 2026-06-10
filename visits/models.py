from django.db import models
from django.conf import settings

class VisitPlan(models.Model):
    date = models.DateField(db_index=True)
    sales_officer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='visit_plans')
    description = models.TextField(help_text="Instructions/Plan added by Admin")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_visit_plans')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date']
        permissions = [
            ("view_weekly_summary", "Can view weekly summary report"),
        ]

    def __str__(self):
        return f"{self.sales_officer} - {self.date}"

class VisitTask(models.Model):
    plan = models.OneToOneField(VisitPlan, on_delete=models.CASCADE, related_name='task')
    tasks_done = models.TextField(blank=True, null=True, help_text="Tasks actually completed")
    remarks = models.TextField(blank=True, null=True, help_text="Sales Officer's remarks after visit")
    is_done = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Task for {self.plan}"
