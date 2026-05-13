from django.db import migrations


def backfill_supplier_fk(apps, schema_editor):
    """
    For every existing GRN that has a text supplier name,
    try to find the matching Supplier record by name and set supplier_fk.
    GRNs linked to a PurchaseOrder get supplier_fk from the PO's supplier directly
    (most accurate). Otherwise we fall back to name matching.
    """
    GRN = apps.get_model('purchases', 'GRN')
    Supplier = apps.get_model('suppliers', 'Supplier')

    for grn in GRN.objects.all():
        # 1. Best source: PO's supplier (already a FK — guaranteed correct)
        if grn.po_id and grn.po and grn.po.supplier_id:
            grn.supplier_fk_id = grn.po.supplier_id
            grn.save(update_fields=['supplier_fk_id'])
            continue

        # 2. Fallback: case-insensitive name match on the text snapshot
        if grn.supplier:
            try:
                matched = Supplier.objects.get(
                    supplier_name__iexact=grn.supplier.strip()
                )
                grn.supplier_fk_id = matched.pk
                grn.save(update_fields=['supplier_fk_id'])
            except (Supplier.DoesNotExist, Supplier.MultipleObjectsReturned):
                # Leave supplier_fk as NULL if no unique match found
                pass


def reverse_backfill(apps, schema_editor):
    """Nothing to reverse — the text field is still intact."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('purchases', '0005_add_grn_supplier_fk'),
    ]

    operations = [
        migrations.RunPython(backfill_supplier_fk, reverse_backfill),
    ]
