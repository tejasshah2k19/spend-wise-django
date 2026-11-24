import datetime
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    currency = models.CharField(max_length=10, default='$')
    theme = models.CharField(max_length=10, default='light')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} Profile ({self.currency})"


@receiver(post_save, sender=User)
def create_or_save_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)
    else:
        if hasattr(instance, 'profile'):
            instance.profile.save()


class BankAccount(models.Model):
    ACCOUNT_TYPE_CHOICES = [
        ('savings', 'Savings Account'),
        ('checking', 'Checking / Salary'),
        ('credit', 'Credit Card'),
        ('wallet', 'Digital Wallet / UPI'),
        ('investment', 'Investment / Brokerage'),
        ('cash', 'Cash in Hand'),
    ]

    CARD_THEME_CHOICES = [
        ('card-theme-blue', 'Solid Royal Blue'),
        ('card-theme-purple', 'Solid Cool Indigo'),
        ('card-theme-emerald', 'Solid Ocean Teal'),
        ('card-theme-dark', 'Solid Cool Slate'),
        ('card-theme-crimson', 'Solid Pacific Cyan'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='accounts')
    bank_name = models.CharField(max_length=100)
    account_name = models.CharField(max_length=100)
    account_type = models.CharField(max_length=30, choices=ACCOUNT_TYPE_CHOICES, default='savings')
    account_number = models.CharField(max_length=30)
    opening_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    current_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    currency = models.CharField(max_length=10, default='$')
    color_theme = models.CharField(max_length=30, choices=CARD_THEME_CHOICES, default='card-theme-blue')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.bank_name} - {self.account_name} ({self.account_number})"

    def to_dict(self):
        return {
            'id': self.id,
            'userId': self.user_id,
            'bankName': self.bank_name,
            'accountName': self.account_name,
            'accountType': self.account_type,
            'accountNumber': self.account_number,
            'openingBalance': float(self.opening_balance),
            'currentBalance': float(self.current_balance),
            'currency': self.currency,
            'colorTheme': self.color_theme,
            'createdAt': self.created_at.isoformat() if self.created_at else '',
        }


class Category(models.Model):
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    icon = models.CharField(max_length=50, default='bi-tag')
    color = models.CharField(max_length=30, default='#4f46e5')

    class Meta:
        verbose_name_plural = 'Categories'
        ordering = ['name']

    def __str__(self):
        return self.name

    def to_dict(self):
        return {
            'id': self.code,
            'name': self.name,
            'icon': self.icon,
            'color': self.color,
        }


class Expense(models.Model):
    PAYMENT_MODE_CHOICES = [
        ('Debit Card', 'Debit Card'),
        ('Credit Card', 'Credit Card'),
        ('UPI / Online', 'UPI / Online'),
        ('NetBanking', 'NetBanking / Wire'),
        ('Auto-Debit', 'Auto-Debit / Mandate'),
        ('Cash', 'Cash'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='expenses')
    account = models.ForeignKey(BankAccount, on_delete=models.CASCADE, related_name='expenses')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    place = models.CharField(max_length=200)
    purpose = models.CharField(max_length=300, blank=True, default='')
    category = models.CharField(max_length=50, default='others')
    date = models.DateField()
    time = models.TimeField(default=datetime.time(12, 0))
    payment_mode = models.CharField(max_length=50, choices=PAYMENT_MODE_CHOICES, default='Debit Card')
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-time', '-created_at']

    def __str__(self):
        return f"{self.place} - {self.amount} ({self.date})"

    def to_dict(self):
        return {
            'id': self.id,
            'userId': self.user_id,
            'accountId': self.account_id,
            'accountName': f"{self.account.bank_name} - {self.account.account_name}",
            'accountNumber': self.account.account_number,
            'amount': float(self.amount),
            'place': self.place,
            'purpose': self.purpose,
            'category': self.category,
            'date': self.date.strftime('%Y-%m-%d') if self.date else '',
            'time': self.time.strftime('%H:%M') if self.time else '12:00',
            'paymentMode': self.payment_mode,
            'notes': self.notes,
            'createdAt': self.created_at.isoformat() if self.created_at else '',
        }
