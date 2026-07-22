"""
Management command: fix_due_dates

Safe two-step command to recalculate all invoice due_dates using the
PaymentTermRule database table.

Usage:
    # Step 1 — Preview only (ZERO database writes):
    python3 manage.py fix_due_dates

    # Step 2 — Apply changes (only after reviewing preview):
    python3 manage.py fix_due_dates --confirm
"""
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone

from sales.models import Invoice
from dashboard.models import PaymentTermRule


def get_correct_due_date(inv, rules_map):
    """
    Calculate the correct due_date for an invoice using the rules_map.
    Always calculated from the invoice creation_date (= issued date).
    Never changes any other field.
    """
    creation_date = inv.creation_date.date()

    if inv.invoice_type == 'CASH':
        term_code = 'CASH'
    elif inv.invoice_type == 'COD':
        term_code = 'COD'
    elif inv.invoice_type == 'CREDIT':
        term_code = inv.customer.payment_terms if inv.customer_id else 'CASH'
    else:
        term_code = 'CASH'

    due_days = rules_map.get(term_code, 0)
    return creation_date + timedelta(days=due_days)


class Command(BaseCommand):
    help = (
        'Recalculates due_date for all invoices using PaymentTermRule table. '
        'Run without --confirm for a safe dry-run preview.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Actually apply the changes. Without this flag, only a preview is shown.',
        )

    def handle(self, *args, **options):
        confirm = options['confirm']

        # Load all term rules into a map for fast lookup
        rules_map = {r.term_code: r.due_days for r in PaymentTermRule.objects.all()}

        if not rules_map:
            self.stderr.write(self.style.ERROR(
                'ERROR: PaymentTermRule table is empty! Run migrations first.\n'
                'Run: python3 manage.py migrate'
            ))
            return

        self.stdout.write('\n' + '=' * 70)
        if confirm:
            self.stdout.write(self.style.WARNING('=== DUE DATE FIX — APPLYING CHANGES ==='))
        else:
            self.stdout.write(self.style.SUCCESS('=== DUE DATE FIX — DRY RUN PREVIEW (no changes will be made) ==='))
        self.stdout.write('=' * 70)
        self.stdout.write(f'\nLoaded {len(rules_map)} payment term rules:')
        for code, days in sorted(rules_map.items()):
            self.stdout.write(f'  {code:15s} → {days} days')
        self.stdout.write('\n')

        invoices = (
            Invoice.objects
            .select_related('customer')
            .order_by('creation_date', 'invoice_number')
        )

        total = invoices.count()
        will_change = []
        already_correct = []
        no_change_needed = []

        for inv in invoices:
            correct_due = get_correct_due_date(inv, rules_map)
            current_due = inv.due_date

            if current_due == correct_due:
                already_correct.append(inv)
            else:
                will_change.append((inv, current_due, correct_due))

        # Print invoices that will change
        if will_change:
            self.stdout.write(self.style.WARNING(f'Invoices that will be updated ({len(will_change)}):'))
            self.stdout.write('-' * 70)
            header = f"{'Invoice':<25} {'Type':<8} {'CustTerms':<12} {'Current Due':<14} {'New Due':<14} {'Change'}"
            self.stdout.write(header)
            self.stdout.write('-' * 70)
            for inv, current_due, correct_due in will_change:
                change_days = (correct_due - inv.creation_date.date()).days
                current_str = str(current_due) if current_due else 'NULL'
                self.stdout.write(
                    f"{inv.invoice_number:<25} {inv.invoice_type:<8} "
                    f"{inv.customer.payment_terms:<12} {current_str:<14} "
                    f"{str(correct_due):<14} (+{change_days}d from creation)"
                )
        else:
            self.stdout.write(self.style.SUCCESS('✓ All invoices already have correct due dates!'))

        self.stdout.write('')
        self.stdout.write(f'Already correct:  {len(already_correct)} invoices')
        self.stdout.write(f'Will be updated:  {len(will_change)} invoices')
        self.stdout.write(f'Total:            {total} invoices')

        if not confirm:
            self.stdout.write('\n' + '=' * 70)
            self.stdout.write(self.style.WARNING(
                '[DRY RUN] No changes were made.\n'
                'Review the list above carefully.\n'
                'When ready, run with --confirm to apply:\n'
                '  python3 manage.py fix_due_dates --confirm'
            ))
            self.stdout.write('=' * 70 + '\n')
            return

        # Apply changes
        if not will_change:
            self.stdout.write(self.style.SUCCESS('\nNothing to update. All done!'))
            return

        self.stdout.write(self.style.WARNING(f'\nApplying {len(will_change)} updates...'))
        updated = 0
        errors = 0
        for inv, current_due, correct_due in will_change:
            try:
                # Use queryset update() to bypass Invoice.save() entirely
                # This ensures ONLY due_date is written — nothing else
                Invoice.objects.filter(pk=inv.pk).update(due_date=correct_due)
                updated += 1
            except Exception as e:
                self.stderr.write(self.style.ERROR(f'  ERROR on {inv.invoice_number}: {e}'))
                errors += 1

        self.stdout.write('\n' + '=' * 70)
        if errors == 0:
            self.stdout.write(self.style.SUCCESS(
                f'✓ COMPLETE: {updated} invoices updated successfully. {errors} errors.'
            ))
        else:
            self.stdout.write(self.style.ERROR(
                f'DONE WITH ERRORS: {updated} updated, {errors} failed. Check logs above.'
            ))
        self.stdout.write('=' * 70 + '\n')
