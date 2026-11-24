import csv
import json
import calendar
import datetime
from decimal import Decimal
from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_exempt
from django.views.decorators.http import require_http_methods
from django.db import transaction
from django.db.models import Sum, Q

from .models import BankAccount, Expense, Category, UserProfile
from .seed_data import seed_user_demo_data, seed_categories, DEFAULT_CATEGORIES
from .analytics_service import compute_analytics, get_available_years
from .pdf_service import generate_expense_pdf_report
from .chat_service import process_chat_message


def user_to_dict(user):
    profile = getattr(user, 'profile', None)
    return {
        'id': user.id,
        'name': f"{user.first_name} {user.last_name}".strip() or user.username,
        'email': user.email or user.username,
        'currency': profile.currency if profile else '$',
        'theme': profile.theme if profile else 'light',
    }


@ensure_csrf_cookie
def index(request):
    """
    Renders the main single-page application dashboard.
    """
    accounts_list = []
    expenses_list = []
    if request.user.is_authenticated:
        accounts_list = [a.to_dict() for a in BankAccount.objects.filter(user=request.user)]
        expenses_list = [e.to_dict() for e in Expense.objects.filter(user=request.user).select_related('account')]

    context = {
        'user': request.user,
        'is_authenticated': request.user.is_authenticated,
        'user_data': json.dumps(user_to_dict(request.user) if request.user.is_authenticated else None),
        'accounts_data': json.dumps(accounts_list),
        'expenses_data': json.dumps(expenses_list),
        'currency': getattr(request.user.profile, 'currency', '$') if request.user.is_authenticated and hasattr(request.user, 'profile') else '$',
        'theme': getattr(request.user.profile, 'theme', 'light') if request.user.is_authenticated and hasattr(request.user, 'profile') else 'light',
    }
    return render(request, 'index.html', context)


# ==========================================
# AUTHENTICATION API
# ==========================================

@require_http_methods(['GET'])
def api_current_user(request):
    if request.user.is_authenticated:
        return JsonResponse({
            'authenticated': True,
            'user': user_to_dict(request.user)
        })
    return JsonResponse({'authenticated': False, 'user': None})


@csrf_exempt
@require_http_methods(['POST'])
def api_register(request):
    try:
        data = json.loads(request.body.decode('utf-8'))
        name = data.get('name', '').strip()
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        currency = data.get('currency', '$')

        if not email or not password:
            return JsonResponse({'success': False, 'message': 'Email and password are required.'}, status=400)

        if len(password) < 6:
            return JsonResponse({'success': False, 'message': 'Password must be at least 6 characters.'}, status=400)

        if User.objects.filter(username=email).exists() or User.objects.filter(email=email).exists():
            return JsonResponse({'success': False, 'message': 'An account with this email already exists.'}, status=400)

        name_parts = name.split(' ', 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ''

        with transaction.atomic():
            user = User.objects.create_user(
                username=email,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name
            )
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.currency = currency
            profile.save()

            # Seed demo data for instant usability
            seed_user_demo_data(user, force_reset=False)

        user.refresh_from_db()
        user.backend = 'django.contrib.auth.backends.ModelBackend'
        login(request, user)
        return JsonResponse({'success': True, 'user': user_to_dict(user)})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@csrf_exempt
@require_http_methods(['POST'])
def api_login(request):
    try:
        data = json.loads(request.body.decode('utf-8'))
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')

        # Django auth checks username
        user = authenticate(request, username=email, password=password)
        if user is None:
            # Check by email lookup if username differs
            try:
                user_obj = User.objects.get(email=email)
                user = authenticate(request, username=user_obj.username, password=password)
            except User.DoesNotExist:
                user = None

        if user is None:
            return JsonResponse({'success': False, 'message': 'Invalid email or password.'}, status=401)

        login(request, user)
        return JsonResponse({'success': True, 'user': user_to_dict(user)})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@csrf_exempt
@require_http_methods(['POST'])
def api_demo_login(request):
    try:
        demo_email = 'demo@spendwise.com'
        user, created = User.objects.get_or_create(
            username=demo_email,
            defaults={
                'email': demo_email,
                'first_name': 'Alex',
                'last_name': 'Morgan',
            }
        )
        if created or not user.has_usable_password():
            user.set_password('password123')
            user.save()

        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.currency = '$'
        profile.save()

        # Ensure demo user has data
        if not user.accounts.exists():
            seed_user_demo_data(user, force_reset=False)

        user.backend = 'django.contrib.auth.backends.ModelBackend'
        login(request, user)
        return JsonResponse({'success': True, 'user': user_to_dict(user)})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@csrf_exempt
@require_http_methods(['POST'])
def api_logout(request):
    logout(request)
    return JsonResponse({'success': True})


@csrf_exempt
@require_http_methods(['POST'])
def api_delete_user(request):
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)

    user = request.user
    logout(request)
    user.delete()
    return JsonResponse({'success': True})


@csrf_exempt
@require_http_methods(['POST'])
def api_update_theme(request):
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)

    try:
        data = json.loads(request.body.decode('utf-8'))
        theme = data.get('theme', 'light')
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        profile.theme = theme
        profile.save()
        return JsonResponse({'success': True, 'theme': theme})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


# ==========================================
# BANK ACCOUNTS API
# ==========================================

@csrf_exempt
@require_http_methods(['GET', 'POST'])
def api_accounts(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    if request.method == 'GET':
        accounts = BankAccount.objects.filter(user=request.user)
        return JsonResponse({'accounts': [acc.to_dict() for acc in accounts]})

    elif request.method == 'POST':
        try:
            data = json.loads(request.body.decode('utf-8'))
            opening_balance = Decimal(str(data.get('openingBalance', '0') or '0'))
            account = BankAccount.objects.create(
                user=request.user,
                bank_name=data.get('bankName', '').strip(),
                account_name=data.get('accountName', '').strip(),
                account_type=data.get('accountType', 'savings'),
                account_number=data.get('accountNumber', '').strip(),
                opening_balance=opening_balance,
                current_balance=opening_balance,
                currency=data.get('currency', getattr(request.user.profile, 'currency', '$')),
                color_theme=data.get('colorTheme', 'card-theme-blue')
            )
            return JsonResponse({'success': True, 'account': account.to_dict()}, status=201)
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=400)


@csrf_exempt
@require_http_methods(['GET', 'PUT', 'DELETE'])
def api_account_detail(request, pk):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    try:
        account = BankAccount.objects.get(pk=pk, user=request.user)
    except BankAccount.DoesNotExist:
        return JsonResponse({'error': 'Account not found'}, status=404)

    if request.method == 'GET':
        return JsonResponse({'account': account.to_dict()})

    elif request.method == 'PUT':
        try:
            data = json.loads(request.body.decode('utf-8'))
            if 'bankName' in data:
                account.bank_name = data['bankName'].strip()
            if 'accountName' in data:
                account.account_name = data['accountName'].strip()
            if 'accountType' in data:
                account.account_type = data['accountType']
            if 'accountNumber' in data:
                account.account_number = data['accountNumber'].strip()
            if 'colorTheme' in data:
                account.color_theme = data['colorTheme']
            if 'currentBalance' in data and data['currentBalance'] is not None:
                account.current_balance = Decimal(str(data['currentBalance']))
            account.save()
            return JsonResponse({'success': True, 'account': account.to_dict()})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=400)

    elif request.method == 'DELETE':
        account.delete()
        return JsonResponse({'success': True})


@csrf_exempt
@require_http_methods(['POST'])
def api_account_top_up(request, pk):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    try:
        account = BankAccount.objects.get(pk=pk, user=request.user)
    except BankAccount.DoesNotExist:
        return JsonResponse({'error': 'Account not found'}, status=404)

    try:
        data = json.loads(request.body.decode('utf-8'))
        amount = Decimal(str(data.get('amount', '0')))
        if amount <= 0:
            return JsonResponse({'success': False, 'message': 'Deposit amount must be greater than zero.'}, status=400)

        with transaction.atomic():
            account.current_balance += amount
            account.save()

        return JsonResponse({'success': True, 'account': account.to_dict()})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=400)


# ==========================================
# EXPENSES API
# ==========================================

@csrf_exempt
@require_http_methods(['GET', 'POST'])
def api_expenses(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    if request.method == 'GET':
        qs = Expense.objects.filter(user=request.user).select_related('account')

        # Filter: Account
        account_id = request.GET.get('accountId') or request.GET.get('account')
        if account_id and account_id != 'all':
            try:
                qs = qs.filter(account_id=int(account_id))
            except ValueError:
                pass

        # Filter: Category
        category = request.GET.get('category')
        if category and category != 'all':
            qs = qs.filter(category=category)

        # Filter: Search (place or purpose or notes)
        search = request.GET.get('search', '').strip()
        if search:
            qs = qs.filter(
                Q(place__icontains=search) |
                Q(purpose__icontains=search) |
                Q(notes__icontains=search)
            )

        # Filter: Date range
        date_from = request.GET.get('dateFrom')
        if date_from:
            qs = qs.filter(date__gte=date_from)

        date_to = request.GET.get('dateTo')
        if date_to:
            qs = qs.filter(date__lte=date_to)

        # Filter: Year
        year = request.GET.get('year')
        if year:
            try:
                qs = qs.filter(date__year=int(year))
            except ValueError:
                pass

        total_spent = float(qs.aggregate(t=Sum('amount'))['t'] or 0)
        expenses_list = [exp.to_dict() for exp in qs]

        return JsonResponse({
            'expenses': expenses_list,
            'total': total_spent,
            'count': len(expenses_list)
        })

    elif request.method == 'POST':
        try:
            data = json.loads(request.body.decode('utf-8'))
            account_id = data.get('accountId')
            account = BankAccount.objects.get(pk=account_id, user=request.user)
            amount = Decimal(str(data.get('amount', '0')))

            date_str = data.get('date')
            if date_str:
                exp_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
            else:
                exp_date = datetime.date.today()

            time_str = data.get('time', '12:00')
            try:
                exp_time = datetime.datetime.strptime(time_str, '%H:%M').time()
            except ValueError:
                exp_time = datetime.time(12, 0)

            with transaction.atomic():
                expense = Expense.objects.create(
                    user=request.user,
                    account=account,
                    amount=amount,
                    place=data.get('place', '').strip(),
                    purpose=data.get('purpose', '').strip(),
                    category=data.get('category', 'others'),
                    date=exp_date,
                    time=exp_time,
                    payment_mode=data.get('paymentMode', 'Debit Card'),
                    notes=data.get('notes', '').strip()
                )
                # Deduct from account balance
                account.current_balance -= amount
                account.save()

            return JsonResponse({'success': True, 'expense': expense.to_dict()}, status=201)
        except BankAccount.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Selected bank account does not exist.'}, status=400)
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=400)


@csrf_exempt
@require_http_methods(['GET', 'PUT', 'DELETE'])
def api_expense_detail(request, pk):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    try:
        expense = Expense.objects.get(pk=pk, user=request.user)
    except Expense.DoesNotExist:
        return JsonResponse({'error': 'Expense not found'}, status=404)

    if request.method == 'GET':
        return JsonResponse({'expense': expense.to_dict()})

    elif request.method == 'PUT':
        try:
            data = json.loads(request.body.decode('utf-8'))
            old_amount = expense.amount
            old_account = expense.account

            new_amount = Decimal(str(data.get('amount', old_amount)))
            new_account_id = data.get('accountId', old_account.id)
            new_account = BankAccount.objects.get(pk=new_account_id, user=request.user)

            date_str = data.get('date')
            if date_str:
                exp_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
            else:
                exp_date = expense.date

            time_str = data.get('time')
            if time_str:
                try:
                    exp_time = datetime.datetime.strptime(time_str, '%H:%M').time()
                except ValueError:
                    exp_time = expense.time
            else:
                exp_time = expense.time

            with transaction.atomic():
                # Adjust bank balances
                if old_account.id == new_account.id:
                    # Same account, adjust difference
                    diff = old_amount - new_amount
                    old_account.current_balance += diff
                    old_account.save()
                else:
                    # Swapped account: refund old, deduct from new
                    old_account.current_balance += old_amount
                    old_account.save()
                    new_account.current_balance -= new_amount
                    new_account.save()

                expense.account = new_account
                expense.amount = new_amount
                expense.place = data.get('place', expense.place).strip()
                expense.purpose = data.get('purpose', expense.purpose).strip()
                expense.category = data.get('category', expense.category)
                expense.date = exp_date
                expense.time = exp_time
                expense.payment_mode = data.get('paymentMode', expense.payment_mode)
                expense.notes = data.get('notes', expense.notes).strip()
                expense.save()

            return JsonResponse({'success': True, 'expense': expense.to_dict()})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=400)

    elif request.method == 'DELETE':
        with transaction.atomic():
            # Refund amount to account
            account = expense.account
            account.current_balance += expense.amount
            account.save()
            expense.delete()
        return JsonResponse({'success': True})


@require_http_methods(['GET'])
def api_export_expenses_csv(request):
    if not request.user.is_authenticated:
        return HttpResponse('Unauthorized', status=401)

    qs = Expense.objects.filter(user=request.user).select_related('account').order_by('-date', '-time')

    # Optional filter parameters
    account_id = request.GET.get('accountId')
    if account_id and account_id != 'all':
        try:
            qs = qs.filter(account_id=int(account_id))
        except ValueError:
            pass

    category = request.GET.get('category')
    if category and category != 'all':
        qs = qs.filter(category=category)

    date_from = request.GET.get('dateFrom')
    if date_from:
        qs = qs.filter(date__gte=date_from)

    date_to = request.GET.get('dateTo')
    if date_to:
        qs = qs.filter(date__lte=date_to)

    currency = getattr(request.user.profile, 'currency', '$') if hasattr(request.user, 'profile') else '$'

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="spendwise_expenses_{datetime.date.today().strftime("%Y%m%d")}.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'Expense ID', 'Date', 'Time', 'Merchant / Place', 'Purpose',
        'Category', 'Deducted Bank Account', 'Account Number', 'Payment Method',
        'Amount', 'Currency', 'Notes'
    ])

    for exp in qs:
        writer.writerow([
            exp.id,
            exp.date.strftime('%Y-%m-%d'),
            exp.time.strftime('%H:%M'),
            exp.place,
            exp.purpose,
            exp.category,
            exp.account.bank_name,
            exp.account.account_number,
            exp.payment_mode,
            float(exp.amount),
            currency,
            exp.notes
        ])

    return response


# ==========================================
# ANALYTICS API
# ==========================================

@require_http_methods(['GET'])
def api_analytics(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    year = request.GET.get('year')
    account_id = request.GET.get('accountId', 'all')
    timeframe = request.GET.get('timeframe', 'monthly')
    month = request.GET.get('month')
    quarter = request.GET.get('quarter', 1)
    half = request.GET.get('half', 1)

    data = compute_analytics(
        user=request.user,
        year=year,
        account_id=account_id,
        timeframe=timeframe,
        month=month,
        quarter=quarter,
        half=half
    )

    return JsonResponse(data)


# ==========================================
# PDF REPORTS API (Monthly, Half-Yearly, Quarterly, Yearly)
# ==========================================

@require_http_methods(['GET'])
def api_download_pdf_report(request, timeframe=None):
    """
    Generates and downloads publication-quality PDF financial reports.
    Supports Monthly, Quarterly, Half-Yearly, and Yearly timeframes,
    with filtering by year, sub-period (month/quarter/half), and bank account.
    """
    if not request.user.is_authenticated:
        return HttpResponse('Unauthorized: Please log in to download reports.', status=401)

    tf = (timeframe or request.GET.get('timeframe') or 'monthly').strip().lower()
    if tf not in ['monthly', 'quarterly', 'halfyearly', 'yearly']:
        tf = 'monthly'

    year = request.GET.get('year')
    month = request.GET.get('month')
    quarter = request.GET.get('quarter', 1)
    half = request.GET.get('half', 1)
    account_id = request.GET.get('accountId', 'all')

    try:
        pdf_buffer = generate_expense_pdf_report(
            user=request.user,
            timeframe=tf,
            year=year,
            month=month,
            quarter=quarter,
            half=half,
            account_id=account_id
        )
    except Exception as e:
        return HttpResponse(f"Error generating PDF report: {str(e)}", status=500)

    # Build descriptive filename
    cur_year = year or datetime.date.today().year
    if tf == 'monthly':
        try:
            m_idx = int(month) if month is not None else (datetime.date.today().month - 1)
            m_name = calendar.month_name[m_idx + 1]
        except (ValueError, IndexError):
            m_name = calendar.month_name[datetime.date.today().month]
        filename = f"SpendWise_Monthly_Report_{m_name}_{cur_year}.pdf"

    elif tf == 'quarterly':
        q_idx = int(quarter) if quarter else 1
        filename = f"SpendWise_Quarterly_Report_Q{q_idx}_{cur_year}.pdf"

    elif tf == 'halfyearly':
        h_idx = int(half) if half else 1
        filename = f"SpendWise_HalfYearly_Report_H{h_idx}_{cur_year}.pdf"

    elif tf == 'yearly':
        filename = f"SpendWise_Annual_Report_{cur_year}.pdf"

    else:
        filename = f"SpendWise_Report_{cur_year}.pdf"

    response = HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


# ==========================================
# CHATBOT API (User-scoped Financial Assistant)
# ==========================================

@csrf_exempt
@require_http_methods(['POST'])
def api_chat(request):
    """
    Receives user query and returns contextual answers generated exclusively
    from the authenticated user's SQLite financial records.
    """
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Unauthorized: Please log in to chat with SpendBot.'}, status=401)

    try:
        data = json.loads(request.body.decode('utf-8'))
        message = data.get('message', '').strip()
        if not message:
            return JsonResponse({'error': 'Message cannot be empty.'}, status=400)

        response_payload = process_chat_message(request.user, message)
        return JsonResponse(response_payload)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON format.'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ==========================================
# DEMO DATA RESET & REFERENCE DATA
# ==========================================

@csrf_exempt
@require_http_methods(['POST'])
def api_demo_reset(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    seed_user_demo_data(request.user, force_reset=True)
    return JsonResponse({'success': True, 'message': 'Demo data reset successfully.'})


@require_http_methods(['GET'])
def api_categories(request):
    seed_categories()
    categories = Category.objects.all()
    account_types = [
        {'id': 'savings', 'label': 'Savings Account', 'icon': 'bi-piggy-bank'},
        {'id': 'checking', 'label': 'Checking / Salary', 'icon': 'bi-briefcase'},
        {'id': 'credit', 'label': 'Credit Card', 'icon': 'bi-credit-card-2-front'},
        {'id': 'wallet', 'label': 'Digital Wallet / UPI', 'icon': 'bi-phone'},
        {'id': 'investment', 'label': 'Investment / Brokerage', 'icon': 'bi-graph-up-arrow'},
        {'id': 'cash', 'label': 'Cash in Hand', 'icon': 'bi-cash-stack'}
    ]
    card_themes = [
        {'id': 'card-theme-blue', 'name': 'Solid Royal Blue', 'class': 'card-theme-blue'},
        {'id': 'card-theme-purple', 'name': 'Solid Cool Indigo', 'class': 'card-theme-purple'},
        {'id': 'card-theme-emerald', 'name': 'Solid Ocean Teal', 'class': 'card-theme-emerald'},
        {'id': 'card-theme-dark', 'name': 'Solid Cool Slate', 'class': 'card-theme-dark'},
        {'id': 'card-theme-crimson', 'name': 'Solid Pacific Cyan', 'class': 'card-theme-crimson'}
    ]
    return JsonResponse({
        'categories': [c.to_dict() for c in categories],
        'accountTypes': account_types,
        'cardThemes': card_themes
    })
