/**
 * SpendWise - Storage & Data Management Layer (Django + SQLite Database Integrated)
 * Manages server synchronization, REST API calls, CSRF tokens, and in-memory caching
 * for instant, reactive rendering backed by the SQLite database.
 */

const STORAGE_KEYS = {
    USERS: 'spendwise_users',
    CURRENT_USER: 'spendwise_current_user',
    THEME: 'spendwise_theme_preference'
};

const DEFAULT_CATEGORIES = [
    { id: 'food', name: 'Food & Dining', icon: 'bi-cup-hot', color: '#ff6384' },
    { id: 'groceries', name: 'Groceries & Mart', icon: 'bi-cart3', color: '#36a2eb' },
    { id: 'housing', name: 'Housing & Rent', icon: 'bi-house-door', color: '#ffce56' },
    { id: 'bills', name: 'Bills & Utilities', icon: 'bi-lightning-charge', color: '#4bc0c0' },
    { id: 'transport', name: 'Transport & Fuel', icon: 'bi-car-front', color: '#9966ff' },
    { id: 'shopping', name: 'Shopping & Retail', icon: 'bi-bag', color: '#ff9f40' },
    { id: 'entertainment', name: 'Entertainment', icon: 'bi-controller', color: '#e74c3c' },
    { id: 'health', name: 'Health & Medical', icon: 'bi-heart-pulse', color: '#2ecc71' },
    { id: 'education', name: 'Education & Fees', icon: 'bi-book', color: '#1abc9c' },
    { id: 'travel', name: 'Travel & Holiday', icon: 'bi-airplane', color: '#3498db' },
    { id: 'fitness', name: 'Fitness & Sports', icon: 'bi-person-arms-up', color: '#9b59b6' },
    { id: 'others', name: 'Others & Misc', icon: 'bi-three-dots', color: '#7f8c8d' }
];

const ACCOUNT_TYPES = [
    { id: 'savings', label: 'Savings Account', icon: 'bi-piggy-bank' },
    { id: 'checking', label: 'Checking / Salary', icon: 'bi-briefcase' },
    { id: 'credit', label: 'Credit Card', icon: 'bi-credit-card-2-front' },
    { id: 'wallet', label: 'Digital Wallet / UPI', icon: 'bi-phone' },
    { id: 'investment', label: 'Investment / Brokerage', icon: 'bi-graph-up-arrow' },
    { id: 'cash', label: 'Cash in Hand', icon: 'bi-cash-stack' }
];

const CARD_THEMES = [
    { id: 'card-theme-blue', name: 'Solid Royal Blue', class: 'card-theme-blue' },
    { id: 'card-theme-purple', name: 'Solid Cool Indigo', class: 'card-theme-purple' },
    { id: 'card-theme-emerald', name: 'Solid Ocean Teal', class: 'card-theme-emerald' },
    { id: 'card-theme-dark', name: 'Solid Cool Slate', class: 'card-theme-dark' },
    { id: 'card-theme-crimson', name: 'Solid Pacific Cyan', class: 'card-theme-crimson' }
];

function getCsrfToken() {
    const el = document.querySelector('[name=csrfmiddlewaretoken]') || document.querySelector('meta[name="csrf-token"]');
    if (el) return el.value || el.getAttribute('content');
    const match = document.cookie.match(/csrftoken=([\w-]+)/);
    return match ? match[1] : '';
}

async function apiFetch(url, options = {}) {
    const headers = {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCsrfToken(),
        ...(options.headers || {})
    };
    const response = await fetch(url, {
        ...options,
        headers,
        credentials: 'same-origin'
    });
    if (!response.ok) {
        let errData = {};
        try {
            errData = await response.json();
        } catch (_) {}
        const msg = errData.message || errData.error || `Server error (${response.status})`;
        throw new Error(msg);
    }
    return response.json();
}

class StorageManager {
    static _currentUser = null;
    static _accounts = [];
    static _expenses = [];
    static _isInitialized = false;

    // ===== INITIALIZATION & SERVER HYDRATION =====

    static async init() {
        if (this._isInitialized) return;

        // 1. Try reading pre-rendered server payload for 0ms initial render
        const serverScript = document.getElementById('serverData');
        if (serverScript) {
            try {
                const serverData = JSON.parse(serverScript.textContent);
                if (serverData && serverData.isAuthenticated && serverData.user) {
                    this._currentUser = serverData.user;
                    this._accounts = serverData.accounts || [];
                    this._expenses = serverData.expenses || [];
                    this._isInitialized = true;
                    return;
                }
            } catch (err) {
                console.warn('Could not parse server payload:', err);
            }
        }

        // 2. Fetch session from server
        try {
            const authRes = await apiFetch('/api/auth/user/', { method: 'GET' });
            if (authRes && authRes.authenticated && authRes.user) {
                this._currentUser = authRes.user;
                await this.refreshData();
            }
        } catch (e) {
            console.warn('Session check failed:', e);
        }

        this._isInitialized = true;
    }

    static async refreshData() {
        if (!this._currentUser) {
            this._accounts = [];
            this._expenses = [];
            return;
        }
        try {
            const [accRes, expRes] = await Promise.all([
                apiFetch('/api/accounts/', { method: 'GET' }),
                apiFetch('/api/expenses/', { method: 'GET' })
            ]);
            this._accounts = accRes.accounts || [];
            this._expenses = expRes.expenses || [];
        } catch (e) {
            console.error('Error refreshing accounts and expenses from SQLite:', e);
        }
    }

    // ===== USER & AUTHENTICATION =====

    static getCurrentUser() {
        return this._currentUser;
    }

    static setCurrentUser(user) {
        this._currentUser = user;
    }

    static async register(name, email, password, currency = '$') {
        try {
            const res = await apiFetch('/api/auth/register/', {
                method: 'POST',
                body: JSON.stringify({ name, email, password, currency })
            });
            if (res.success && res.user) {
                this._currentUser = res.user;
                await this.refreshData();
                return { success: true, user: res.user };
            }
            return { success: false, message: res.message || 'Registration failed.' };
        } catch (err) {
            return { success: false, message: err.message };
        }
    }

    static async login(email, password) {
        try {
            const res = await apiFetch('/api/auth/login/', {
                method: 'POST',
                body: JSON.stringify({ email, password })
            });
            if (res.success && res.user) {
                this._currentUser = res.user;
                await this.refreshData();
                return { success: true, user: res.user };
            }
            return { success: false, message: res.message || 'Login failed.' };
        } catch (err) {
            return { success: false, message: err.message };
        }
    }

    static async demoLogin() {
        try {
            const res = await apiFetch('/api/auth/demo-login/', { method: 'POST' });
            if (res.success && res.user) {
                this._currentUser = res.user;
                await this.refreshData();
                return { success: true, user: res.user };
            }
            return { success: false, message: res.message || 'Demo login failed.' };
        } catch (err) {
            return { success: false, message: err.message };
        }
    }

    static async logout() {
        try {
            await apiFetch('/api/auth/logout/', { method: 'POST' });
        } catch (_) {}
        this._currentUser = null;
        this._accounts = [];
        this._expenses = [];
        return { success: true };
    }

    static async deleteUser(userId) {
        try {
            await apiFetch('/api/auth/delete/', { method: 'POST' });
        } catch (_) {}
        this._currentUser = null;
        this._accounts = [];
        this._expenses = [];
        return true;
    }

    static async updateTheme(theme) {
        try {
            await apiFetch('/api/auth/theme/', {
                method: 'POST',
                body: JSON.stringify({ theme })
            });
        } catch (_) {}
    }

    // ===== BANK ACCOUNTS MANAGEMENT =====

    static getAccounts(userId) {
        return this._accounts;
    }

    static saveAccounts(userId, accounts) {
        this._accounts = accounts;
    }

    static getAccountById(userId, accountId) {
        const id = String(accountId);
        return this._accounts.find(a => String(a.id) === id) || null;
    }

    static async addAccount(userId, accountData) {
        try {
            const payload = {
                bankName: accountData.bankName,
                accountName: accountData.accountName,
                accountType: accountData.accountType,
                accountNumber: accountData.accountNumber,
                openingBalance: parseFloat(accountData.openingBalance) || 0,
                currency: accountData.currency || '$',
                colorTheme: accountData.colorTheme || 'card-theme-blue'
            };
            const res = await apiFetch('/api/accounts/', {
                method: 'POST',
                body: JSON.stringify(payload)
            });
            if (res.success && res.account) {
                this._accounts.unshift(res.account);
                return res.account;
            }
            throw new Error(res.message || 'Failed to create bank account.');
        } catch (err) {
            console.error('addAccount error:', err);
            throw err;
        }
    }

    static async updateAccount(userId, accountId, updatedData) {
        try {
            const res = await apiFetch(`/api/accounts/${accountId}/`, {
                method: 'PUT',
                body: JSON.stringify(updatedData)
            });
            if (res.success && res.account) {
                const idx = this._accounts.findIndex(a => String(a.id) === String(accountId));
                if (idx !== -1) {
                    this._accounts[idx] = res.account;
                }
                return res.account;
            }
            throw new Error(res.message || 'Failed to update bank account.');
        } catch (err) {
            console.error('updateAccount error:', err);
            throw err;
        }
    }

    static async adjustAccountBalance(userId, accountId, deltaAmount) {
        // Delta amount for top-up
        if (deltaAmount > 0) {
            try {
                const res = await apiFetch(`/api/accounts/${accountId}/top-up/`, {
                    method: 'POST',
                    body: JSON.stringify({ amount: deltaAmount })
                });
                if (res.success && res.account) {
                    const idx = this._accounts.findIndex(a => String(a.id) === String(accountId));
                    if (idx !== -1) {
                        this._accounts[idx] = res.account;
                    }
                    return res.account;
                }
            } catch (err) {
                console.error('adjustAccountBalance error:', err);
                throw err;
            }
        }
        // Local fallback adjustment
        const acc = this.getAccountById(userId, accountId);
        if (acc) {
            acc.currentBalance = Math.round((acc.currentBalance + deltaAmount) * 100) / 100;
        }
        return acc;
    }

    static async deleteAccount(userId, accountId) {
        try {
            await apiFetch(`/api/accounts/${accountId}/`, { method: 'DELETE' });
            this._accounts = this._accounts.filter(a => String(a.id) !== String(accountId));
            this._expenses = this._expenses.filter(e => String(e.accountId) !== String(accountId));
            return true;
        } catch (err) {
            console.error('deleteAccount error:', err);
            throw err;
        }
    }

    // ===== EXPENSES MANAGEMENT =====

    static getExpenses(userId) {
        return this._expenses;
    }

    static saveExpenses(userId, expenses) {
        this._expenses = expenses;
    }

    static getExpenseById(userId, expenseId) {
        const id = String(expenseId);
        return this._expenses.find(e => String(e.id) === id) || null;
    }

    static async addExpense(userId, expenseData) {
        try {
            const res = await apiFetch('/api/expenses/', {
                method: 'POST',
                body: JSON.stringify(expenseData)
            });
            if (res.success && res.expense) {
                this._expenses.unshift(res.expense);
                // Also update local cached account balance
                const acc = this.getAccountById(userId, expenseData.accountId);
                if (acc) {
                    acc.currentBalance = Math.round((acc.currentBalance - parseFloat(expenseData.amount)) * 100) / 100;
                }
                return res.expense;
            }
            throw new Error(res.message || 'Failed to log expense.');
        } catch (err) {
            console.error('addExpense error:', err);
            throw err;
        }
    }

    static async updateExpense(userId, expenseId, updatedData) {
        try {
            const res = await apiFetch(`/api/expenses/${expenseId}/`, {
                method: 'PUT',
                body: JSON.stringify(updatedData)
            });
            if (res.success && res.expense) {
                const idx = this._expenses.findIndex(e => String(e.id) === String(expenseId));
                if (idx !== -1) {
                    this._expenses[idx] = res.expense;
                }
                // Refresh accounts to ensure balances reflect change
                const accRes = await apiFetch('/api/accounts/', { method: 'GET' });
                if (accRes && accRes.accounts) {
                    this._accounts = accRes.accounts;
                }
                return res.expense;
            }
            throw new Error(res.message || 'Failed to update expense.');
        } catch (err) {
            console.error('updateExpense error:', err);
            throw err;
        }
    }

    static async deleteExpense(userId, expenseId) {
        try {
            const exp = this.getExpenseById(userId, expenseId);
            await apiFetch(`/api/expenses/${expenseId}/`, { method: 'DELETE' });
            this._expenses = this._expenses.filter(e => String(e.id) !== String(expenseId));
            if (exp) {
                const acc = this.getAccountById(userId, exp.accountId);
                if (acc) {
                    acc.currentBalance = Math.round((acc.currentBalance + parseFloat(exp.amount)) * 100) / 100;
                }
            }
            return true;
        } catch (err) {
            console.error('deleteExpense error:', err);
            throw err;
        }
    }

    // ===== DEMO SEED DATA =====

    static async seedDemoData(userId, currency = '$') {
        try {
            await apiFetch('/api/demo/reset/', { method: 'POST' });
            await this.refreshData();
        } catch (err) {
            console.error('seedDemoData error:', err);
        }
    }

    static async initializeDemoUserIfEmpty() {
        // Handled automatically by Django backend and seed_demo command
    }
}

// Global exposure
window.StorageManager = StorageManager;
window.DEFAULT_CATEGORIES = DEFAULT_CATEGORIES;
window.ACCOUNT_TYPES = ACCOUNT_TYPES;
window.CARD_THEMES = CARD_THEMES;
