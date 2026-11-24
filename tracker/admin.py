from django.contrib import admin
from .models import UserProfile, BankAccount, Category, Expense


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'currency', 'theme', 'created_at')
    search_fields = ('user__username', 'user__email')


@admin.register(BankAccount)
class BankAccountAdmin(admin.ModelAdmin):
    list_display = ('bank_name', 'account_name', 'user', 'account_type', 'account_number', 'current_balance', 'currency')
    list_filter = ('account_type', 'currency', 'bank_name')
    search_fields = ('bank_name', 'account_name', 'account_number', 'user__username')


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'icon', 'color')
    search_fields = ('name', 'code')


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ('place', 'amount', 'category', 'account', 'user', 'date', 'payment_mode')
    list_filter = ('category', 'payment_mode', 'date', 'account')
    search_fields = ('place', 'purpose', 'notes', 'user__username')
    date_hierarchy = 'date'
