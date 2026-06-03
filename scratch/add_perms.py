import os

files_to_update = {
    'manufacturing/views.py': {
        'BOMListView': 'manufacturing.view_bom',
        'BOMCreateView': 'manufacturing.add_bom',
        'BOMDetailView': 'manufacturing.view_bom',
        'BOMUpdateView': 'manufacturing.change_bom',
        'ProductionListView': 'manufacturing.view_production',
        'ProductionCreateView': 'manufacturing.add_production',
        'ProductionUpdateView': 'manufacturing.change_production',
        'ProductionDetailView': 'manufacturing.view_production',
    },
    'purchases/views.py': {
        'GRNListView': 'purchases.view_grn',
        'GRNDetailView': 'purchases.view_grn',
        'PurchaseOrderListView': 'purchases.view_purchaseorder',
        'PurchaseOrderDetailView': 'purchases.view_purchaseorder',
        'PurchaseOrderPrintView': 'purchases.view_purchaseorder',
    }
}

for filepath, classes in files_to_update.items():
    if not os.path.exists(filepath): continue
    with open(filepath, 'r') as f:
        content = f.read()
        
    if "from users.mixins import ERPPermissionRequiredMixin" not in content:
        content = "from users.mixins import ERPPermissionRequiredMixin\n" + content
        
    lines = content.split('\n')
    new_lines = []
    
    for line in lines:
        for class_name, perm in classes.items():
            if line.startswith(f"class {class_name}("):
                if "ERPPermissionRequiredMixin" not in line:
                    line = line.replace("LoginRequiredMixin,", "LoginRequiredMixin, ERPPermissionRequiredMixin,")
        new_lines.append(line)
        
        for class_name, perm in classes.items():
            if line.startswith(f"class {class_name}("):
                # Add permission_required property after class definition
                new_lines.append(f"    permission_required = '{perm}'")
                
    with open(filepath, 'w') as f:
        f.write('\n'.join(new_lines))
        
print("Added permissions to manufacturing and purchases.")
