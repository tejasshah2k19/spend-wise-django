import json
import datetime
from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth.models import User
from tracker.models import BankAccount, Expense, Category, UserProfile
from tracker.seed_data import seed_categories, seed_user_demo_data

class SpendWiseTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        seed_categories()
        self.user = User.objects.create_user(
            username='tester@example.com',
            email='tester@example.com',
            password='testpassword123',
            first_name='Test',
            last_name='User'
        )
        self.profile = UserProfile.objects.get(user=self.user)
        self.profile.currency = '$'
        self.profile.save()

        self.account = BankAccount.objects.create(
            user=self.user,
            bank_name='Chase Bank',
            account_name='Checking',
            account_type='checking',
            account_number='**** 1234',
            opening_balance=Decimal('1000.00'),
            current_balance=Decimal('1000.00'),
            currency='$',
            color_theme='card-theme-blue'
        )

    def test_user_registration(self):
        res = self.client.post(
            '/api/auth/register/',
            data=json.dumps({
                'name': 'New Registered User',
                'email': 'brandnew@spendwise.com',
                'password': 'brandnewpassword123',
                'currency': '€'
            }),
            content_type='application/json'
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['user']['email'], 'brandnew@spendwise.com')
        self.assertEqual(data['user']['currency'], '€')

    def test_user_login(self):
        res = self.client.post(
            '/api/auth/login/',
            data=json.dumps({'email': 'tester@example.com', 'password': 'testpassword123'}),
            content_type='application/json'
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['user']['email'], 'tester@example.com')

    def test_account_creation_and_top_up(self):
        self.client.force_login(self.user)
        # Create new account
        res = self.client.post(
            '/api/accounts/',
            data=json.dumps({
                'bankName': 'Capital One',
                'accountName': 'Savings',
                'accountType': 'savings',
                'accountNumber': '**** 5678',
                'openingBalance': 500.00,
                'currency': '$',
                'colorTheme': 'card-theme-emerald'
            }),
            content_type='application/json'
        )
        self.assertEqual(res.status_code, 201)
        acc_data = res.json()['account']
        acc_id = acc_data['id']
        self.assertEqual(acc_data['currentBalance'], 500.00)

        # Top-up / deposit funds
        top_up_res = self.client.post(
            f'/api/accounts/{acc_id}/top-up/',
            data=json.dumps({'amount': 250.00}),
            content_type='application/json'
        )
        self.assertEqual(top_up_res.status_code, 200)
        self.assertEqual(top_up_res.json()['account']['currentBalance'], 750.00)

    def test_expense_logging_and_balance_deduction(self):
        self.client.force_login(self.user)
        initial_balance = self.account.current_balance

        # Log an expense of $150.00
        res = self.client.post(
            '/api/expenses/',
            data=json.dumps({
                'accountId': self.account.id,
                'amount': 150.00,
                'place': 'Whole Foods',
                'purpose': 'Groceries',
                'category': 'groceries',
                'date': '2026-11-20',
                'time': '14:30',
                'paymentMode': 'Debit Card',
                'notes': 'Weekly groceries'
            }),
            content_type='application/json'
        )
        self.assertEqual(res.status_code, 201)
        exp_id = res.json()['expense']['id']

        # Verify account balance deducted in database
        self.account.refresh_from_db()
        self.assertEqual(self.account.current_balance, initial_balance - Decimal('150.00'))

        # Delete expense and verify balance refunded
        del_res = self.client.delete(f'/api/expenses/{exp_id}/')
        self.assertEqual(del_res.status_code, 200)
        self.account.refresh_from_db()
        self.assertEqual(self.account.current_balance, initial_balance)

    def test_csv_export(self):
        self.client.force_login(self.user)
        # Log sample expense
        Expense.objects.create(
            user=self.user,
            account=self.account,
            amount=Decimal('45.00'),
            place='Gas Station',
            purpose='Fuel',
            category='transport',
            date=datetime.date.today()
        )
        res = self.client.get('/api/expenses/export/csv/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res['Content-Type'], 'text/csv')
        self.assertIn('Gas Station', res.content.decode('utf-8'))

    def test_analytics_api(self):
        self.client.force_login(self.user)
        seed_user_demo_data(self.user, force_reset=True)
        res = self.client.get('/api/analytics/?timeframe=monthly&month=10&year=2026')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn('stat1', data)
        self.assertIn('topCategory', data)
        self.assertIn('categoryLeaderboard', data)
        self.assertIn('trendChart', data)
        self.assertIn('crossAccounts', data)

    def test_pdf_report_unauthorized(self):
        # Unauthenticated request must return 401
        res = self.client.get('/api/reports/pdf/?timeframe=monthly')
        self.assertEqual(res.status_code, 401)

    def test_pdf_report_monthly(self):
        self.client.force_login(self.user)
        seed_user_demo_data(self.user, force_reset=True)
        res = self.client.get('/api/reports/pdf/?timeframe=monthly&year=2026&month=10')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res['Content-Type'], 'application/pdf')
        self.assertTrue(res['Content-Disposition'].startswith('attachment; filename="SpendWise_Monthly_Report_'))
        self.assertTrue(res.content.startswith(b'%PDF-'))

    def test_pdf_report_quarterly(self):
        self.client.force_login(self.user)
        seed_user_demo_data(self.user, force_reset=True)
        res = self.client.get('/api/reports/quarterly/pdf/?year=2026&quarter=2')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res['Content-Type'], 'application/pdf')
        self.assertIn('SpendWise_Quarterly_Report_Q2_2026.pdf', res['Content-Disposition'])
        self.assertTrue(res.content.startswith(b'%PDF-'))

    def test_pdf_report_halfyearly(self):
        self.client.force_login(self.user)
        seed_user_demo_data(self.user, force_reset=True)
        res = self.client.get('/api/reports/halfyearly/pdf/?year=2026&half=1')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res['Content-Type'], 'application/pdf')
        self.assertIn('SpendWise_HalfYearly_Report_H1_2026.pdf', res['Content-Disposition'])
        self.assertTrue(res.content.startswith(b'%PDF-'))

    def test_pdf_report_yearly(self):
        self.client.force_login(self.user)
        seed_user_demo_data(self.user, force_reset=True)
        res = self.client.get('/api/reports/yearly/pdf/?year=2026')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res['Content-Type'], 'application/pdf')
        self.assertIn('SpendWise_Annual_Report_2026.pdf', res['Content-Disposition'])
        self.assertTrue(res.content.startswith(b'%PDF-'))

    def test_pdf_report_with_account_filter(self):
        self.client.force_login(self.user)
        seed_user_demo_data(self.user, force_reset=True)
        acc = BankAccount.objects.filter(user=self.user).first()
        res = self.client.get(f'/api/reports/pdf/?timeframe=monthly&year=2026&month=10&accountId={acc.id}')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res['Content-Type'], 'application/pdf')
        self.assertTrue(res.content.startswith(b'%PDF-'))

    # ==========================================
    # CHATBOT TESTS
    # ==========================================

    def test_chat_unauthorized(self):
        res = self.client.post('/api/chat/', data=json.dumps({'message': 'total expense'}), content_type='application/json')
        self.assertEqual(res.status_code, 401)

    def test_chat_empty_message(self):
        self.client.force_login(self.user)
        res = self.client.post('/api/chat/', data=json.dumps({'message': '   '}), content_type='application/json')
        self.assertEqual(res.status_code, 400)

    def test_chat_total_expense(self):
        self.client.force_login(self.user)
        seed_user_demo_data(self.user, force_reset=True)
        res = self.client.post('/api/chat/', data=json.dumps({'message': 'total expense'}), content_type='application/json')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['intent'], 'total_expense')
        self.assertIn('Total Overall Expenses', data['reply'])
        self.assertTrue(len(data['suggestions']) > 0)

    def test_chat_total_monthly_expense(self):
        self.client.force_login(self.user)
        seed_user_demo_data(self.user, force_reset=True)
        res = self.client.post('/api/chat/', data=json.dumps({'message': 'total monthly expense'}), content_type='application/json')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['intent'], 'total_monthly_expense')
        self.assertIn('Total Monthly Expense', data['reply'])

    def test_chat_qtr_expense(self):
        self.client.force_login(self.user)
        seed_user_demo_data(self.user, force_reset=True)
        res = self.client.post('/api/chat/', data=json.dumps({'message': 'qtr expense'}), content_type='application/json')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['intent'], 'qtr_expense')
        self.assertIn('Quarterly Expense', data['reply'])

    def test_chat_yearly_expense(self):
        self.client.force_login(self.user)
        seed_user_demo_data(self.user, force_reset=True)
        res = self.client.post('/api/chat/', data=json.dumps({'message': 'yearly expense'}), content_type='application/json')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['intent'], 'yearly_expense')
        self.assertIn('Yearly / Annual Expense', data['reply'])

    def test_chat_jan_month_expense(self):
        self.client.force_login(self.user)
        seed_user_demo_data(self.user, force_reset=True)
        res = self.client.post('/api/chat/', data=json.dumps({'message': 'jan month expense'}), content_type='application/json')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['intent'], 'specific_month_expense')
        self.assertIn('January', data['reply'])

    def test_chat_category_wise_expense(self):
        self.client.force_login(self.user)
        seed_user_demo_data(self.user, force_reset=True)
        res = self.client.post('/api/chat/', data=json.dumps({'message': 'category wise expense'}), content_type='application/json')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['intent'], 'category_wise_expense')
        self.assertIn('Category-Wise Spending Breakdown', data['reply'])

    def test_chat_max_month_expense(self):
        self.client.force_login(self.user)
        seed_user_demo_data(self.user, force_reset=True)
        res = self.client.post('/api/chat/', data=json.dumps({'message': 'max month expense'}), content_type='application/json')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['intent'], 'max_month_expense')
        self.assertIn('Highest Spending Month', data['reply'])

    def test_chat_max_category_expense(self):
        self.client.force_login(self.user)
        seed_user_demo_data(self.user, force_reset=True)
        res = self.client.post('/api/chat/', data=json.dumps({'message': 'max category expense'}), content_type='application/json')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['intent'], 'max_category_expense')
        self.assertIn('Highest Spending Category', data['reply'])

    def test_chat_user_data_isolation(self):
        # Verify chatbot NEVER returns another user's data
        user_b = User.objects.create_user(username='other_user@test.com', password='password123')
        acc_b = BankAccount.objects.create(
            user=user_b, bank_name='Secret Bank', account_name='Secret Acc', account_number='**** 9999',
            opening_balance=Decimal('50000.00'), current_balance=Decimal('50000.00')
        )
        Expense.objects.create(
            user=user_b, account=acc_b, amount=Decimal('9999.99'), place='Secret Luxury Villa',
            category='housing', date=datetime.date.today()
        )

        # Clear user A's expenses to only a single $12.50 expense
        self.user.expenses.all().delete()
        Expense.objects.create(
            user=self.user, account=self.account, amount=Decimal('12.50'), place='Local Bakery',
            category='food', date=datetime.date.today()
        )

        # Login as user A
        self.client.force_login(self.user)
        res_a = self.client.post('/api/chat/', data=json.dumps({'message': 'total expense'}), content_type='application/json')
        self.assertEqual(res_a.status_code, 200)
        reply_a = res_a.json()['reply']

        # Must see user A's $12.50, and must NOT see user B's $9,999.99 or secret villa
        self.assertIn('12.50', reply_a)
        self.assertNotIn('9,999.99', reply_a)
        self.assertNotIn('Secret', reply_a)

        # Login as user B
        self.client.force_login(user_b)
        res_b = self.client.post('/api/chat/', data=json.dumps({'message': 'total expense'}), content_type='application/json')
        self.assertEqual(res_b.status_code, 200)
        reply_b = res_b.json()['reply']

        # Must see user B's $9,999.99, and must NOT see user A's $12.50
        self.assertIn('9,999.99', reply_b)
        self.assertNotIn('12.50', reply_b)


