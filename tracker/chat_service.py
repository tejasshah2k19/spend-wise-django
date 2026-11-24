"""
SpendWise - Intelligent Financial Chatbot Engine
Answers user questions scoped exclusively to their own financial records:
- Total expense
- Total monthly expense
- Quarterly (qtr) expense
- Yearly expense
- Specific month expense (e.g. Jan month expense)
- Category wise expense
- Max month expense (peak spending month)
- Max category expense (highest spending category)
- Specific category spend, bank balances, recent expenses, and highest single purchase.
"""

import re
import calendar
import datetime
from decimal import Decimal
from django.db.models import Sum, Count, Max, Q
from .models import Expense, BankAccount, Category
from .seed_data import DEFAULT_CATEGORIES


MONTH_NAMES_MAP = {
    'jan': 1, 'january': 1,
    'feb': 2, 'february': 2,
    'mar': 3, 'march': 3,
    'apr': 4, 'april': 4,
    'may': 5,
    'jun': 6, 'june': 6,
    'jul': 7, 'july': 7,
    'aug': 8, 'august': 8,
    'sep': 9, 'sept': 9, 'september': 9,
    'oct': 10, 'october': 10,
    'nov': 11, 'november': 11,
    'dec': 12, 'december': 12
}

CATEGORY_SYNONYMS = {
    'food': ['food', 'dining', 'restaurant', 'cafe', 'coffee', 'lunch', 'dinner', 'breakfast'],
    'groceries': ['groceries', 'grocery', 'mart', 'supermarket', 'provisions'],
    'housing': ['housing', 'rent', 'apartment', 'mortgage', 'maintenance'],
    'bills': ['bills', 'bill', 'utilities', 'utility', 'electricity', 'water', 'internet', 'phone', 'wifi'],
    'transport': ['transport', 'transportation', 'fuel', 'gas', 'gasoline', 'metro', 'subway', 'transit', 'uber', 'taxi', 'commute'],
    'shopping': ['shopping', 'retail', 'clothes', 'clothing', 'apparel', 'amazon'],
    'entertainment': ['entertainment', 'movie', 'movies', 'cinema', 'games', 'gaming', 'netflix', 'spotify', 'theatre'],
    'health': ['health', 'medical', 'medicine', 'doctor', 'pharmacy', 'dental', 'clinic', 'hospital'],
    'education': ['education', 'course', 'courses', 'books', 'tuition', 'school', 'learning'],
    'travel': ['travel', 'flight', 'hotel', 'vacation', 'holiday', 'trip', 'airline'],
    'fitness': ['fitness', 'gym', 'workout', 'sports'],
    'others': ['others', 'other', 'misc', 'miscellaneous']
}


def get_user_currency(user):
    profile = getattr(user, 'profile', None)
    return profile.currency if profile else '$'


def format_amount(amount, currency='$'):
    val = float(amount or 0)
    return f"{currency}{val:,.2f}"


def get_category_meta(category_code):
    for cat in DEFAULT_CATEGORIES:
        if cat['code'] == category_code:
            return cat
    return {'code': category_code, 'name': category_code.capitalize(), 'icon': 'bi-tag', 'color': '#6c757d'}


def process_chat_message(user, raw_message):
    """
    Parses a user natural language message and answers based strictly
    on the authenticated user's expenses and bank accounts.
    """
    today = datetime.date.today()
    current_year = today.year
    currency = get_user_currency(user)

    msg = (raw_message or '').strip().lower()
    clean_msg = re.sub(r'[^\w\s]', ' ', msg)
    tokens = clean_msg.split()

    # Scope expenses strictly to user
    user_expenses = Expense.objects.filter(user=user)
    user_accounts = BankAccount.objects.filter(user=user)

    total_expense_count = user_expenses.count()

    # Extract optional year from message (e.g. 2025, 2026, 2024)
    year_match = re.search(r'\b(20\d\d)\b', msg)
    query_year = int(year_match.group(1)) if year_match else current_year

    # Helper for quick suggestions
    default_suggestions = [
        "💰 Total Expense",
        "📅 Total Monthly Expense",
        "📊 Qtr Expense",
        "🗓️ Yearly Expense",
        "❄️ Jan Month Expense",
        "🏷️ Category Wise Expense",
        "📈 Max Month Expense",
        "🏆 Max Category Expense"
    ]

    if total_expense_count == 0 and not any(k in msg for k in ['hi', 'hello', 'hey', 'help', 'balance', 'account']):
        return {
            'reply': (
                f"👋 Hello **{user.first_name or user.username}**!\n\n"
                f"You haven't recorded any expenses in your account yet. Once you log transactions "
                f"using the **'Add Expense'** button, I'll be able to calculate your monthly, quarterly, "
                f"yearly, category, and peak spending data instantly!"
            ),
            'intent': 'empty_state',
            'suggestions': ["💳 Check Bank Balance", "❓ What can you do?"]
        }

    # ==========================================================
    # 1. MAX CATEGORY EXPENSE (Highest Spending Category)
    # ==========================================================
    if re.search(r'(max|highest|peak|top|biggest|most)\s+(category|cat)', msg) or \
       re.search(r'category\s+(max|highest|peak|top)', msg) or \
       'where do i spend the most' in msg or 'where i spend the most' in msg or \
       'top spending category' in msg or 'top category' in msg:
        
        cat_agg = user_expenses.values('category').annotate(
            total=Sum('amount'),
            count=Count('id')
        ).order_by('-total')

        if not cat_agg.exists():
            return {
                'reply': "You don't have any expense records yet to determine the top category.",
                'intent': 'max_category',
                'suggestions': default_suggestions[:4]
            }

        top = cat_agg[0]
        meta = get_category_meta(top['category'])
        top_total = float(top['total'])
        top_count = top['count']
        all_time_total = float(user_expenses.aggregate(t=Sum('amount'))['t'] or 0)
        pct = (top_total / all_time_total * 100) if all_time_total > 0 else 0

        # Also get runner-up if available
        runner_up_text = ""
        if len(cat_agg) > 1:
            runner = cat_agg[1]
            r_meta = get_category_meta(runner['category'])
            runner_up_text = f"\n• Runner-up: **{r_meta['name']}** at {format_amount(runner['total'], currency)} ({round(float(runner['total']) / all_time_total * 100, 1)}%)"

        reply = (
            f"🏆 **Highest Spending Category (Max Category Expense):**\n\n"
            f"Your #1 largest expense category is **{meta['name']}**!\n\n"
            f"• **Total Spent:** **{format_amount(top_total, currency)}**\n"
            f"• **Transactions:** **{top_count}** entries\n"
            f"• **Budget Share:** <span class='badge bg-danger text-white'>{pct:.1f}%</span> of your entire expenses ({format_amount(all_time_total, currency)})"
            f"{runner_up_text}\n\n"
            f"💡 *Tip: Check out the Analytics section to see detailed charts and trends for {meta['name']}.*"
        )
        return {
            'reply': reply,
            'intent': 'max_category_expense',
            'suggestions': ["🏷️ Category Wise Expense", "📈 Max Month Expense", "📅 Total Monthly Expense", "💰 Total Expense"]
        }

    # ==========================================================
    # 2. MAX MONTH EXPENSE (Highest Spending Month)
    # ==========================================================
    if re.search(r'(max|highest|peak|biggest|most)\s+(month)', msg) or \
       re.search(r'month\s+(max|highest|peak|most)', msg) or \
       'peak spending month' in msg or 'which month did i spend the most' in msg:

        monthly_agg = user_expenses.filter(date__year=query_year).values('date__month').annotate(
            total=Sum('amount'),
            count=Count('id')
        ).order_by('-total')

        if not monthly_agg.exists():
            # Try any year
            monthly_agg = user_expenses.values('date__year', 'date__month').annotate(
                total=Sum('amount'),
                count=Count('id')
            ).order_by('-total')

        if not monthly_agg.exists():
            return {
                'reply': f"No expense records found for {query_year}.",
                'intent': 'max_month_expense',
                'suggestions': default_suggestions[:4]
            }

        top_month = monthly_agg[0]
        m_num = top_month['date__month']
        m_name = calendar.month_name[m_num]
        m_total = float(top_month['total'])
        m_count = top_month['count']

        # Find top category in that peak month
        month_expenses = user_expenses.filter(date__year=query_year, date__month=m_num)
        top_cat_obj = month_expenses.values('category').annotate(tot=Sum('amount')).order_by('-tot').first()
        top_cat_text = ""
        if top_cat_obj:
            t_meta = get_category_meta(top_cat_obj['category'])
            top_cat_text = f"\n• Top category in {m_name}: **{t_meta['name']}** ({format_amount(top_cat_obj['tot'], currency)})"

        # Calculate daily average in that month
        num_days = calendar.monthrange(query_year, m_num)[1]
        daily_avg = m_total / num_days

        reply = (
            f"📈 **Highest Spending Month (Max Month Expense):**\n\n"
            f"Your peak spending month in **{query_year}** was **{m_name}**!\n\n"
            f"• **Total Spent:** **{format_amount(m_total, currency)}**\n"
            f"• **Transactions:** **{m_count}** entries\n"
            f"• **Daily Average:** ~{format_amount(daily_avg, currency)} / day"
            f"{top_cat_text}\n\n"
            f"💡 *Would you like to see the category breakdown for {m_name} or another month?*"
        )
        return {
            'reply': reply,
            'intent': 'max_month_expense',
            'suggestions': [f"❄️ {m_name[:3]} Month Expense", "🏆 Max Category Expense", "📊 Qtr Expense", "🗓️ Yearly Expense"]
        }

    # ==========================================================
    # 3. CATEGORY WISE EXPENSE (Breakdown Across All Categories)
    # ==========================================================
    if ('category wise' in msg or 'category-wise' in msg or 'category breakdown' in msg or
        'spending by category' in msg or 'expenses by category' in msg or 'category expense' in msg or
        'categories expense' in msg or 'categories breakdown' in msg or 'all categories' in msg):

        cat_agg = user_expenses.values('category').annotate(
            total=Sum('amount'),
            count=Count('id')
        ).order_by('-total')

        all_total = float(user_expenses.aggregate(t=Sum('amount'))['t'] or 0)
        total_tx = user_expenses.count()

        if not cat_agg.exists():
            return {
                'reply': "You don't have any categorized expenses recorded yet.",
                'intent': 'category_wise',
                'suggestions': default_suggestions[:4]
            }

        lines = [
            f"🏷️ **Category-Wise Spending Breakdown:**",
            f"Total across all categories: **{format_amount(all_total, currency)}** ({total_tx} transactions)\n"
        ]

        for i, item in enumerate(cat_agg, 1):
            meta = get_category_meta(item['category'])
            tot = float(item['total'])
            cnt = item['count']
            pct = (tot / all_total * 100) if all_total > 0 else 0
            lines.append(f"{i}. **{meta['name']}**: **{format_amount(tot, currency)}** ({pct:.1f}% • {cnt} txns)")

        top_cat = get_category_meta(cat_agg[0]['category'])
        lines.append(f"\n💡 *Your #1 category is **{top_cat['name']}**.*")

        return {
            'reply': "\n".join(lines),
            'intent': 'category_wise_expense',
            'suggestions': ["🏆 Max Category Expense", "📈 Max Month Expense", "📅 Total Monthly Expense", "💰 Total Expense"]
        }

    # ==========================================================
    # 4. SPECIFIC MONTH EXPENSE (e.g. "jan month expense", "november expense")
    # ==========================================================
    detected_month = None
    for m_key, m_val in MONTH_NAMES_MAP.items():
        # Match whole word or pattern like "jan expense", "jan month expense"
        if re.search(r'\b' + m_key + r'\b', msg):
            detected_month = m_val
            break

    # If user mentioned a specific month (and didn't ask "max month")
    if detected_month is not None:
        m_name = calendar.month_name[detected_month]
        m_qs = user_expenses.filter(date__year=query_year, date__month=detected_month)
        m_total = float(m_qs.aggregate(t=Sum('amount'))['t'] or 0)
        m_count = m_qs.count()

        if m_count == 0:
            return {
                'reply': (
                    f"📅 **{m_name} {query_year} Expenses:**\n\n"
                    f"You have **no recorded expenses** for {m_name} {query_year}.\n\n"
                    f"💡 *You can log a transaction for this month using the '+ Add Expense' button!*"
                ),
                'intent': 'month_expense',
                'suggestions': ["📅 Total Monthly Expense", "📈 Max Month Expense", "💰 Total Expense"]
            }

        # Top category in that month
        top_cat_obj = m_qs.values('category').annotate(tot=Sum('amount'), cnt=Count('id')).order_by('-tot').first()
        top_cat_text = ""
        if top_cat_obj:
            t_meta = get_category_meta(top_cat_obj['category'])
            c_pct = round(float(top_cat_obj['tot']) / m_total * 100, 1) if m_total > 0 else 0
            top_cat_text = f"\n• **Top Category:** **{t_meta['name']}** ({format_amount(top_cat_obj['tot'], currency)}, {c_pct}%)"

        # Most frequent place
        top_place = m_qs.values('place').annotate(cnt=Count('id'), tot=Sum('amount')).order_by('-tot').first()
        place_text = ""
        if top_place:
            place_text = f"\n• **Largest Merchant Spend:** {top_place['place']} ({format_amount(top_place['tot'], currency)})"

        avg_txn = m_total / m_count if m_count > 0 else 0

        reply = (
            f"📅 **{m_name} {query_year} Expense Summary:**\n\n"
            f"• **Total Spent in {m_name}:** **{format_amount(m_total, currency)}**\n"
            f"• **Transactions:** **{m_count}** entries\n"
            f"• **Average per Transaction:** {format_amount(avg_txn, currency)}"
            f"{top_cat_text}"
            f"{place_text}\n\n"
            f"💡 *Would you like to download the full {m_name} PDF report from the Analytics tab?*"
        )
        return {
            'reply': reply,
            'intent': 'specific_month_expense',
            'suggestions': [f"🏷️ Category Wise Expense", "📈 Max Month Expense", "📊 Qtr Expense", "💰 Total Expense"]
        }

    # ==========================================================
    # 5. TOTAL MONTHLY EXPENSE (Current Month or Monthly Overview)
    # ==========================================================
    if ('monthly expense' in msg or 'monthly total' in msg or 'this month' in msg or
        'current month' in msg or 'month expense' in msg or 'total monthly' in msg):

        cur_m = today.month
        cur_y = today.year
        cur_m_name = calendar.month_name[cur_m]

        m_qs = user_expenses.filter(date__year=cur_y, date__month=cur_m)
        cur_total = float(m_qs.aggregate(t=Sum('amount'))['t'] or 0)
        cur_count = m_qs.count()

        # Comparison with previous month
        prev_m = 12 if cur_m == 1 else cur_m - 1
        prev_y = cur_y - 1 if cur_m == 1 else cur_y
        prev_m_name = calendar.month_name[prev_m]
        prev_qs = user_expenses.filter(date__year=prev_y, date__month=prev_m)
        prev_total = float(prev_qs.aggregate(t=Sum('amount'))['t'] or 0)

        comparison_text = "—"
        if prev_total > 0:
            diff = cur_total - prev_total
            pct = round((diff / prev_total) * 100, 1)
            sign = "+" if pct > 0 else ""
            badge_class = "danger" if pct > 0 else "success"
            comparison_text = f"<span class='badge bg-{badge_class} text-white'>{sign}{pct}%</span> vs {prev_m_name} ({format_amount(prev_total, currency)})"
        elif cur_total > 0 and prev_total == 0:
            comparison_text = f"First active tracking month (no data for {prev_m_name})"

        top_cat_obj = m_qs.values('category').annotate(tot=Sum('amount')).order_by('-tot').first()
        top_cat_text = ""
        if top_cat_obj:
            t_meta = get_category_meta(top_cat_obj['category'])
            top_cat_text = f"\n• **Top Category this Month:** **{t_meta['name']}** ({format_amount(top_cat_obj['tot'], currency)})"

        daily_avg = cur_total / today.day if today.day > 0 else cur_total

        reply = (
            f"📅 **Total Monthly Expense ({cur_m_name} {cur_y}):**\n\n"
            f"• **Current Month Total:** **{format_amount(cur_total, currency)}**\n"
            f"• **Month-to-Date Transactions:** **{cur_count}** entries\n"
            f"• **Daily Average (Day 1 to {today.day}):** ~{format_amount(daily_avg, currency)} / day\n"
            f"• **Comparison:** {comparison_text}"
            f"{top_cat_text}\n\n"
            f"💡 *Ask for any specific month like 'Jan month expense' or 'March expense' to see past history.*"
        )
        return {
            'reply': reply,
            'intent': 'total_monthly_expense',
            'suggestions': ["❄️ Jan Month Expense", "📈 Max Month Expense", "📊 Qtr Expense", "🏆 Max Category Expense"]
        }

    # ==========================================================
    # 6. QUARTERLY EXPENSE (Qtr Expense / Q1, Q2, Q3, Q4)
    # ==========================================================
    if ('qtr' in msg or 'quarter' in msg or 'quarterly' in msg or
        re.search(r'\bq[1-4]\b', msg)):

        # Determine target quarter (1 to 4)
        q_target = None
        for q_num in range(1, 5):
            if f'q{q_num}' in msg or f'quarter {q_num}' in msg or f'qtr {q_num}' in msg:
                q_target = q_num
                break

        # Default to current quarter if not specified
        if q_target is None:
            q_target = (today.month - 1) // 3 + 1

        quarter_months = {
            1: ([1, 2, 3], 'Q1 (Jan - Mar)'),
            2: ([4, 5, 6], 'Q2 (Apr - Jun)'),
            3: ([7, 8, 9], 'Q3 (Jul - Sep)'),
            4: ([10, 11, 12], 'Q4 (Oct - Dec)')
        }
        m_list, q_label = quarter_months[q_target]

        q_qs = user_expenses.filter(date__year=query_year, date__month__in=m_list)
        q_total = float(q_qs.aggregate(t=Sum('amount'))['t'] or 0)
        q_count = q_qs.count()

        # Monthly breakdown within this quarter
        monthly_breakdown = []
        for m in m_list:
            m_sum = float(q_qs.filter(date__month=m).aggregate(t=Sum('amount'))['t'] or 0)
            monthly_breakdown.append(f"• **{calendar.month_abbr[m]}:** {format_amount(m_sum, currency)}")

        top_cat_obj = q_qs.values('category').annotate(tot=Sum('amount')).order_by('-tot').first()
        top_cat_text = ""
        if top_cat_obj:
            t_meta = get_category_meta(top_cat_obj['category'])
            top_cat_text = f"\n• **Top Category in {q_label.split()[0]}:** **{t_meta['name']}** ({format_amount(top_cat_obj['tot'], currency)})"

        reply = (
            f"📊 **Quarterly Expense — {q_label} {query_year}:**\n\n"
            f"• **Total Quarter Expense:** **{format_amount(q_total, currency)}**\n"
            f"• **Total Transactions:** **{q_count}** entries\n\n"
            f"**Monthly Breakdown:**\n"
            + "\n".join(monthly_breakdown)
            + f"{top_cat_text}\n\n"
            f"💡 *Ask for 'Q1 expense', 'Q2 expense', 'Q3 expense', or 'Q4 expense' to inspect another quarter.*"
        )
        return {
            'reply': reply,
            'intent': 'qtr_expense',
            'suggestions': ["🗓️ Yearly Expense", "🏆 Max Category Expense", "📈 Max Month Expense", "💰 Total Expense"]
        }

    # ==========================================================
    # 7. YEARLY EXPENSE / ANNUAL EXPENSE
    # ==========================================================
    if ('yearly' in msg or 'annual' in msg or 'year expense' in msg or 'yearly expense' in msg or
        'this year' in msg or 'year total' in msg or 'total expense for year' in msg):

        y_qs = user_expenses.filter(date__year=query_year)
        y_total = float(y_qs.aggregate(t=Sum('amount'))['t'] or 0)
        y_count = y_qs.count()

        if y_count == 0:
            return {
                'reply': f"You have no recorded expenses for the year **{query_year}**.",
                'intent': 'yearly_expense',
                'suggestions': default_suggestions[:4]
            }

        avg_month = y_total / 12

        # Find peak spending month in this year
        peak_month_obj = y_qs.values('date__month').annotate(tot=Sum('amount')).order_by('-tot').first()
        peak_text = ""
        if peak_month_obj:
            peak_m_name = calendar.month_name[peak_month_obj['date__month']]
            peak_text = f"\n• **Peak Month:** **{peak_m_name}** ({format_amount(peak_month_obj['tot'], currency)})"

        top_cat_obj = y_qs.values('category').annotate(tot=Sum('amount')).order_by('-tot').first()
        top_cat_text = ""
        if top_cat_obj:
            t_meta = get_category_meta(top_cat_obj['category'])
            c_pct = round(float(top_cat_obj['tot']) / y_total * 100, 1) if y_total > 0 else 0
            top_cat_text = f"\n• **Top Category of the Year:** **{t_meta['name']}** ({format_amount(top_cat_obj['tot'], currency)}, {c_pct}%)"

        reply = (
            f"🗓️ **Yearly / Annual Expense ({query_year}):**\n\n"
            f"• **Total Spent in {query_year}:** **{format_amount(y_total, currency)}**\n"
            f"• **Total Transactions:** **{y_count}** entries\n"
            f"• **Monthly Average:** ~{format_amount(avg_month, currency)} / month"
            f"{peak_text}"
            f"{top_cat_text}\n\n"
            f"💡 *You can download the full annual PDF financial report from the Analytics tab!*"
        )
        return {
            'reply': reply,
            'intent': 'yearly_expense',
            'suggestions': ["📊 Qtr Expense", "📈 Max Month Expense", "🏆 Max Category Expense", "🏷️ Category Wise Expense"]
        }

    # ==========================================================
    # 8. TOTAL EXPENSE (Overall Grand Total)
    # ==========================================================
    if ('total expense' in msg or 'total expenses' in msg or 'all expense' in msg or
        'overall expense' in msg or 'how much did i spend' in msg or 'total spend' in msg or
        'all spending' in msg or msg.strip() == 'total'):

        all_total = float(user_expenses.aggregate(t=Sum('amount'))['t'] or 0)
        all_count = user_expenses.count()

        cur_year_total = float(user_expenses.filter(date__year=current_year).aggregate(t=Sum('amount'))['t'] or 0)
        cur_year_count = user_expenses.filter(date__year=current_year).count()

        cur_month_total = float(user_expenses.filter(date__year=current_year, date__month=today.month).aggregate(t=Sum('amount'))['t'] or 0)

        avg_txn = all_total / all_count if all_count > 0 else 0

        reply = (
            f"💰 **Total Overall Expenses Summary:**\n\n"
            f"• **All-Time Total Spent:** **{format_amount(all_total, currency)}**\n"
            f"• **Total Transactions Logged:** **{all_count}** entries\n"
            f"• **Average per Transaction:** {format_amount(avg_txn, currency)}\n\n"
            f"**Timeframe Highlights:**\n"
            f"• **Current Year ({current_year}):** {format_amount(cur_year_total, currency)} ({cur_year_count} txns)\n"
            f"• **Current Month ({calendar.month_name[today.month]}):** {format_amount(cur_month_total, currency)}\n\n"
            f"💡 *Ask for 'monthly expense', 'qtr expense', or 'category wise expense' to dive deeper!*"
        )
        return {
            'reply': reply,
            'intent': 'total_expense',
            'suggestions': ["📅 Total Monthly Expense", "📊 Qtr Expense", "🏷️ Category Wise Expense", "📈 Max Month Expense"]
        }

    # ==========================================================
    # 9. SPECIFIC CATEGORY SPENDING (e.g. "how much on food?")
    # ==========================================================
    matched_cat_code = None
    for cat_code, synonyms in CATEGORY_SYNONYMS.items():
        for syn in synonyms:
            if re.search(r'\b' + syn + r'\b', msg):
                matched_cat_code = cat_code
                break
        if matched_cat_code:
            break

    if matched_cat_code:
        meta = get_category_meta(matched_cat_code)
        c_qs = user_expenses.filter(category=matched_cat_code)
        c_total = float(c_qs.aggregate(t=Sum('amount'))['t'] or 0)
        c_count = c_qs.count()
        all_time_total = float(user_expenses.aggregate(t=Sum('amount'))['t'] or 0)
        c_pct = round(c_total / all_time_total * 100, 1) if all_time_total > 0 else 0

        latest = c_qs.order_by('-date', '-time').first()
        latest_text = ""
        if latest:
            latest_text = f"\n• **Latest {meta['name']} purchase:** {format_amount(latest.amount, currency)} at *{latest.place}* ({latest.date.strftime('%b %d, %Y')})"

        reply = (
            f"🏷️ **{meta['name']} Expense Summary:**\n\n"
            f"• **Total Spent on {meta['name']}:** **{format_amount(c_total, currency)}**\n"
            f"• **Transactions:** **{c_count}** entries\n"
            f"• **Share of Total Budget:** <span class='badge bg-primary text-white'>{c_pct}%</span>"
            f"{latest_text}\n\n"
            f"💡 *Ask for 'category wise expense' to see your complete ranked breakdown.*"
        )
        return {
            'reply': reply,
            'intent': 'specific_category_expense',
            'suggestions': ["🏷️ Category Wise Expense", "🏆 Max Category Expense", "💰 Total Expense"]
        }

    # ==========================================================
    # 10. BANK BALANCE & ACCOUNTS
    # ==========================================================
    if ('balance' in msg or 'bank' in msg or 'account' in msg or 'how much money' in msg):
        if not user_accounts.exists():
            return {
                'reply': "You don't have any registered bank accounts yet. You can add one in the **Bank Accounts** tab!",
                'intent': 'bank_balance',
                'suggestions': default_suggestions[:4]
            }

        total_bal = float(user_accounts.aggregate(t=Sum('current_balance'))['t'] or 0)
        lines = [
            f"💳 **Your Registered Bank Accounts & Balances:**",
            f"• **Consolidated Liquid Balance:** **{format_amount(total_bal, currency)}**\n"
        ]

        for acc in user_accounts:
            lines.append(f"• **{acc.bank_name}** ({acc.account_name}): **{format_amount(acc.current_balance, acc.currency or currency)}** `{acc.account_number}`")

        lines.append(f"\n💡 *You can top up funds or link another bank in the Bank Accounts view.*")
        return {
            'reply': "\n".join(lines),
            'intent': 'bank_balance',
            'suggestions': ["💰 Total Expense", "📅 Total Monthly Expense", "🏆 Max Category Expense"]
        }

    # ==========================================================
    # 11. RECENT TRANSACTIONS
    # ==========================================================
    if ('recent' in msg or 'latest' in msg or 'last expense' in msg or 'last transaction' in msg or 'history' in msg):
        recents = user_expenses.order_by('-date', '-time', '-created_at')[:5]
        if not recents:
            return {
                'reply': "No recent expenses logged yet.",
                'intent': 'recent_expenses',
                'suggestions': default_suggestions[:4]
            }

        lines = ["🧾 **Your 5 Most Recent Expense Transactions:**\n"]
        for r in recents:
            meta = get_category_meta(r.category)
            d_str = r.date.strftime('%b %d, %Y')
            lines.append(f"• **{format_amount(r.amount, currency)}** at **{r.place}** ({meta['name']}) on {d_str}")

        lines.append(f"\n💡 *View the Expenses tab for full logs and CSV/PDF export options.*")
        return {
            'reply': "\n".join(lines),
            'intent': 'recent_expenses',
            'suggestions': ["💰 Total Expense", "📅 Total Monthly Expense", "🏷️ Category Wise Expense"]
        }

    # ==========================================================
    # 12. GREETINGS & HELP (DEFAULT / FALLBACK)
    # ==========================================================
    user_display_name = user.first_name or user.username
    greeting_reply = (
        f"👋 Hi **{user_display_name}**! I'm **SpendBot**, your personal financial assistant.\n\n"
        f"I have direct, secure access to **your data only**. Here are some questions you can ask me:\n\n"
        f"• **Total Expense** — *\"What is my total expense?\"*\n"
        f"• **Total Monthly Expense** — *\"What did I spend this month?\"*\n"
        f"• **Qtr Expense** — *\"Show my qtr expense\"* or *\"Q1 / Q2 expense\"*\n"
        f"• **Yearly Expense** — *\"What is my yearly expense?\"*\n"
        f"• **Jan Month Expense** — *\"How much did I spend in Jan?\"*\n"
        f"• **Category Wise Expense** — *\"Show category wise expense\"*\n"
        f"• **Max Month Expense** — *\"Which month had the highest expense?\"*\n"
        f"• **Max Category Expense** — *\"What is my max category expense?\"*\n"
        f"• **Bank Balance** — *\"What is my account balance?\"*\n\n"
        f"Click any of the quick suggestions below or type your question!"
    )
    return {
        'reply': greeting_reply,
        'intent': 'help_or_fallback',
        'suggestions': default_suggestions
    }
