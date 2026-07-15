from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()

class ISOCategory(models.Model):
    name = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "ISO Category"
        verbose_name_plural = "ISO Categories"

    def __str__(self):
        return self.name

class ISOCriteria(models.Model):
    class DurationType(models.TextChoices):
        DAILY = 'DAILY', 'Daily'
        TWO_WEEKS = 'TWO_WEEKS', '2 Weeks'
        CUSTOM = 'CUSTOM', 'Custom'

    name = models.CharField(max_length=255)
    category = models.ForeignKey(ISOCategory, on_delete=models.CASCADE, related_name='criteria')
    duration_type = models.CharField(max_length=20, choices=DurationType.choices, default=DurationType.DAILY)
    custom_duration_days = models.PositiveIntegerField(null=True, blank=True, help_text="Number of days if duration is custom")
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='iso_criteria')

    class Meta:
        verbose_name = "ISO Criteria"
        verbose_name_plural = "ISO Criteria"
        
        # We define explicit permissions for user management to control
        permissions = [
            ("can_manage_iso", "Can manage ISO checklists"),
        ]

    def __str__(self):
        return self.name

class ISODailyPlan(models.Model):
    criteria = models.ForeignKey(ISOCriteria, on_delete=models.CASCADE, related_name='daily_plans')
    date = models.DateField(default=timezone.now)
    submitted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='iso_plans')
    submitted_at = models.DateTimeField(auto_now_add=True)
    is_submitted = models.BooleanField(default=False)

    class Meta:
        verbose_name = "ISO Daily Plan"
        verbose_name_plural = "ISO Daily Plans"
        unique_together = [['criteria', 'date']] # A single plan per criteria per date

    def __str__(self):
        return f"{self.criteria.name} - {self.date}"

class ISODailyTask(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PASS = 'pass', 'Pass'
        FAIL = 'fail', 'Fail'

    plan = models.ForeignKey(ISODailyPlan, on_delete=models.CASCADE, related_name='tasks')
    task_description = models.CharField(max_length=500)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    remark = models.TextField(blank=True)

    class Meta:
        verbose_name = "ISO Daily Task"
        verbose_name_plural = "ISO Daily Tasks"

    def __str__(self):
        return f"{self.plan} - {self.task_description[:30]}"
