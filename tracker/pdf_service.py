"""
SpendWise - PDF Financial Report Generation Engine
Generates comprehensive, publication-quality PDF reports for:
- Monthly Report
- Quarterly Report
- Half-Yearly Report
- Yearly (Annual) Report
"""

import io
import os
import calendar
import datetime
from decimal import Decimal

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, HRFlowable
)
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from django.db.models import Sum, Count, Q
from .models import Expense, BankAccount, Category, UserProfile
from .seed_data import DEFAULT_CATEGORIES
from .analytics_service import compute_analytics


# ==========================================
# FONT INITIALIZATION & FALLBACK
# ==========================================
FONT_REGULAR = 'Helvetica'
FONT_BOLD = 'Helvetica-Bold'
FONT_OBLIQUE = 'Helvetica-Oblique'

try:
    windows_fonts_dir = os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'Fonts')
    arial_path = os.path.join(windows_fonts_dir, 'arial.ttf')
    arialbd_path = os.path.join(windows_fonts_dir, 'arialbd.ttf')
    if os.path.exists(arial_path) and os.path.exists(arialbd_path):
        pdfmetrics.registerFont(TTFont('AppFont', arial_path))
        pdfmetrics.registerFont(TTFont('AppFont-Bold', arialbd_path))
        FONT_REGULAR = 'AppFont'
        FONT_BOLD = 'AppFont-Bold'
        FONT_OBLIQUE = 'AppFont'
except Exception:
    pass


def clean_currency_symbol(currency):
    """
    Ensures currency symbol is safe to render with the selected font.
    If Helvetica is used and currency is non-Latin (like ₹), fall back to 'Rs.'.
    """
    if FONT_REGULAR == 'Helvetica' and currency and ord(currency[0]) > 255:
        if currency == '₹':
            return 'Rs.'
        return ' '
    return currency or '$'


# ==========================================
# NUMBERED CANVAS (Page X of Y & Headers)
# ==========================================
class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont(FONT_REGULAR, 8)
        self.setFillColor(colors.HexColor('#64748B'))

        # Running header on subsequent pages (page 2+)
        if self._pageNumber > 1:
            self.drawString(36, 756, "SpendWise Expense Tracker — Financial Report")
            self.drawRightString(576, 756, getattr(self, 'report_period_title', ''))
            self.setStrokeColor(colors.HexColor('#CBD5E1'))
            self.setLineWidth(0.5)
            self.line(36, 750, 576, 750)

        # Running footer on every page
        self.setStrokeColor(colors.HexColor('#E2E8F0'))
        self.setLineWidth(0.75)
        self.line(36, 40, 576, 40)

        # Left footer: App & Generation timestamp
        timestamp_str = getattr(self, 'generation_time', datetime.datetime.now().strftime('%b %d, %Y %I:%M %p'))
        self.drawString(36, 28, f"SpendWise • Generated on {timestamp_str}")

        # Right footer: Page numbers
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(576, 28, page_str)

        self.restoreState()


# ==========================================
# PDF GENERATOR FUNCTION
# ==========================================
def generate_expense_pdf_report(user, timeframe='monthly', year=None, month=None, quarter=1, half=1, account_id='all'):
    """
    Builds a PDF financial report in memory and returns a BytesIO buffer.
    
    Args:
        user: Django User instance
        timeframe: 'monthly', 'quarterly', 'halfyearly', or 'yearly'
        year: int (e.g. 2026)
        month: 0-indexed int (0-11 for monthly)
        quarter: 1-4 (for quarterly)
        half: 1-2 (for halfyearly)
        account_id: 'all' or BankAccount pk
    """
    today = datetime.date.today()
    if not year:
        year = today.year
    else:
        year = int(year)

    profile = getattr(user, 'profile', None)
    raw_currency = profile.currency if profile else '$'
    currency = clean_currency_symbol(raw_currency)

    # 1. Fetch Analytics data
    analytics_data = compute_analytics(
        user=user,
        year=year,
        account_id=account_id,
        timeframe=timeframe,
        month=month,
        quarter=quarter,
        half=half
    )

    # 2. Filter the exact expenses queryset
    qs = Expense.objects.filter(user=user, date__year=year).select_related('account')
    selected_account_obj = None
    if account_id and account_id != 'all':
        try:
            acc_pk = int(account_id)
            qs = qs.filter(account_id=acc_pk)
            selected_account_obj = BankAccount.objects.filter(pk=acc_pk, user=user).first()
        except (ValueError, TypeError):
            pass

    # Timeframe filtering for expenses
    period_label = analytics_data.get('periodTitle', '')
    report_type_names = {
        'monthly': 'Monthly Expense Report',
        'quarterly': 'Quarterly Expense Report',
        'halfyearly': 'Half-Yearly Expense Report',
        'yearly': 'Annual Financial Report'
    }
    report_title = report_type_names.get(timeframe, 'Financial Expense Report')

    if timeframe == 'monthly':
        target_month_1based = (int(month) + 1) if month is not None else today.month
        qs = qs.filter(date__month=target_month_1based)
    elif timeframe == 'quarterly':
        q_num = int(quarter) if quarter else 1
        q_months = {1: [1, 2, 3], 2: [4, 5, 6], 3: [7, 8, 9], 4: [10, 11, 12]}.get(q_num, [1, 2, 3])
        qs = qs.filter(date__month__in=q_months)
    elif timeframe == 'halfyearly':
        h_num = int(half) if half else 1
        h_months = [1, 2, 3, 4, 5, 6] if h_num == 1 else [7, 8, 9, 10, 11, 12]
        qs = qs.filter(date__month__in=h_months)
    elif timeframe == 'yearly':
        pass  # full year already filtered

    expenses_list = list(qs.order_by('-date', '-time', '-created_at'))
    total_spent = sum(Decimal(str(e.amount)) for e in expenses_list)
    tx_count = len(expenses_list)

    # 3. Setup document and styles
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=54
    )

    styles = getSampleStyleSheet()
    
    # Custom Palette
    COLOR_PRIMARY = colors.HexColor('#1E293B')      # Slate 800
    COLOR_BRAND = colors.HexColor('#2563EB')        # Blue 600
    COLOR_ACCENT = colors.HexColor('#4F46E5')       # Indigo 600
    COLOR_TEXT = colors.HexColor('#0F172A')         # Slate 900
    COLOR_MUTED = colors.HexColor('#64748B')        # Slate 500
    COLOR_LIGHT = colors.HexColor('#F8FAFC')        # Slate 50
    COLOR_BORDER = colors.HexColor('#E2E8F0')       # Slate 200
    COLOR_SUCCESS = colors.HexColor('#059669')      # Emerald 600
    COLOR_DANGER = colors.HexColor('#DC2626')       # Red 600
    COLOR_CARD_BG = colors.HexColor('#F1F5F9')      # Slate 100

    # Custom Typography Styles
    style_brand = ParagraphStyle(
        'ReportBrand',
        parent=styles['Normal'],
        fontName=FONT_BOLD,
        fontSize=15,
        leading=18,
        textColor=COLOR_BRAND
    )
    style_title = ParagraphStyle(
        'ReportTitle',
        parent=styles['Normal'],
        fontName=FONT_BOLD,
        fontSize=20,
        leading=24,
        textColor=COLOR_PRIMARY
    )
    style_subtitle = ParagraphStyle(
        'ReportSubtitle',
        parent=styles['Normal'],
        fontName=FONT_REGULAR,
        fontSize=11,
        leading=14,
        textColor=COLOR_MUTED
    )
    style_meta_label = ParagraphStyle(
        'MetaLabel',
        parent=styles['Normal'],
        fontName=FONT_BOLD,
        fontSize=8,
        leading=11,
        textColor=COLOR_MUTED
    )
    style_meta_value = ParagraphStyle(
        'MetaValue',
        parent=styles['Normal'],
        fontName=FONT_REGULAR,
        fontSize=9,
        leading=12,
        textColor=COLOR_TEXT
    )
    style_heading = ParagraphStyle(
        'SectionHeading',
        parent=styles['Normal'],
        fontName=FONT_BOLD,
        fontSize=12,
        leading=15,
        textColor=COLOR_PRIMARY
    )
    style_card_title = ParagraphStyle(
        'CardTitle',
        parent=styles['Normal'],
        fontName=FONT_REGULAR,
        fontSize=8,
        leading=10,
        textColor=COLOR_MUTED,
        alignment=1
    )
    style_card_value = ParagraphStyle(
        'CardValue',
        parent=styles['Normal'],
        fontName=FONT_BOLD,
        fontSize=13,
        leading=16,
        textColor=COLOR_PRIMARY,
        alignment=1
    )
    style_table_header = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName=FONT_BOLD,
        fontSize=8,
        leading=10,
        textColor=colors.white
    )
    style_table_header_right = ParagraphStyle(
        'TableHeaderRight',
        parent=styles['Normal'],
        fontName=FONT_BOLD,
        fontSize=8,
        leading=10,
        textColor=colors.white,
        alignment=2
    )
    style_cell = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName=FONT_REGULAR,
        fontSize=8,
        leading=10,
        textColor=COLOR_TEXT
    )
    style_cell_bold = ParagraphStyle(
        'TableCellBold',
        parent=styles['Normal'],
        fontName=FONT_BOLD,
        fontSize=8,
        leading=10,
        textColor=COLOR_TEXT
    )
    style_cell_right = ParagraphStyle(
        'TableCellRight',
        parent=styles['Normal'],
        fontName=FONT_REGULAR,
        fontSize=8,
        leading=10,
        textColor=COLOR_TEXT,
        alignment=2
    )
    style_cell_bold_right = ParagraphStyle(
        'TableCellBoldRight',
        parent=styles['Normal'],
        fontName=FONT_BOLD,
        fontSize=8,
        leading=10,
        textColor=COLOR_TEXT,
        alignment=2
    )
    style_pill = ParagraphStyle(
        'CategoryPill',
        parent=styles['Normal'],
        fontName=FONT_BOLD,
        fontSize=7,
        leading=9,
        textColor=COLOR_ACCENT
    )

    story = []

    # ==========================================
    # 1. HEADER SECTION
    # ==========================================
    header_table_data = [
        [
            Paragraph("SpendWise", style_brand),
            Paragraph(f"<b>STATUS:</b> FINAL STATEMENT", ParagraphStyle('StatusPill', parent=styles['Normal'], fontName=FONT_BOLD, fontSize=8, leading=10, textColor=COLOR_SUCCESS, alignment=2))
        ],
        [
            Paragraph(report_title, style_title),
            Paragraph(f"<b>Period:</b> {period_label}", ParagraphStyle('PeriodTag', parent=styles['Normal'], fontName=FONT_BOLD, fontSize=11, leading=14, textColor=COLOR_PRIMARY, alignment=2))
        ],
        [
            Paragraph("Multi-Bank Expense Tracker & Financial Intelligence", style_subtitle),
            Paragraph(f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}", ParagraphStyle('DateTag', parent=styles['Normal'], fontName=FONT_REGULAR, fontSize=8, leading=10, textColor=COLOR_MUTED, alignment=2))
        ]
    ]

    header_table = Table(header_table_data, colWidths=[360, 180])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
        ('TOPPADDING', (0, 0), (-1, -1), 1),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 10))

    # Divider Line
    story.append(HRFlowable(width="100%", thickness=1.5, color=COLOR_BRAND, spaceBefore=2, spaceAfter=10))

    # ==========================================
    # 2. METADATA INFO PANEL (2x2 grid)
    # ==========================================
    user_name = f"{user.first_name} {user.last_name}".strip() or user.username
    account_filter_label = f"{selected_account_obj.bank_name} - {selected_account_obj.account_name} ({selected_account_obj.account_number})" if selected_account_obj else "All Accounts Combined"

    meta_data = [
        [
            Paragraph("ACCOUNT HOLDER", style_meta_label),
            Paragraph(f"{user_name} &lt;{user.email}&gt;", style_meta_value),
            Paragraph("ACCOUNT SCOPE", style_meta_label),
            Paragraph(account_filter_label, style_meta_value)
        ],
        [
            Paragraph("CURRENCY", style_meta_label),
            Paragraph(f"{currency} ({user_name}'s preferred)", style_meta_value),
            Paragraph("STATEMENT TYPE", style_meta_label),
            Paragraph(f"{timeframe.capitalize()} Aggregation ({year})", style_meta_value)
        ]
    ]
    meta_table = Table(meta_data, colWidths=[100, 170, 100, 170])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), COLOR_CARD_BG),
        ('BOX', (0, 0), (-1, -1), 0.5, COLOR_BORDER),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, COLOR_BORDER),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 12))

    # ==========================================
    # 3. EXECUTIVE KPI CARDS
    # ==========================================
    stat1_val = f"{currency}{total_spent:,.2f}"
    stat2_val = analytics_data.get('stat2', {}).get('value', '—')
    stat2_title = analytics_data.get('stat2', {}).get('title', 'Comparison Metric')
    stat3_val = f"{tx_count} records"

    avg_spend = (total_spent / tx_count) if tx_count > 0 else Decimal('0.00')
    stat4_val = f"{currency}{avg_spend:,.2f}"

    kpi_data = [
        [
            Paragraph("TOTAL PERIOD SPENT", style_card_title),
            Paragraph(stat2_title.upper(), style_card_title),
            Paragraph("TRANSACTION VOLUME", style_card_title),
            Paragraph("AVERAGE / TRANSACTION", style_card_title),
        ],
        [
            Paragraph(f"<font color='#DC2626'>{stat1_val}</font>", style_card_value),
            Paragraph(str(stat2_val), style_card_value),
            Paragraph(stat3_val, style_card_value),
            Paragraph(stat4_val, style_card_value),
        ]
    ]
    kpi_table = Table(kpi_data, colWidths=[135, 135, 135, 135])
    kpi_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), COLOR_LIGHT),
        ('BOX', (0, 0), (-1, -1), 1, COLOR_BORDER),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, COLOR_BORDER),
        ('TOPPADDING', (0, 0), (-1, 0), 6),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 2),
        ('TOPPADDING', (0, 1), (-1, 1), 2),
        ('BOTTOMPADDING', (0, 1), (-1, 1), 6),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 14))

    # ==========================================
    # 4. TOP SPENDING CATEGORY SPOTLIGHT BANNER
    # ==========================================
    top_cat = analytics_data.get('topCategory')
    if top_cat:
        top_name = top_cat.get('name', 'N/A')
        top_amount = float(top_cat.get('total', 0))
        top_pct = top_cat.get('percentage', 0)
        top_cnt = top_cat.get('count', 0)

        spotlight_text = (
            f"<b>TOP SPENDING CATEGORY SPOTLIGHT:</b> Your highest expenditure went to "
            f"<b>{top_name}</b>, totaling <b>{currency}{top_amount:,.2f}</b> across <b>{top_cnt}</b> "
            f"transactions, representing <font color='#DC2626'><b>{top_pct}%</b></font> of your overall spending in this period."
        )
        spotlight_table = Table(
            [[Paragraph(spotlight_text, ParagraphStyle('SpotlightText', parent=styles['Normal'], fontName=FONT_REGULAR, fontSize=8.5, leading=12, textColor=COLOR_PRIMARY))]],
            colWidths=[540]
        )
        spotlight_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#FEF3C7')),  # Warm amber
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#F59E0B')),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ]))
        story.append(spotlight_table)
        story.append(Spacer(1, 14))

    # ==========================================
    # 5. CATEGORY BREAKDOWN TABLE
    # ==========================================
    story.append(Paragraph("Category Spending Breakdown (Ranked Highest to Lowest)", style_heading))
    story.append(Spacer(1, 6))

    cat_leaderboard = analytics_data.get('categoryLeaderboard', [])
    if cat_leaderboard:
        cat_table_data = [
            [
                Paragraph("Rank", style_table_header),
                Paragraph("Category", style_table_header),
                Paragraph("Transactions", style_table_header_right),
                Paragraph("Total Spent", style_table_header_right),
                Paragraph("Share of Budget", style_table_header_right),
            ]
        ]

        for idx, cat_item in enumerate(cat_leaderboard, start=1):
            tot = float(cat_item.get('total', 0))
            cnt = cat_item.get('count', 0)
            pct = cat_item.get('percentage', 0)
            cat_table_data.append([
                Paragraph(f"#{idx}", style_cell_bold),
                Paragraph(f"<b>{cat_item.get('name', '')}</b>", style_cell),
                Paragraph(f"{cnt} txns", style_cell_right),
                Paragraph(f"{currency}{tot:,.2f}", style_cell_bold_right),
                Paragraph(f"{pct}%", style_cell_right),
            ])

        # Summary total row
        cat_table_data.append([
            Paragraph("Total", style_cell_bold),
            Paragraph("<b>All Categories Combined</b>", style_cell_bold),
            Paragraph(f"<b>{tx_count} txns</b>", style_cell_bold_right),
            Paragraph(f"<b>{currency}{total_spent:,.2f}</b>", style_cell_bold_right),
            Paragraph("<b>100.0%</b>", style_cell_bold_right),
        ])

        cat_table = Table(cat_table_data, colWidths=[45, 195, 90, 110, 100])
        cat_style = [
            ('BACKGROUND', (0, 0), (-1, 0), COLOR_PRIMARY),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('BOX', (0, 0), (-1, -1), 0.75, COLOR_BORDER),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, COLOR_BORDER),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BACKGROUND', (0, -1), (-1, -1), COLOR_CARD_BG),
        ]
        # Alternating row colors
        for r in range(1, len(cat_table_data) - 1):
            if r % 2 == 0:
                cat_style.append(('BACKGROUND', (0, r), (-1, r), COLOR_LIGHT))
        cat_table.setStyle(TableStyle(cat_style))
        story.append(cat_table)
    else:
        story.append(Paragraph("<i>No category spending data recorded for this timeframe.</i>", style_cell))

    story.append(Spacer(1, 14))

    # ==========================================
    # 6. BANK ACCOUNTS BREAKDOWN TABLE
    # ==========================================
    accounts = BankAccount.objects.filter(user=user)
    if accounts.exists():
        story.append(Paragraph("Bank Accounts Balance & Period Spending", style_heading))
        story.append(Spacer(1, 6))

        acc_table_data = [
            [
                Paragraph("Bank Name", style_table_header),
                Paragraph("Account Name & Type", style_table_header),
                Paragraph("Account Number", style_table_header),
                Paragraph("Available Balance", style_table_header_right),
                Paragraph("Period Outflow", style_table_header_right),
            ]
        ]

        total_bal = Decimal('0.00')
        for acc in accounts:
            acc_outflow = sum(Decimal(str(e.amount)) for e in expenses_list if e.account_id == acc.id)
            total_bal += acc.current_balance
            acc_table_data.append([
                Paragraph(f"<b>{acc.bank_name}</b>", style_cell),
                Paragraph(f"{acc.account_name} ({acc.get_account_type_display()})", style_cell),
                Paragraph(acc.account_number, style_cell),
                Paragraph(f"{currency}{acc.current_balance:,.2f}", style_cell_right),
                Paragraph(f"{currency}{acc_outflow:,.2f}", style_cell_bold_right),
            ])

        acc_table_data.append([
            Paragraph("Total", style_cell_bold),
            Paragraph(f"<b>{accounts.count()} Registered Accounts</b>", style_cell_bold),
            Paragraph("—", style_cell),
            Paragraph(f"<b>{currency}{total_bal:,.2f}</b>", style_cell_bold_right),
            Paragraph(f"<b>{currency}{total_spent:,.2f}</b>", style_cell_bold_right),
        ])

        acc_table = Table(acc_table_data, colWidths=[110, 150, 80, 100, 100])
        acc_style = [
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#334155')),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('BOX', (0, 0), (-1, -1), 0.75, COLOR_BORDER),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, COLOR_BORDER),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BACKGROUND', (0, -1), (-1, -1), COLOR_CARD_BG),
        ]
        for r in range(1, len(acc_table_data) - 1):
            if r % 2 == 0:
                acc_style.append(('BACKGROUND', (0, r), (-1, r), COLOR_LIGHT))
        acc_table.setStyle(TableStyle(acc_style))
        story.append(acc_table)
        story.append(Spacer(1, 14))

    # ==========================================
    # 7. ITEMIZED EXPENSE TRANSACTIONS LOG
    # ==========================================
    story.append(Paragraph(f"Itemized Transactions Log ({tx_count} records)", style_heading))
    story.append(Spacer(1, 6))

    if expenses_list:
        tx_table_data = [
            [
                Paragraph("Date", style_table_header),
                Paragraph("Place / Merchant", style_table_header),
                Paragraph("Category", style_table_header),
                Paragraph("Account", style_table_header),
                Paragraph("Payment Method", style_table_header),
                Paragraph("Amount", style_table_header_right),
            ]
        ]

        cat_names_dict = {c['code']: c['name'] for c in DEFAULT_CATEGORIES}

        for exp in expenses_list:
            d_str = exp.date.strftime('%Y-%m-%d')
            c_name = cat_names_dict.get(exp.category, exp.category.capitalize())
            b_name = f"{exp.account.bank_name}"
            amt = Decimal(str(exp.amount))
            place_str = exp.place
            if exp.purpose:
                place_str += f" <font color='#64748B'>({exp.purpose})</font>"

            tx_table_data.append([
                Paragraph(d_str, style_cell),
                Paragraph(place_str, style_cell),
                Paragraph(c_name, style_cell),
                Paragraph(b_name, style_cell),
                Paragraph(exp.payment_mode or '—', style_cell),
                Paragraph(f"{currency}{amt:,.2f}", style_cell_bold_right),
            ])

        # Grand total row at bottom
        tx_table_data.append([
            Paragraph("Total", style_cell_bold),
            Paragraph(f"<b>Grand Total ({tx_count} transactions)</b>", style_cell_bold),
            Paragraph("—", style_cell),
            Paragraph("—", style_cell),
            Paragraph("—", style_cell),
            Paragraph(f"<b>{currency}{total_spent:,.2f}</b>", style_cell_bold_right),
        ])

        tx_table = Table(
            tx_table_data,
            colWidths=[65, 145, 95, 85, 75, 75],
            repeatRows=1
        )
        tx_style = [
            ('BACKGROUND', (0, 0), (-1, 0), COLOR_PRIMARY),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('LEFTPADDING', (0, 0), (-1, -1), 5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 5),
            ('BOX', (0, 0), (-1, -1), 0.75, COLOR_BORDER),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, COLOR_BORDER),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BACKGROUND', (0, -1), (-1, -1), COLOR_CARD_BG),
        ]
        for r in range(1, len(tx_table_data) - 1):
            if r % 2 == 0:
                tx_style.append(('BACKGROUND', (0, r), (-1, r), COLOR_LIGHT))
        tx_table.setStyle(TableStyle(tx_style))
        story.append(tx_table)
    else:
        empty_box = Table(
            [[Paragraph("<b>No expense transactions found</b> for the selected timeframe and account filter.", style_cell)]],
            colWidths=[540]
        )
        empty_box.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), COLOR_LIGHT),
            ('BOX', (0, 0), (-1, -1), 0.5, COLOR_BORDER),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ]))
        story.append(empty_box)

    # 4. Build Document using NumberedCanvas
    def canvas_maker(*args, **kwargs):
        c = NumberedCanvas(*args, **kwargs)
        c.report_period_title = period_label
        c.generation_time = datetime.datetime.now().strftime('%b %d, %Y %I:%M %p')
        return c

    doc.build(story, canvasmaker=canvas_maker)
    buffer.seek(0)
    return buffer
