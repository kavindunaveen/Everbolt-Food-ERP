import django.db.models.deletion
from django.db import migrations

def seed_and_migrate_roles(apps, schema_editor):
    Role = apps.get_model('users', 'Role')
    User = apps.get_model('users', 'User')
    Permission = apps.get_model('auth', 'Permission')

    admin_role, _ = Role.objects.get_or_create(
        name='Administrator',
        defaults={'description': 'Full system access', 'is_system': True}
    )
    
    sales_role, _ = Role.objects.get_or_create(
        name='Sales Officer',
        defaults={'description': 'Manage sales, quotes, and delivery', 'is_system': True}
    )
    
    user_role, _ = Role.objects.get_or_create(
        name='General User',
        defaults={'description': 'Basic view-only access', 'is_system': True}
    )
    
    # Assign predefined permissions for Sales Officer
    sales_perms = Permission.objects.filter(
        content_type__app_label__in=['crm', 'sales'],
        codename__in=[
            'view_customer', 'add_customer', 'change_customer', 'delete_customer',
            'view_quotation', 'add_quotation', 'change_quotation', 'delete_quotation',
            'view_invoice', 'add_invoice', 'change_invoice', 'delete_invoice',
            'view_deliverynote', 'add_deliverynote', 'change_deliverynote', 'delete_deliverynote',
            'view_return', 'add_return', 'change_return', 'delete_return'
        ]
    )
    sales_role.permissions.set(sales_perms)

    # Assign view-only permissions for Products and Stock Adjustments
    inventory_view_perms = Permission.objects.filter(
        content_type__app_label='inventory',
        codename__in=['view_product', 'view_stockadjustment']
    )
    sales_role.permissions.add(*inventory_view_perms)

    # Migrate existing users
    for user in User.objects.all():
        if user.role == 'ADMIN' or user.is_superuser:
            user.role_fk = admin_role
        elif user.role == 'USER':
            user.role_fk = user_role
        else:
            user.role_fk = sales_role
        user.save()


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0015_role_user_role_fk'),
    ]

    operations = [
        migrations.RunPython(seed_and_migrate_roles, reverse_code=migrations.RunPython.noop),
    ]
