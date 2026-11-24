import calendar
from decimal import Decimal
from django.db.models import Sum, Count, Q
from .models import Expense, BankAccount, Category
from .seed_data import DEFAULT_CATEGORIES

def get_available_years(user):
    years = list(Expense.objects.filter(user=user).dates('date', 'year', order='DESC'))
    year_nums = [y.year for y in years]
    current_year = calendar.datetime.date.today().year
    if current_year not in year_nums:
        year_nums.insert(0, current_year)
    return sorted(list(set(year_nums)), reverse=True)

def compute_analytics(user, year=None, account_id=None, timeframe='monthly', month=None, quarter=1, half=1):
    today = calendar.datetime.date.today()
    if not year:
        year = today.year
    else:
        year = int(year)

    qs = Expense.objects.filter(user=user, date__year=year)
    if account_id and account_id != 'all':
        try:
            acc_id = int(account_id)
            qs = qs.filter(account_id=acc_id)
        except (ValueError, TypeError):
            pass

    # 1. Determine period dates & comparison
    period_title = ""
    comparison_title = ""
    comparison_val = "—"

    period_expenses = qs
    comp_expenses = Expense.objects.none()

    if timeframe == 'monthly':
        if month is None:
            month = today.month - 1 # 0-indexed like JS
        else:
            month = int(month)
        month_1based = month + 1
        month_name = calendar.month_name[month_1based]
        period_title = f"{month_name} {year}"
        period_expenses = qs.filter(date__month=month_1based)

        # Comparison: Previous month
        if month_1based > 1:
            prev_qs = Expense.objects.filter(user=user, date__year=year, date__month=month_1based - 1)
        else:
            prev_qs = Expense.objects.filter(user=user, date__year=year - 1, date__month=12)
        if account_id and account_id != 'all':
            prev_qs = prev_qs.filter(account_id=account_id)
        comp_expenses = prev_qs
        comparison_title = "vs. Previous Month"

    elif timeframe == 'quarterly':
        quarter = int(quarter)
        q_months = {
            1: [1, 2, 3],
            2: [4, 5, 6],
            3: [7, 8, 9],
            4: [10, 11, 12]
        }.get(quarter, [1, 2, 3])
        period_title = f"Q{quarter} ({calendar.month_abbr[q_months[0]]} - {calendar.month_abbr[q_months[-1]]}) {year}"
        period_expenses = qs.filter(date__month__in=q_months)

        # Comparison: Previous quarter
        if quarter > 1:
            prev_q_months = {2: [1, 2, 3], 3: [4, 5, 6], 4: [7, 8, 9]}[quarter]
            prev_qs = Expense.objects.filter(user=user, date__year=year, date__month__in=prev_q_months)
        else:
            prev_qs = Expense.objects.filter(user=user, date__year=year - 1, date__month__in=[10, 11, 12])
        if account_id and account_id != 'all':
            prev_qs = prev_qs.filter(account_id=account_id)
        comp_expenses = prev_qs
        comparison_title = "vs. Previous Quarter"

    elif timeframe == 'halfyearly':
        half = int(half)
        h_months = [1, 2, 3, 4, 5, 6] if half == 1 else [7, 8, 9, 10, 11, 12]
        period_title = f"H{half} ({'Jan - Jun' if half == 1 else 'Jul - Dec'}) {year}"
        period_expenses = qs.filter(date__month__in=h_months)

        # Comparison: the other half or previous year
        comp_months = [7, 8, 9, 10, 11, 12] if half == 1 else [1, 2, 3, 4, 5, 6]
        comp_year = year - 1 if half == 1 else year
        prev_qs = Expense.objects.filter(user=user, date__year=comp_year, date__month__in=comp_months)
        if account_id and account_id != 'all':
            prev_qs = prev_qs.filter(account_id=account_id)
        comp_expenses = prev_qs
        comparison_title = f"vs. {'H2 ' + str(year-1) if half == 1 else 'H1 ' + str(year)}"

    elif timeframe == 'yearly':
        period_title = f"Full Year {year}"
        period_expenses = qs
        prev_qs = Expense.objects.filter(user=user, date__year=year - 1)
        if account_id and account_id != 'all':
            prev_qs = prev_qs.filter(account_id=account_id)
        comp_expenses = prev_qs
        comparison_title = f"vs. Year {year - 1}"

    # Totals
    period_total = float(period_expenses.aggregate(t=Sum('amount'))['t'] or 0)
    comp_total = float(comp_expenses.aggregate(t=Sum('amount'))['t'] or 0)
    tx_count = period_expenses.count()

    # Percentage change
    if comp_total > 0:
        pct_change = round(((period_total - comp_total) / comp_total) * 100, 1)
        if pct_change > 0:
            comparison_val = f"+{pct_change}%"
        else:
            comparison_val = f"{pct_change}%"
    elif period_total > 0 and comp_total == 0:
        comparison_val = "+100% (No prev data)"
    else:
        comparison_val = "0%"

    # 2. Category Breakdown & Leaderboard
    cat_meta = {c['code']: c for c in DEFAULT_CATEGORIES}
    cat_aggregates = period_expenses.values('category').annotate(
        total=Sum('amount'),
        count=Count('id')
    ).order_by('-total')

    category_leaderboard = []
    category_chart_labels = []
    category_chart_data = []
    category_chart_colors = []

    for item in cat_aggregates:
        code = item['category']
        tot = float(item['total'])
        cnt = item['count']
        meta = cat_meta.get(code, {'name': code.capitalize(), 'icon': 'bi-tag', 'color': '#6c757d'})
        pct = round((tot / period_total * 100), 1) if period_total > 0 else 0

        entry = {
            'id': code,
            'name': meta['name'],
            'icon': meta['icon'],
            'color': meta['color'],
            'total': tot,
            'count': cnt,
            'percentage': pct,
        }
        category_leaderboard.append(entry)
        category_chart_labels.append(meta['name'])
        category_chart_data.append(tot)
        category_chart_colors.append(meta['color'])

    # Spotlight on Top Category
    top_category = category_leaderboard[0] if category_leaderboard else None

    # 3. Trend Chart Data
    trend_labels = []
    trend_values = []

    if timeframe == 'monthly':
        # Daily breakdown for the selected month
        month_1based = (month if month is not None else 0) + 1
        num_days = calendar.monthrange(year, month_1based)[1]
        daily_dict = {d: 0.0 for d in range(1, num_days + 1)}
        for exp in period_expenses:
            daily_dict[exp.date.day] += float(exp.amount)
        for d in range(1, num_days + 1):
            trend_labels.append(f"{month_name[:3]} {d}")
            trend_values.append(round(daily_dict[d], 2))

    elif timeframe == 'quarterly':
        # 3 months in quarter
        for m in q_months:
            m_total = float(qs.filter(date__month=m).aggregate(t=Sum('amount'))['t'] or 0)
            trend_labels.append(calendar.month_name[m])
            trend_values.append(round(m_total, 2))

    elif timeframe == 'halfyearly':
        # 6 months in half
        for m in h_months:
            m_total = float(qs.filter(date__month=m).aggregate(t=Sum('amount'))['t'] or 0)
            trend_labels.append(calendar.month_name[m])
            trend_values.append(round(m_total, 2))

    elif timeframe == 'yearly':
        # 12 months
        for m in range(1, 13):
            m_total = float(qs.filter(date__month=m).aggregate(t=Sum('amount'))['t'] or 0)
            trend_labels.append(calendar.month_abbr[m])
            trend_values.append(round(m_total, 2))

    # 4. Cross-Account Breakdown
    accounts = BankAccount.objects.filter(user=user)
    cross_accounts = []
    for acc in accounts:
        acc_spent = float(Expense.objects.filter(user=user, account=acc, date__year=year).aggregate(t=Sum('amount'))['t'] or 0)
        cross_accounts.append({
            'id': acc.id,
            'name': acc.bank_name,
            'nickname': acc.account_name,
            'currentBalance': float(acc.current_balance),
            'totalExpenses': acc_spent,
            'colorTheme': acc.color_theme,
        })

    return {
        'timeframe': timeframe,
        'year': year,
        'periodTitle': period_title,
        'stat1': {
            'title': f"{period_title} Total",
            'value': period_total,
        },
        'stat2': {
            'title': comparison_title,
            'value': comparison_val,
        },
        'stat3': {
            'title': 'Transactions',
            'value': f"{tx_count} entries",
        },
        'topCategory': top_category,
        'categoryLeaderboard': category_leaderboard,
        'trendChart': {
            'labels': trend_labels,
            'values': trend_values,
        },
        'categoryChart': {
            'labels': category_chart_labels,
            'values': category_chart_data,
            'colors': category_chart_colors,
        },
        'crossAccounts': cross_accounts,
        'availableYears': get_available_years(user),
    }
