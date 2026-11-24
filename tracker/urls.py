from django.urls import path
from . import views

urlpatterns = [
    # Main Dashboard Page
    path('', views.index, name='index'),

    # Auth API
    path('api/auth/user/', views.api_current_user, name='api_current_user'),
    path('api/auth/register/', views.api_register, name='api_register'),
    path('api/auth/login/', views.api_login, name='api_login'),
    path('api/auth/demo-login/', views.api_demo_login, name='api_demo_login'),
    path('api/auth/logout/', views.api_logout, name='api_logout'),
    path('api/auth/delete/', views.api_delete_user, name='api_delete_user'),
    path('api/auth/theme/', views.api_update_theme, name='api_update_theme'),

    # Bank Accounts API
    path('api/accounts/', views.api_accounts, name='api_accounts'),
    path('api/accounts/<int:pk>/', views.api_account_detail, name='api_account_detail'),
    path('api/accounts/<int:pk>/top-up/', views.api_account_top_up, name='api_account_top_up'),

    # Expenses API
    path('api/expenses/', views.api_expenses, name='api_expenses'),
    path('api/expenses/<int:pk>/', views.api_expense_detail, name='api_expense_detail'),
    path('api/expenses/export/csv/', views.api_export_expenses_csv, name='api_export_expenses_csv'),

    # Analytics API
    path('api/analytics/', views.api_analytics, name='api_analytics'),

    # Reports API (PDF format: Monthly, Quarterly, Half-Yearly, Yearly)
    path('api/reports/pdf/', views.api_download_pdf_report, name='api_download_pdf_report'),
    path('api/reports/monthly/pdf/', views.api_download_pdf_report, {'timeframe': 'monthly'}, name='api_download_monthly_pdf'),
    path('api/reports/quarterly/pdf/', views.api_download_pdf_report, {'timeframe': 'quarterly'}, name='api_download_quarterly_pdf'),
    path('api/reports/halfyearly/pdf/', views.api_download_pdf_report, {'timeframe': 'halfyearly'}, name='api_download_halfyearly_pdf'),
    path('api/reports/yearly/pdf/', views.api_download_pdf_report, {'timeframe': 'yearly'}, name='api_download_yearly_pdf'),

    # Financial Assistant Chatbot API
    path('api/chat/', views.api_chat, name='api_chat'),

    # Seed Demo / Reference Data
    path('api/demo/reset/', views.api_demo_reset, name='api_demo_reset'),
    path('api/categories/', views.api_categories, name='api_categories'),
]
