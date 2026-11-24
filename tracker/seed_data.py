import datetime
from django.db import transaction
from django.contrib.auth.models import User
from .models import BankAccount, Expense, Category, UserProfile

DEFAULT_CATEGORIES = [
    { 'code': 'food', 'name': 'Food & Dining', 'icon': 'bi-cup-hot', 'color': '#ff6384' },
    { 'code': 'groceries', 'name': 'Groceries & Mart', 'icon': 'bi-cart3', 'color': '#36a2eb' },
    { 'code': 'housing', 'name': 'Housing & Rent', 'icon': 'bi-house-door', 'color': '#ffce56' },
    { 'code': 'bills', 'name': 'Bills & Utilities', 'icon': 'bi-lightning-charge', 'color': '#4bc0c0' },
    { 'code': 'transport', 'name': 'Transport & Fuel', 'icon': 'bi-car-front', 'color': '#9966ff' },
    { 'code': 'shopping', 'name': 'Shopping & Retail', 'icon': 'bi-bag', 'color': '#ff9f40' },
    { 'code': 'entertainment', 'name': 'Entertainment', 'icon': 'bi-controller', 'color': '#e74c3c' },
    { 'code': 'health', 'name': 'Health & Medical', 'icon': 'bi-heart-pulse', 'color': '#2ecc71' },
    { 'code': 'education', 'name': 'Education & Fees', 'icon': 'bi-book', 'color': '#1abc9c' },
    { 'code': 'travel', 'name': 'Travel & Holiday', 'icon': 'bi-airplane', 'color': '#3498db' },
    { 'code': 'fitness', 'name': 'Fitness & Sports', 'icon': 'bi-person-arms-up', 'color': '#9b59b6' },
    { 'code': 'others', 'name': 'Others & Misc', 'icon': 'bi-three-dots', 'color': '#7f8c8d' },
]

def seed_categories():
    for cat in DEFAULT_CATEGORIES:
        Category.objects.update_or_create(
            code=cat['code'],
            defaults={
                'name': cat['name'],
                'icon': cat['icon'],
                'color': cat['color']
            }
        )

def seed_user_demo_data(user, force_reset=False):
    """
    Seeds demo bank accounts and realistic expenses spanning all 12 months for a given user.
    """
    with transaction.atomic():
        seed_categories()

        if force_reset:
            user.expenses.all().delete()
            user.accounts.all().delete()
        elif user.accounts.exists():
            return

        currency = getattr(user.profile, 'currency', '$') if hasattr(user, 'profile') else '$'

        # Create 3 realistic accounts
        acc_chase = BankAccount.objects.create(
            user=user,
            bank_name='Chase Bank',
            account_name='Primary Checking',
            account_type='checking',
            account_number='**** 4892',
            opening_balance=6500.00,
            current_balance=4210.50,
            currency=currency,
            color_theme='card-theme-blue'
        )

        acc_cap_one = BankAccount.objects.create(
            user=user,
            bank_name='Capital One',
            account_name='High Yield Savings',
            account_type='savings',
            account_number='**** 7731',
            opening_balance=12000.00,
            current_balance=10450.00,
            currency=currency,
            color_theme='card-theme-emerald'
        )

        acc_amex = BankAccount.objects.create(
            user=user,
            bank_name='American Express',
            account_name='Gold Rewards Card',
            account_type='credit',
            account_number='**** 2004',
            opening_balance=3000.00,
            current_balance=1845.20,
            currency=currency,
            color_theme='card-theme-purple'
        )

        expense_templates = [
            {'place': 'Starbucks Coffee', 'purpose': 'Morning Latte & Croissant', 'category': 'food', 'amount': 14.50, 'account': acc_chase, 'payment_mode': 'Debit Card'},
            {'place': 'The Olive Bistro', 'purpose': 'Dinner with Team', 'category': 'food', 'amount': 84.00, 'account': acc_amex, 'payment_mode': 'Credit Card'},
            {'place': 'Chipotle Mexican Grill', 'purpose': 'Quick Lunch', 'category': 'food', 'amount': 18.25, 'account': acc_chase, 'payment_mode': 'Debit Card'},
            {'place': 'UberEats Delivery', 'purpose': 'Late Night Dinner', 'category': 'food', 'amount': 36.80, 'account': acc_amex, 'payment_mode': 'Credit Card'},
            {'place': 'Whole Foods Market', 'purpose': 'Weekly Organic Groceries', 'category': 'groceries', 'amount': 142.60, 'account': acc_chase, 'payment_mode': 'Debit Card'},
            {'place': 'Trader Joe\'s', 'purpose': 'Snacks & Pantry Restock', 'category': 'groceries', 'amount': 68.40, 'account': acc_chase, 'payment_mode': 'Debit Card'},
            {'place': 'Costco Wholesale', 'purpose': 'Monthly Bulk Grocery & Household', 'category': 'groceries', 'amount': 215.00, 'account': acc_cap_one, 'payment_mode': 'Debit Card'},
            {'place': 'Avalon Luxury Apartments', 'purpose': 'Monthly Apartment Rent', 'category': 'housing', 'amount': 1250.00, 'account': acc_chase, 'payment_mode': 'NetBanking'},
            {'place': 'Home Depot', 'purpose': 'Appliance Repair & Lighting', 'category': 'housing', 'amount': 95.00, 'account': acc_chase, 'payment_mode': 'Debit Card'},
            {'place': 'ConEdison Electric', 'purpose': 'Electricity & Gas Bill', 'category': 'bills', 'amount': 89.20, 'account': acc_chase, 'payment_mode': 'Auto-Debit'},
            {'place': 'AT&T Mobility', 'purpose': 'Fiber Internet & Phone Bill', 'category': 'bills', 'amount': 110.00, 'account': acc_chase, 'payment_mode': 'Auto-Debit'},
            {'place': 'City Water Works', 'purpose': 'Quarterly Water Utility', 'category': 'bills', 'amount': 54.00, 'account': acc_chase, 'payment_mode': 'Debit Card'},
            {'place': 'Shell Fuel Station', 'purpose': 'Full Tank Premium Gasoline', 'category': 'transport', 'amount': 58.50, 'account': acc_chase, 'payment_mode': 'Debit Card'},
            {'place': 'Uber Technologies', 'purpose': 'Airport Transit Ride', 'category': 'transport', 'amount': 42.00, 'account': acc_amex, 'payment_mode': 'Credit Card'},
            {'place': 'Metro Transit Pass', 'purpose': 'Monthly Commuter Subway Pass', 'category': 'transport', 'amount': 75.00, 'account': acc_chase, 'payment_mode': 'Debit Card'},
            {'place': 'Amazon Prime', 'purpose': 'Wireless Noise-Canceling Headphones', 'category': 'shopping', 'amount': 179.99, 'account': acc_amex, 'payment_mode': 'Credit Card'},
            {'place': 'Nike Store', 'purpose': 'Running Shoes & Sports Apparel', 'category': 'shopping', 'amount': 130.00, 'account': acc_amex, 'payment_mode': 'Credit Card'},
            {'place': 'Zara Fashion', 'purpose': 'Office Casual Wear', 'category': 'shopping', 'amount': 94.50, 'account': acc_amex, 'payment_mode': 'Credit Card'},
            {'place': 'Netflix & Spotify', 'purpose': 'Monthly Streaming Subscriptions', 'category': 'entertainment', 'amount': 32.98, 'account': acc_amex, 'payment_mode': 'Credit Card'},
            {'place': 'AMC Theatres', 'purpose': 'IMAX Movie Tickets & Popcorn', 'category': 'entertainment', 'amount': 45.00, 'account': acc_chase, 'payment_mode': 'Debit Card'},
            {'place': 'Steam Games Store', 'purpose': 'Weekend Gaming Pack', 'category': 'entertainment', 'amount': 59.99, 'account': acc_amex, 'payment_mode': 'Credit Card'},
            {'place': 'CVS Pharmacy', 'purpose': 'Prescriptions & Multivitamins', 'category': 'health', 'amount': 48.30, 'account': acc_chase, 'payment_mode': 'Debit Card'},
            {'place': 'City Dental Clinic', 'purpose': 'Routine Checkup & Cleaning', 'category': 'health', 'amount': 120.00, 'account': acc_cap_one, 'payment_mode': 'Debit Card'},
            {'place': 'Coursera Inc', 'purpose': 'Data Science Specialization', 'category': 'education', 'amount': 49.00, 'account': acc_amex, 'payment_mode': 'Credit Card'},
            {'place': 'O\'Reilly Media', 'purpose': 'Annual Tech Books Subscription', 'category': 'education', 'amount': 199.00, 'account': acc_cap_one, 'payment_mode': 'Credit Card'},
            {'place': 'Delta Air Lines', 'purpose': 'Conference Flight Booking', 'category': 'travel', 'amount': 340.00, 'account': acc_amex, 'payment_mode': 'Credit Card'},
            {'place': 'Marriott Bonvoy', 'purpose': 'Weekend Getaway Stay', 'category': 'travel', 'amount': 280.00, 'account': acc_amex, 'payment_mode': 'Credit Card'},
        ]

        now = datetime.date.today()
        current_year = now.year

        expenses_to_create = []
        for m in range(1, 13):
            count = 3 + (m % 3)
            for i in range(count):
                template = expense_templates[(m * 3 + i) % len(expense_templates)]
                day = min(28, 2 + (i * 6) + (m % 4))
                exp_date = datetime.date(current_year, m, day)
                variance = 1.0 + (((i + m) % 5) - 2) * 0.05
                amount = round(float(template['amount']) * variance, 2)
                exp_time = datetime.time(10 + (i * 2), 30)

                expenses_to_create.append(
                    Expense(
                        user=user,
                        account=template['account'],
                        amount=amount,
                        place=template['place'],
                        purpose=template['purpose'],
                        category=template['category'],
                        date=exp_date,
                        time=exp_time,
                        payment_mode=template['payment_mode'],
                        notes='Verified expense record'
                    )
                )

        Expense.objects.bulk_create(expenses_to_create)
