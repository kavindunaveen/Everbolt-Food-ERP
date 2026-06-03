import os

apps = ['crm', 'sales', 'inventory', 'manufacturing', 'purchases', 'suppliers', 'dashboard', 'contacts', 'website', 'users']

for app in apps:
    views_path = f"{app}/views.py"
    if not os.path.exists(views_path): continue
    
    with open(views_path, 'r') as f:
        content = f.read()
        
    original_content = content
    
    # Replace import
    content = content.replace(
        "from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin",
        "from django.contrib.auth.mixins import LoginRequiredMixin\nfrom users.mixins import ERPPermissionRequiredMixin"
    )
    content = content.replace(
        "from django.contrib.auth.mixins import PermissionRequiredMixin, LoginRequiredMixin",
        "from django.contrib.auth.mixins import LoginRequiredMixin\nfrom users.mixins import ERPPermissionRequiredMixin"
    )
    
    # What if it's imported separately?
    if "from django.contrib.auth.mixins import PermissionRequiredMixin" in content:
        content = content.replace("from django.contrib.auth.mixins import PermissionRequiredMixin", "")
        if "from users.mixins import ERPPermissionRequiredMixin" not in content:
            content = "from users.mixins import ERPPermissionRequiredMixin\n" + content

    # Replace class inheritance
    content = content.replace("PermissionRequiredMixin,", "ERPPermissionRequiredMixin,")
    content = content.replace("PermissionRequiredMixin)", "ERPPermissionRequiredMixin)")
    
    # Also update AdminRequiredMixin to inherit from ERPUserPassesTestMixin
    if "class AdminRequiredMixin(UserPassesTestMixin):" in content:
        if "from users.mixins import ERPUserPassesTestMixin" not in content:
            content = content.replace("class AdminRequiredMixin(UserPassesTestMixin):", "from users.mixins import ERPUserPassesTestMixin\nclass AdminRequiredMixin(ERPUserPassesTestMixin):")
    
    if content != original_content:
        with open(views_path, 'w') as f:
            f.write(content)
        print(f"Refactored {views_path}")
        
print("Refactoring complete.")
