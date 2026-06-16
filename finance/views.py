import json
from datetime import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Sum, Q, F
from django.db import transaction

from sales.models import Invoice
from .models import Payment

class FinanceDashboardView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'finance.manage_finance'
    template_name = 'finance/dashboard.html'

    def get(self, request):
        today = timezone.now().date()
        
        # We consider overdue: ISSUED status, not CASH/COD, due_date < today
        overdue_invoices = Invoice.objects.filter(
            status=Invoice.Status.ISSUED,
            due_date__lt=today
        ).exclude(invoice_type__in=['CASH', 'COD'])
        
        overdue_count = overdue_invoices.count()
        overdue_total = sum(inv.total_amount for inv in overdue_invoices)
        
        context = {
            'overdue_count': overdue_count,
            'overdue_total': overdue_total,
        }
        return render(request, self.template_name, context)

class OverdueInvoicesView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'finance.manage_finance'
    template_name = 'finance/overdue_invoices.html'

    def get(self, request):
        today = timezone.now().date()
        
        overdue_qs = Invoice.objects.filter(
            status=Invoice.Status.ISSUED,
            due_date__lt=today
        ).exclude(invoice_type__in=['CASH', 'COD']).order_by('due_date', '-total_amount')
        
        # Filtering logic
        date_from = request.GET.get('date_from')
        if date_from:
            overdue_qs = overdue_qs.filter(due_date__gte=date_from)
            
        date_to = request.GET.get('date_to')
        if date_to:
            overdue_qs = overdue_qs.filter(due_date__lte=date_to)
            
        month = request.GET.get('month')
        if month:
            try:
                year_str, month_str = month.split('-')
                overdue_qs = overdue_qs.filter(due_date__year=int(year_str), due_date__month=int(month_str))
            except ValueError:
                pass
            
        q = request.GET.get('q')
        if q:
            overdue_qs = overdue_qs.filter(
                Q(invoice_number__icontains=q) |
                Q(customer__customer_name__icontains=q)
            )

        salesperson_id = request.GET.get('salesperson')
        if salesperson_id:
            overdue_qs = overdue_qs.filter(salesperson_id=salesperson_id)

        # Calculate remaining balances
        invoices = []
        for inv in overdue_qs:
            total_paid = sum(p.amount for p in inv.payments.all())
            balance = inv.total_amount - total_paid
            if balance > 0:
                invoices.append({
                    'id': inv.id,
                    'invoice_number': inv.invoice_number,
                    'customer': inv.customer,
                    'salesperson': inv.salesperson,
                    'due_date': inv.due_date,
                    'total_amount': inv.total_amount,
                    'total_paid': total_paid,
                    'balance': balance,
                    'days_overdue': (today - inv.due_date).days
                })
                
        # Optional: Pagination could be added here if needed, but standard python lists might be small enough for overdue invoices.
        
        from users.models import User
        sales_officers = User.objects.filter(role__name='Sales Officer', is_active=True).distinct()
                
        context = {
            'invoices': invoices,
            'payment_methods': Payment.PaymentMethod.choices,
            'sales_officers': sales_officers
        }
        
        # Provide Saved Filters
        try:
            from users.models import SavedFilter
            context['saved_filters'] = SavedFilter.objects.filter(user=request.user, model_name='OverdueInvoices')
        except ImportError:
            context['saved_filters'] = []
            
        return render(request, self.template_name, context)

class RecordPaymentView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'finance.manage_finance'

    def post(self, request):
        try:
            data = json.loads(request.body)
            invoice_id = data.get('invoice_id')
            amount_str = data.get('amount')
            payment_date_str = data.get('payment_date')
            payment_method = data.get('payment_method')
            reference = data.get('reference', '').strip()
            notes = data.get('notes', '').strip()

            if not amount_str:
                raise ValueError("Payment amount is required.")

            invoice = get_object_or_404(Invoice, id=invoice_id)
            amount = float(amount_str)
            
            if amount <= 0:
                raise ValueError("Payment amount must be greater than 0.")
                
            total_paid = sum(p.amount for p in invoice.payments.all())
            balance = invoice.total_amount - total_paid
            
            # Allow tiny floating point differences
            if amount > balance + 0.01:
                raise ValueError(f"Payment amount cannot exceed the current balance (Rs {balance:.2f}).")
                
            if payment_method in ['CHEQUE', 'BANK_TRANSFER'] and not reference:
                raise ValueError("Reference number is required for Cheque and Bank Transfer payments.")

            payment_date = datetime.strptime(payment_date_str, '%Y-%m-%d').date()

            with transaction.atomic():
                Payment.objects.create(
                    invoice=invoice,
                    amount=amount,
                    payment_date=payment_date,
                    payment_method=payment_method,
                    reference_number=reference,
                    notes=notes,
                    recorded_by=request.user
                )

            return JsonResponse({'status': 'ok', 'message': 'Payment recorded successfully.'})

        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
class AgedReceivablesView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'finance.manage_finance'
    template_name = 'finance/aged_receivables.html'

    def get(self, request):
        today = timezone.now().date()
        as_of_date_str = request.GET.get('as_of_date')
        if as_of_date_str:
            from datetime import datetime
            try:
                as_of_date = datetime.strptime(as_of_date_str, '%Y-%m-%d').date()
            except ValueError:
                as_of_date = today
        else:
            as_of_date = today
            
        qs = Invoice.objects.filter(
            status__in=[Invoice.Status.ISSUED, Invoice.Status.PAID],
            creation_date__date__lte=as_of_date
        ).exclude(invoice_type__in=['CASH', 'COD']).select_related('customer', 'salesperson').prefetch_related('payments')
        
        q = request.GET.get('q')
        if q:
            from django.db.models import Q
            qs = qs.filter(
                Q(invoice_number__icontains=q) |
                Q(customer__customer_name__icontains=q)
            )
            
        salesperson_id = request.GET.get('salesperson')
        if salesperson_id:
            qs = qs.filter(salesperson_id=salesperson_id)
        
        customers_data = {}
        
        for inv in qs:
            total_paid = sum(p.amount for p in inv.payments.all() if p.payment_date <= as_of_date)
            balance = inv.total_amount - total_paid
            
            if balance <= 0.005:
                continue
                
            customer_id = inv.customer.id
            if customer_id not in customers_data:
                customers_data[customer_id] = {
                    'customer': inv.customer,
                    'invoices': [],
                    'not_due': 0,
                    '1_30': 0,
                    '31_45': 0,
                    '46_60': 0,
                    '61_90': 0,
                    '91_120': 0,
                    'older': 0,
                    'total': 0
                }
                
            days_overdue = (as_of_date - inv.due_date).days if inv.due_date else 0
            
            inv_data = {
                'id': inv.id,
                'invoice_number': inv.invoice_number,
                'salesperson': inv.salesperson,
                'due_date': inv.due_date,
                'total_amount': float(inv.total_amount),
                'balance': float(balance),
                'days_overdue': days_overdue
            }
            
            if days_overdue <= 0:
                customers_data[customer_id]['not_due'] += float(balance)
                inv_data['bucket'] = 'not_due'
            elif 1 <= days_overdue <= 30:
                customers_data[customer_id]['1_30'] += float(balance)
                inv_data['bucket'] = '1_30'
            elif 31 <= days_overdue <= 45:
                customers_data[customer_id]['31_45'] += float(balance)
                inv_data['bucket'] = '31_45'
            elif 46 <= days_overdue <= 60:
                customers_data[customer_id]['46_60'] += float(balance)
                inv_data['bucket'] = '46_60'
            elif 61 <= days_overdue <= 90:
                customers_data[customer_id]['61_90'] += float(balance)
                inv_data['bucket'] = '61_90'
            elif 91 <= days_overdue <= 120:
                customers_data[customer_id]['91_120'] += float(balance)
                inv_data['bucket'] = '91_120'
            else:
                customers_data[customer_id]['older'] += float(balance)
                inv_data['bucket'] = 'older'
                
            customers_data[customer_id]['total'] += float(balance)
            customers_data[customer_id]['invoices'].append(inv_data)
            
        customers_list = list(customers_data.values())
        customers_list.sort(key=lambda x: x['total'], reverse=True)
        
        grand_totals = {
            'not_due': sum(c['not_due'] for c in customers_list),
            '1_30': sum(c['1_30'] for c in customers_list),
            '31_45': sum(c['31_45'] for c in customers_list),
            '46_60': sum(c['46_60'] for c in customers_list),
            '61_90': sum(c['61_90'] for c in customers_list),
            '91_120': sum(c['91_120'] for c in customers_list),
            'older': sum(c['older'] for c in customers_list),
            'total': sum(c['total'] for c in customers_list),
        }
        
        export_format = request.GET.get('export')
        if export_format == 'pdf':
            context = {
                'customers_data': customers_list,
                'grand_totals': grand_totals,
                'as_of_date': as_of_date
            }
            return render(request, 'finance/aged_receivables_print.html', context)
            
        if export_format == 'xlsx':
            import openpyxl
            from openpyxl.styles import Font, PatternFill
            from django.http import HttpResponse
            
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Aged Receivables"
            
            ws.append([f"Aged Receivables Report (As of {as_of_date.strftime('%Y-%m-%d')})"])
            ws.append([])
            
            headers = ["Customer / Invoice", "Salesperson", "Expected Date", "Not Due", "1-30", "31-45", "46-60", "61-90", "91-120", "Older", "Total"]
            ws.append(headers)
            
            header_font = Font(bold=True)
            header_fill = PatternFill(start_color="EEEEEE", end_color="EEEEEE", fill_type="solid")
            
            for col in range(1, len(headers) + 1):
                cell = ws.cell(row=3, column=col)
                cell.font = header_font
                cell.fill = header_fill
                
            for c in customers_list:
                row = [
                    c['customer'].customer_name,
                    "",
                    "",
                    c['not_due'],
                    c['1_30'],
                    c['31_45'],
                    c['46_60'],
                    c['61_90'],
                    c['91_120'],
                    c['older'],
                    c['total']
                ]
                ws.append(row)
                for i in range(1, len(headers)+1):
                    ws.cell(row=ws.max_row, column=i).font = Font(bold=True)
                
                for inv in c['invoices']:
                    ws.append([
                        inv['invoice_number'],
                        inv['salesperson'].get_full_name() if inv['salesperson'] else "",
                        inv['due_date'].strftime('%Y-%m-%d') if inv['due_date'] else "",
                        inv['balance'] if inv['bucket'] == 'not_due' else "",
                        inv['balance'] if inv['bucket'] == '1_30' else "",
                        inv['balance'] if inv['bucket'] == '31_45' else "",
                        inv['balance'] if inv['bucket'] == '46_60' else "",
                        inv['balance'] if inv['bucket'] == '61_90' else "",
                        inv['balance'] if inv['bucket'] == '91_120' else "",
                        inv['balance'] if inv['bucket'] == 'older' else "",
                        inv['balance']
                    ])
            
            ws.append([])
            ws.append([
                "GRAND TOTAL", "", "",
                grand_totals['not_due'],
                grand_totals['1_30'],
                grand_totals['31_45'],
                grand_totals['46_60'],
                grand_totals['61_90'],
                grand_totals['91_120'],
                grand_totals['older'],
                grand_totals['total']
            ])
            for i in range(1, len(headers)+1):
                ws.cell(row=ws.max_row, column=i).font = Font(bold=True)
                
            response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition'] = f'attachment; filename="Aged_Receivables_{as_of_date.strftime("%Y%m%d")}.xlsx"'
            wb.save(response)
            return response
            
        from users.models import User
        sales_officers = User.objects.filter(role__name='Sales Officer', is_active=True).distinct()
        
        context = {
            'customers_data': customers_list,
            'grand_totals': grand_totals,
            'as_of_date': as_of_date,
            'sales_officers': sales_officers
        }
        
        return render(request, self.template_name, context)

from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, DetailView
from .models import Account, AccountType, JournalEntry, JournalEntryLine
from .forms import AccountForm, JournalEntryForm

class ChartOfAccountsView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    permission_required = 'finance.manage_finance'
    template_name = 'finance/chart_of_accounts.html'
    model = Account
    context_object_name = 'accounts'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Group accounts by type for the view
        grouped = {}
        for account_type in AccountType.choices:
            grouped[account_type[1]] = Account.objects.filter(account_type=account_type[0])
        context['grouped_accounts'] = grouped
        return context

class AccountCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    permission_required = 'finance.manage_finance'
    template_name = 'finance/account_form.html'
    form_class = AccountForm
    success_url = reverse_lazy('finance_chart_of_accounts')

class JournalEntryListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    permission_required = 'finance.manage_finance'
    template_name = 'finance/journal_entries.html'
    model = JournalEntry
    context_object_name = 'entries'
    paginate_by = 50

class JournalEntryCreateView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'finance.manage_finance'
    template_name = 'finance/journal_entry_form.html'

    def get(self, request):
        accounts = Account.objects.filter(is_active=True)
        return render(request, self.template_name, {'accounts': accounts})

    def post(self, request):
        try:
            data = json.loads(request.body)
            date_str = data.get('date')
            reference = data.get('reference', '')
            lines = data.get('lines', [])
            
            # Validation
            if not lines or len(lines) < 2:
                return JsonResponse({'status': 'error', 'message': 'At least two lines are required.'}, status=400)
                
            total_debit = sum(float(l.get('debit') or 0) for l in lines)
            total_credit = sum(float(l.get('credit') or 0) for l in lines)
            
            if abs(total_debit - total_credit) > 0.01:
                return JsonResponse({'status': 'error', 'message': f'Debits ({total_debit}) and Credits ({total_credit}) must balance.'}, status=400)

            with transaction.atomic():
                je = JournalEntry.objects.create(
                    date=datetime.strptime(date_str, '%Y-%m-%d').date(),
                    reference=reference,
                    created_by=request.user,
                    status=JournalEntry.Status.DRAFT
                )
                
                # Check permissions if trying to post
                if data.get('action') == 'POST':
                    if request.user.has_perm('finance.post_journal_entry'):
                        je.status = JournalEntry.Status.POSTED
                        je.save()
                    else:
                        return JsonResponse({'status': 'error', 'message': 'You do not have permission to post journal entries. Save as Draft instead.'}, status=403)
                
                for line in lines:
                    JournalEntryLine.objects.create(
                        journal_entry=je,
                        account_id=line['account_id'],
                        description=line.get('description', ''),
                        debit=float(line.get('debit') or 0),
                        credit=float(line.get('credit') or 0)
                    )
            
            return JsonResponse({'status': 'ok', 'message': 'Journal Entry created successfully.'})
            
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

class GeneralLedgerView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'finance.manage_finance'
    template_name = 'finance/general_ledger.html'

    def get(self, request):
        accounts = Account.objects.filter(is_active=True)
        
        account_id = request.GET.get('account')
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')
        
        lines = []
        selected_account = None
        running_balance = 0
        
        if account_id:
            selected_account = get_object_or_404(Account, id=account_id)
            qs = JournalEntryLine.objects.filter(
                account=selected_account,
                journal_entry__status=JournalEntry.Status.POSTED
            ).select_related('journal_entry')
            
            if date_from:
                qs = qs.filter(journal_entry__date__gte=date_from)
            if date_to:
                qs = qs.filter(journal_entry__date__lte=date_to)
                
            qs = qs.order_by('journal_entry__date', 'journal_entry__id')
            
            for line in qs:
                # Calculate balance depending on account type
                # Asset/Expense increase with Debit. Liability/Equity/Revenue increase with Credit.
                amount = line.debit - line.credit if selected_account.account_type in [AccountType.ASSET, AccountType.EXPENSE] else line.credit - line.debit
                running_balance += amount
                
                lines.append({
                    'date': line.journal_entry.date,
                    'reference': line.journal_entry.reference,
                    'description': line.description,
                    'debit': line.debit,
                    'credit': line.credit,
                    'balance': running_balance
                })
                
        context = {
            'accounts': accounts,
            'selected_account': selected_account,
            'lines': lines
        }
        return render(request, self.template_name, context)
