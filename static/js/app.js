/**
 * SpendWise - Core Application Controller
 * Handles UI views, Authentication, Modals, CRUD operations for Accounts & Expenses,
 * Dynamic filtering (All vs Individual Accounts), and Chart.js rendering for Analytics.
 */

// Application State
const AppState = {
    currentUser: null,
    currentView: 'dashboard', // 'dashboard' | 'accounts' | 'expenses' | 'analytics'
    selectedAccountFilter: 'all', // 'all' or specific accountId
    selectedYear: new Date().getFullYear(),
    
    // Analytics view state
    analyticsTimeframe: 'monthly', // 'monthly' | 'quarterly' | 'halfyearly' | 'yearly'
    selectedMonth: new Date().getMonth(),
    selectedQuarter: 1,
    selectedHalf: 1,

    // Chart instances for cleanup
    charts: {
        dashboardTrend: null,
        dashboardCategory: null,
        analyticsTrend: null,
        analyticsCategory: null,
        analyticsAccount: null
    }
};

// ==========================================
// INITIALIZATION
// ==========================================
document.addEventListener('DOMContentLoaded', async () => {
    // 1. Register Event Listeners immediately to handle forms & buttons
    setupEventListeners();

    // 2. Initialize Theme
    initTheme();

    // 3. Initialize StorageManager with Django backend & SQLite session
    try {
        await StorageManager.init();
    } catch (e) {
        console.warn('Init storage error:', e);
    }

    // 4. Check Session
    const user = StorageManager.getCurrentUser();
    if (user) {
        AppState.currentUser = user;
        showAppShell();
        renderActiveView();
    } else {
        showAuthView('login');
    }
});

// ==========================================
// THEME MANAGEMENT
// ==========================================
function initTheme() {
    const savedTheme = (AppState.currentUser && AppState.currentUser.theme) || localStorage.getItem(STORAGE_KEYS.THEME) || 'light';
    document.documentElement.setAttribute('data-theme', savedTheme);
    updateThemeToggleBtn(savedTheme);
}

function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme') || 'light';
    const next = current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem(STORAGE_KEYS.THEME, next);
    StorageManager.updateTheme(next);
    updateThemeToggleBtn(next);

    // Re-render active charts with updated theme colors
    if (AppState.currentView === 'dashboard') {
        renderDashboardCharts();
    } else if (AppState.currentView === 'analytics') {
        renderAnalyticsView();
    }
}

function updateThemeToggleBtn(theme) {
    const btn = document.getElementById('themeToggleBtn');
    if (!btn) return;
    if (theme === 'dark') {
        btn.innerHTML = '<i class="bi bi-sun-fill text-warning"></i>';
        btn.title = 'Switch to Light Mode';
    } else {
        btn.innerHTML = '<i class="bi bi-moon-stars-fill text-secondary"></i>';
        btn.title = 'Switch to Dark Mode';
    }
}

// ==========================================
// VIEW SWITCHING & NAVIGATION
// ==========================================
function showAuthView(mode = 'login') {
    document.getElementById('appNavigation').classList.add('d-none');
    document.getElementById('mainContentArea').classList.add('d-none');
    document.getElementById('authArea').classList.remove('d-none');

    const botContainer = document.getElementById('spendBotContainer');
    if (botContainer) botContainer.classList.add('d-none');

    const loginCard = document.getElementById('loginCard');
    const registerCard = document.getElementById('registerCard');

    if (mode === 'register') {
        loginCard.classList.add('d-none');
        registerCard.classList.remove('d-none');
    } else {
        registerCard.classList.add('d-none');
        loginCard.classList.remove('d-none');
    }
}

function showAppShell() {
    document.getElementById('authArea').classList.add('d-none');
    document.getElementById('appNavigation').classList.remove('d-none');
    document.getElementById('mainContentArea').classList.remove('d-none');

    const botContainer = document.getElementById('spendBotContainer');
    if (botContainer) botContainer.classList.remove('d-none');

    // Update User Name and Currency in navbar
    const user = AppState.currentUser;
    const nameEl = document.getElementById('navUserName');
    if (nameEl) nameEl.textContent = user.name || 'User';

    // Populate Account Filter dropdown in navbar
    populateNavbarAccountFilter();
}

function navigateTo(viewName) {
    AppState.currentView = viewName;

    // Update nav links
    document.querySelectorAll('.navbar-nav .nav-link').forEach(link => {
        if (link.getAttribute('data-view') === viewName) {
            link.classList.add('active');
        } else {
            link.classList.remove('active');
        }
    });

    // Hide all view containers
    document.querySelectorAll('.view-section').forEach(sec => sec.classList.add('d-none'));

    // Show target view container
    const target = document.getElementById(`view-${viewName}`);
    if (target) {
        target.classList.remove('d-none');
    }

    renderActiveView();
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

function renderActiveView() {
    if (!AppState.currentUser) return;

    switch (AppState.currentView) {
        case 'dashboard':
            renderDashboardView();
            break;
        case 'accounts':
            renderAccountsView();
            break;
        case 'expenses':
            renderExpensesView();
            break;
        case 'analytics':
            renderAnalyticsView();
            break;
    }
}

// ==========================================
// NAVBAR ACCOUNT FILTER
// ==========================================
function populateNavbarAccountFilter() {
    const select = document.getElementById('globalAccountSelector');
    if (!select) return;

    const accounts = StorageManager.getAccounts(AppState.currentUser.id);
    let optionsHtml = '<option value="all">💳 All Accounts (Combined)</option>';

    accounts.forEach(acc => {
        const isSelected = AppState.selectedAccountFilter === acc.id ? 'selected' : '';
        optionsHtml += `<option value="${acc.id}" ${isSelected}>🏦 ${acc.bankName} - ${acc.accountName} (${acc.currency}${acc.currentBalance.toLocaleString('en-US', { minimumFractionDigits: 2 })})</option>`;
    });

    select.innerHTML = optionsHtml;
}

// ==========================================
// 1. DASHBOARD VIEW
// ==========================================
function renderDashboardView() {
    const userId = AppState.currentUser.id;
    const currency = AppState.currentUser.currency || '$';
    const filterAccId = AppState.selectedAccountFilter;

    const allAccounts = StorageManager.getAccounts(userId);
    const allExpenses = StorageManager.getExpenses(userId);

    // Calculate Totals based on current filter
    let displayBalance = 0;
    let displayExpenses = 0;
    let activeAccountName = 'All Bank Accounts';

    const totalBalanceAll = allAccounts.reduce((sum, a) => sum + (parseFloat(a.currentBalance) || 0), 0);
    const totalExpensesAll = allExpenses.reduce((sum, e) => sum + (parseFloat(e.amount) || 0), 0);

    if (filterAccId === 'all') {
        displayBalance = totalBalanceAll;
        displayExpenses = totalExpensesAll;
    } else {
        const selectedAcc = allAccounts.find(a => a.id === filterAccId);
        if (selectedAcc) {
            displayBalance = selectedAcc.currentBalance;
            activeAccountName = `${selectedAcc.bankName} (${selectedAcc.accountName})`;
        }
        const accExpenses = allExpenses.filter(e => e.accountId === filterAccId);
        displayExpenses = accExpenses.reduce((sum, e) => sum + (parseFloat(e.amount) || 0), 0);
    }

    // Update Stat Cards on Dashboard
    document.getElementById('dashTotalBalance').textContent = `${currency}${displayBalance.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    document.getElementById('dashTotalExpenses').textContent = `${currency}${displayExpenses.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    document.getElementById('dashTotalBalanceAll').textContent = `${currency}${totalBalanceAll.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    document.getElementById('dashTotalExpensesAll').textContent = `${currency}${totalExpensesAll.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    document.getElementById('dashActiveAccountLabel').textContent = activeAccountName;

    // Monthly category breakdown to identify top category this month
    const currentYear = new Date().getFullYear();
    const currentMonth = new Date().getMonth();
    const monthlyStats = AnalyticsEngine.getMonthlyAnalysis(userId, filterAccId, currentYear, currentMonth);

    const topCatEl = document.getElementById('dashTopCategoryName');
    const topCatAmtEl = document.getElementById('dashTopCategoryAmount');
    if (monthlyStats.topCategory) {
        topCatEl.textContent = monthlyStats.topCategory.name;
        topCatAmtEl.textContent = `${currency}${monthlyStats.topCategory.total.toLocaleString('en-US', { minimumFractionDigits: 2 })} (${monthlyStats.topCategory.percentage}% of month)`;
    } else {
        topCatEl.textContent = 'None yet';
        topCatAmtEl.textContent = 'No expenses this month';
    }

    // Render Bank Accounts Carousel / Cards
    renderDashboardAccountCards(allAccounts);

    // Render Recent Expenses Table
    renderDashboardRecentExpenses(filterAccId);

    // Render Charts
    renderDashboardCharts();
}

function renderDashboardAccountCards(accounts) {
    const container = document.getElementById('dashboardAccountCardsList');
    if (!container) return;

    if (accounts.length === 0) {
        container.innerHTML = `
            <div class="col-12">
                <div class="card p-4 text-center border-dashed">
                    <i class="bi bi-wallet2 fs-1 text-muted mb-2"></i>
                    <h5>No Bank Accounts Added Yet</h5>
                    <p class="text-secondary mb-3">Add your first bank account to start tracking expenses across multiple banks.</p>
                    <div>
                        <button class="btn btn-primary" onclick="openAddAccountModal()">
                            <i class="bi bi-plus-circle me-1"></i> Add Bank Account
                        </button>
                    </div>
                </div>
            </div>
        `;
        return;
    }

    let html = '';
    accounts.forEach(acc => {
        const typeInfo = ACCOUNT_TYPES.find(t => t.id === acc.accountType) || { label: 'Bank Account', icon: 'bi-bank' };
        const isCurrentFilter = AppState.selectedAccountFilter === acc.id;

        // Calculate expenses for this individual account
        const expenses = StorageManager.getExpenses(AppState.currentUser.id).filter(e => e.accountId === acc.id);
        const totalSpent = expenses.reduce((sum, e) => sum + (parseFloat(e.amount) || 0), 0);

        html += `
            <div class="col-12 col-md-6 col-lg-4 mb-3">
                <div class="bank-card ${acc.colorTheme || 'card-theme-blue'} ${isCurrentFilter ? 'ring-active' : ''}">
                    <div class="d-flex justify-content-between align-items-start">
                        <div>
                            <span class="badge bg-white text-dark bg-opacity-75 mb-1 px-2 py-1">
                                <i class="${typeInfo.icon} me-1"></i> ${typeInfo.label}
                            </span>
                            <h5 class="mb-0 text-white fw-bold">${escapeHtml(acc.bankName)}</h5>
                            <small class="text-white-50">${escapeHtml(acc.accountName)}</small>
                        </div>
                        <div class="d-flex align-items-center gap-2">
                            <div class="card-chip"></div>
                            <div class="dropdown">
                                <button class="btn btn-sm btn-link text-white text-opacity-75 p-0" type="button" data-bs-toggle="dropdown" aria-expanded="false" title="Account Options" style="font-size: 1.25rem; text-decoration: none;">
                                    <i class="bi bi-three-dots-vertical"></i>
                                </button>
                                <ul class="dropdown-menu dropdown-menu-end shadow-sm border">
                                    <li><a class="dropdown-item" href="#" onclick="openTopUpModal('${acc.id}')"><i class="bi bi-plus-lg me-2 text-success"></i>Add Funds</a></li>
                                    <li><a class="dropdown-item" href="#" onclick="openEditAccountModal('${acc.id}')"><i class="bi bi-pencil me-2 text-secondary"></i>Edit Account</a></li>
                                    <li><hr class="dropdown-divider"></li>
                                    <li><a class="dropdown-item text-danger" href="#" onclick="confirmDeleteAccount('${acc.id}')"><i class="bi bi-trash3 me-2"></i>Remove Bank Account</a></li>
                                </ul>
                            </div>
                        </div>
                    </div>

                    <div class="my-3">
                        <div class="text-white-50 small mb-1">Available Balance</div>
                        <div class="fs-3 fw-bold text-white">
                            ${acc.currency || '$'}${acc.currentBalance.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                        </div>
                    </div>

                    <div class="d-flex justify-content-between align-items-end pt-2 border-top border-white border-opacity-10">
                        <div>
                            <small class="text-white-50 d-block">Account / Card</small>
                            <span class="font-monospace fw-semibold text-white">${escapeHtml(acc.accountNumber || '**** ****')}</span>
                        </div>
                        <div class="text-end">
                            <small class="text-white-50 d-block">Total Spent</small>
                            <span class="fw-bold text-white">${acc.currency || '$'}${totalSpent.toLocaleString('en-US', { minimumFractionDigits: 2 })}</span>
                        </div>
                    </div>
                </div>
            </div>
        `;
    });

    // Also add a quick "+ Add Account" card
    html += `
        <div class="col-12 col-md-6 col-lg-4 mb-3">
            <div class="card h-100 d-flex flex-column justify-content-center align-items-center text-center p-4 border-dashed cursor-pointer card-hover" onclick="openAddAccountModal()" style="min-height: 195px; border-style: dashed !important; border-width: 2px !important;">
                <div class="stat-icon purple mb-2">
                    <i class="bi bi-plus-lg fs-3"></i>
                </div>
                <h6 class="fw-bold mb-1">Add Another Bank</h6>
                <small class="text-secondary">Track Savings, Credit Card, or Checking</small>
            </div>
        </div>
    `;

    container.innerHTML = html;
}

function renderDashboardRecentExpenses(filterAccId) {
    const tableBody = document.getElementById('dashRecentExpensesTableBody');
    if (!tableBody) return;

    const userId = AppState.currentUser.id;
    let expenses = StorageManager.getExpenses(userId);

    if (filterAccId !== 'all') {
        expenses = expenses.filter(e => e.accountId === filterAccId);
    }

    const recent = expenses.slice(0, 7);

    if (recent.length === 0) {
        tableBody.innerHTML = `
            <tr>
                <td colspan="6" class="text-center py-4 text-muted">
                    <i class="bi bi-receipt fs-3 d-block mb-1"></i>
                    No expenses recorded for this selection.
                </td>
            </tr>
        `;
        return;
    }

    const accountsMap = {};
    StorageManager.getAccounts(userId).forEach(a => { accountsMap[a.id] = a; });

    let html = '';
    recent.forEach(exp => {
        const cat = DEFAULT_CATEGORIES.find(c => c.id === exp.category) || { name: 'Others', icon: 'bi-tag', color: '#6c757d' };
        const acc = accountsMap[exp.accountId] || { bankName: 'Unknown', currency: '$' };

        html += `
            <tr>
                <td>
                    <div class="d-flex align-items-center">
                        <div class="rounded-circle d-flex align-items-center justify-content-center me-2" style="width: 36px; height: 36px; background-color: ${cat.color}20; color: ${cat.color};">
                            <i class="${cat.icon}"></i>
                        </div>
                        <div>
                            <div class="fw-semibold">${escapeHtml(exp.place)}</div>
                            <small class="text-muted">${escapeHtml(exp.purpose || 'No description')}</small>
                        </div>
                    </div>
                </td>
                <td>
                    <span class="category-badge" style="background-color: ${cat.color}15; color: ${cat.color};">
                        <i class="${cat.icon}"></i> ${cat.name}
                    </span>
                </td>
                <td>
                    <span class="account-tag">
                        <i class="bi bi-bank me-1"></i> ${escapeHtml(acc.bankName)}
                    </span>
                </td>
                <td>
                    <div class="small fw-medium">${formatDate(exp.date)}</div>
                    <small class="text-muted">${exp.time || ''}</small>
                </td>
                <td class="fw-bold text-danger text-end">
                    -${acc.currency || '$'}${parseFloat(exp.amount).toLocaleString('en-US', { minimumFractionDigits: 2 })}
                </td>
                <td class="text-end">
                    <button class="btn btn-sm btn-outline-secondary me-1" onclick="openEditExpenseModal('${exp.id}')" title="Edit">
                        <i class="bi bi-pencil"></i>
                    </button>
                    <button class="btn btn-sm btn-outline-danger" onclick="confirmDeleteExpense('${exp.id}')" title="Delete">
                        <i class="bi bi-trash"></i>
                    </button>
                </td>
            </tr>
        `;
    });

    tableBody.innerHTML = html;
}

function renderDashboardCharts() {
    const userId = AppState.currentUser.id;
    const filterAccId = AppState.selectedAccountFilter;
    const currentYear = new Date().getFullYear();

    // 1. Monthly trend
    const monthlyStats = AnalyticsEngine.getMonthlyAnalysis(userId, filterAccId, currentYear);
    const trendCtx = document.getElementById('dashTrendChart');

    if (trendCtx) {
        if (AppState.charts.dashboardTrend) {
            AppState.charts.dashboardTrend.destroy();
        }

        const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
        const gridColor = isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.06)';
        const textColor = isDark ? '#94a3b8' : '#64748b';

        AppState.charts.dashboardTrend = new Chart(trendCtx, {
            type: 'bar',
            data: {
                labels: monthlyStats.labels,
                datasets: [{
                    label: `Monthly Spending (${currentYear})`,
                    data: monthlyStats.monthlyTotals,
                    backgroundColor: 'rgba(79, 70, 229, 0.75)',
                    hoverBackgroundColor: '#4f46e5',
                    borderRadius: 6
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false }
                },
                scales: {
                    x: { grid: { display: false }, ticks: { color: textColor } },
                    y: { grid: { color: gridColor }, ticks: { color: textColor } }
                }
            }
        });
    }

    // 2. Category Donut
    const expenses = AnalyticsEngine.getFilteredExpenses(userId, filterAccId, currentYear);
    const catBreakdown = AnalyticsEngine.getCategoryBreakdown(expenses);
    const catCtx = document.getElementById('dashCategoryChart');

    if (catCtx) {
        if (AppState.charts.dashboardCategory) {
            AppState.charts.dashboardCategory.destroy();
        }

        const labels = catBreakdown.categories.map(c => c.name);
        const data = catBreakdown.categories.map(c => c.total);
        const colors = catBreakdown.categories.map(c => c.color);

        AppState.charts.dashboardCategory = new Chart(catCtx, {
            type: 'doughnut',
            data: {
                labels: labels.length ? labels : ['No Expenses'],
                datasets: [{
                    data: data.length ? data : [1],
                    backgroundColor: colors.length ? colors : ['#e2e8f0'],
                    borderWidth: 2,
                    borderColor: document.documentElement.getAttribute('data-theme') === 'dark' ? '#141d2e' : '#ffffff'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            boxWidth: 12,
                            padding: 10,
                            color: document.documentElement.getAttribute('data-theme') === 'dark' ? '#94a3b8' : '#64748b'
                        }
                    }
                },
                cutout: '70%'
            }
        });
    }
}

// ==========================================
// 2. BANK ACCOUNTS VIEW
// ==========================================
function renderAccountsView() {
    const userId = AppState.currentUser.id;
    const currency = AppState.currentUser.currency || '$';
    const breakdown = AnalyticsEngine.getAccountWiseBreakdown(userId);

    // Summary Cards
    document.getElementById('accTotalLiquidBalance').textContent = `${currency}${breakdown.totalBalanceAll.toLocaleString('en-US', { minimumFractionDigits: 2 })}`;
    document.getElementById('accTotalSpentCombined').textContent = `${currency}${breakdown.totalSpentAll.toLocaleString('en-US', { minimumFractionDigits: 2 })}`;
    document.getElementById('accActiveCount').textContent = breakdown.accounts.length;

    const listContainer = document.getElementById('accountsDetailedList');
    if (!listContainer) return;

    if (breakdown.accounts.length === 0) {
        listContainer.innerHTML = `
            <div class="col-12">
                <div class="empty-state card">
                    <i class="bi bi-bank2 empty-state-icon"></i>
                    <h4>No Bank Accounts Configured</h4>
                    <p class="text-secondary mb-3">Add your checking, savings, credit cards, or digital wallets to track balances and transactions.</p>
                    <div>
                        <button class="btn btn-primary px-4 py-2" onclick="openAddAccountModal()">
                            <i class="bi bi-plus-circle me-1"></i> Add Your First Account
                        </button>
                    </div>
                </div>
            </div>
        `;
        return;
    }

    let html = '';
    breakdown.accounts.forEach(acc => {
        const typeInfo = ACCOUNT_TYPES.find(t => t.id === acc.accountType) || { label: 'Bank Account', icon: 'bi-bank' };

        html += `
            <div class="col-12 col-md-6 col-lg-4 mb-4">
                <div class="card h-100 card-hover">
                    <div class="bank-card ${acc.colorTheme || 'card-theme-blue'} rounded-top rounded-0" style="min-height: 160px;">
                        <div class="d-flex justify-content-between align-items-start">
                            <div>
                                <span class="badge bg-white text-dark bg-opacity-75 mb-1 px-2 py-1">
                                    <i class="${typeInfo.icon} me-1"></i> ${typeInfo.label}
                                </span>
                                <h5 class="mb-0 text-white fw-bold">${escapeHtml(acc.bankName)}</h5>
                                <small class="text-white-50">${escapeHtml(acc.accountName)}</small>
                            </div>
                            <div class="card-chip"></div>
                        </div>

                        <div class="d-flex justify-content-between align-items-end mt-3">
                            <div>
                                <small class="text-white-50 d-block">Account Number</small>
                                <span class="font-monospace fw-semibold text-white">${escapeHtml(acc.accountNumber)}</span>
                            </div>
                            <div class="text-end">
                                <small class="text-white-50 d-block">Current Balance</small>
                                <span class="fs-4 fw-bold text-white">${acc.currency}${acc.currentBalance.toLocaleString('en-US', { minimumFractionDigits: 2 })}</span>
                            </div>
                        </div>
                    </div>

                    <div class="card-body">
                        <div class="d-flex justify-content-between py-2 border-bottom border-light-subtle">
                            <span class="text-secondary"><i class="bi bi-credit-card-2-front me-2"></i>Total Spent</span>
                            <span class="fw-bold text-danger">${acc.currency}${acc.totalSpent.toLocaleString('en-US', { minimumFractionDigits: 2 })}</span>
                        </div>
                        <div class="d-flex justify-content-between py-2 border-bottom border-light-subtle">
                            <span class="text-secondary"><i class="bi bi-receipt me-2"></i>Expenses Logged</span>
                            <span class="fw-semibold">${acc.transactionCount} transactions</span>
                        </div>
                        <div class="d-flex justify-content-between py-2">
                            <span class="text-secondary"><i class="bi bi-shield-check me-2"></i>Status</span>
                            <span class="badge bg-success-subtle text-success">Active & Synced</span>
                        </div>
                    </div>

                    <div class="card-footer bg-transparent d-flex justify-content-between pt-0 pb-3 border-0">
                        <button class="btn btn-sm btn-outline-success" onclick="openTopUpModal('${acc.id}')">
                            <i class="bi bi-plus-lg me-1"></i> Add Funds / Income
                        </button>
                        <div>
                            <button class="btn btn-sm btn-outline-secondary me-1" onclick="openEditAccountModal('${acc.id}')" title="Edit Account">
                                <i class="bi bi-pencil"></i>
                            </button>
                            <button class="btn btn-sm btn-outline-danger" onclick="confirmDeleteAccount('${acc.id}')" title="Delete Account">
                                <i class="bi bi-trash"></i>
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
    });

    listContainer.innerHTML = html;
}

// ==========================================
// 3. EXPENSES VIEW (MANAGEMENT & FILTERING)
// ==========================================
function renderExpensesView() {
    const userId = AppState.currentUser.id;
    const accounts = StorageManager.getAccounts(userId);
    let expenses = StorageManager.getExpenses(userId);

    // Populate Account Filter dropdown on Expenses page
    const accFilterSelect = document.getElementById('expenseAccountFilter');
    if (accFilterSelect && accFilterSelect.options.length <= 1) {
        let accOptions = '<option value="all">All Accounts</option>';
        accounts.forEach(a => {
            accOptions += `<option value="${a.id}">${escapeHtml(a.bankName)} - ${escapeHtml(a.accountName)}</option>`;
        });
        accFilterSelect.innerHTML = accOptions;
    }

    // Populate Category Filter dropdown
    const catFilterSelect = document.getElementById('expenseCategoryFilter');
    if (catFilterSelect && catFilterSelect.options.length <= 1) {
        let catOptions = '<option value="all">All Categories</option>';
        DEFAULT_CATEGORIES.forEach(c => {
            catOptions += `<option value="${c.id}">${c.name}</option>`;
        });
        catFilterSelect.innerHTML = catOptions;
    }

    // Apply Active Filters
    const selectedAcc = document.getElementById('expenseAccountFilter')?.value || 'all';
    const selectedCat = document.getElementById('expenseCategoryFilter')?.value || 'all';
    const searchQuery = document.getElementById('expenseSearchInput')?.value.trim().toLowerCase() || '';
    const dateFrom = document.getElementById('expenseDateFrom')?.value || '';
    const dateTo = document.getElementById('expenseDateTo')?.value || '';

    if (selectedAcc !== 'all') {
        expenses = expenses.filter(e => e.accountId === selectedAcc);
    }
    if (selectedCat !== 'all') {
        expenses = expenses.filter(e => e.category === selectedCat);
    }
    if (searchQuery) {
        expenses = expenses.filter(e => 
            (e.place && e.place.toLowerCase().includes(searchQuery)) ||
            (e.purpose && e.purpose.toLowerCase().includes(searchQuery)) ||
            (e.notes && e.notes.toLowerCase().includes(searchQuery))
        );
    }
    if (dateFrom) {
        expenses = expenses.filter(e => e.date >= dateFrom);
    }
    if (dateTo) {
        expenses = expenses.filter(e => e.date <= dateTo);
    }

    // Render stats bar on expenses view
    const totalFilteredAmount = expenses.reduce((sum, e) => sum + (parseFloat(e.amount) || 0), 0);
    const countFiltered = expenses.length;
    const currency = AppState.currentUser.currency || '$';

    document.getElementById('expensesFilteredTotal').textContent = `${currency}${totalFilteredAmount.toLocaleString('en-US', { minimumFractionDigits: 2 })}`;
    document.getElementById('expensesFilteredCount').textContent = countFiltered;

    // Render Table
    const tableBody = document.getElementById('expensesTableBody');
    if (!tableBody) return;

    if (expenses.length === 0) {
        tableBody.innerHTML = `
            <tr>
                <td colspan="7" class="text-center py-5 text-muted">
                    <i class="bi bi-search fs-2 d-block mb-2"></i>
                    No expenses match your current filters.
                    <div class="mt-2">
                        <button class="btn btn-sm btn-outline-primary" onclick="resetExpenseFilters()">Clear All Filters</button>
                    </div>
                </td>
            </tr>
        `;
        return;
    }

    const accountsMap = {};
    accounts.forEach(a => { accountsMap[a.id] = a; });

    let html = '';
    expenses.forEach(exp => {
        const cat = DEFAULT_CATEGORIES.find(c => c.id === exp.category) || { name: 'Others', icon: 'bi-tag', color: '#6c757d' };
        const acc = accountsMap[exp.accountId] || { bankName: 'Unknown', currency: '$' };

        html += `
            <tr>
                <td>
                    <div class="fw-semibold">${formatDate(exp.date)}</div>
                    <small class="text-muted"><i class="bi bi-clock me-1"></i>${exp.time || '12:00'}</small>
                </td>
                <td>
                    <div class="fw-bold">${escapeHtml(exp.place)}</div>
                    <div class="small text-secondary"><i class="bi bi-geo-alt me-1"></i>Merchant / Payee</div>
                </td>
                <td>
                    <div class="text-truncate" style="max-width: 200px;" title="${escapeHtml(exp.purpose || 'N/A')}">
                        ${escapeHtml(exp.purpose || '—')}
                    </div>
                    ${exp.paymentMode ? `<span class="badge bg-light text-dark border small mt-1">${escapeHtml(exp.paymentMode)}</span>` : ''}
                </td>
                <td>
                    <span class="category-badge" style="background-color: ${cat.color}15; color: ${cat.color};">
                        <i class="${cat.icon}"></i> ${cat.name}
                    </span>
                </td>
                <td>
                    <span class="account-tag">
                        <i class="bi bi-bank me-1"></i> ${escapeHtml(acc.bankName)}
                    </span>
                </td>
                <td class="text-end fw-bold text-danger fs-6">
                    -${acc.currency || '$'}${parseFloat(exp.amount).toLocaleString('en-US', { minimumFractionDigits: 2 })}
                </td>
                <td class="text-end">
                    <button class="btn btn-sm btn-outline-secondary me-1" onclick="openEditExpenseModal('${exp.id}')" title="Edit">
                        <i class="bi bi-pencil"></i>
                    </button>
                    <button class="btn btn-sm btn-outline-danger" onclick="confirmDeleteExpense('${exp.id}')" title="Delete">
                        <i class="bi bi-trash"></i>
                    </button>
                </td>
            </tr>
        `;
    });

    tableBody.innerHTML = html;
}

function resetExpenseFilters() {
    if (document.getElementById('expenseAccountFilter')) document.getElementById('expenseAccountFilter').value = 'all';
    if (document.getElementById('expenseCategoryFilter')) document.getElementById('expenseCategoryFilter').value = 'all';
    if (document.getElementById('expenseSearchInput')) document.getElementById('expenseSearchInput').value = '';
    if (document.getElementById('expenseDateFrom')) document.getElementById('expenseDateFrom').value = '';
    if (document.getElementById('expenseDateTo')) document.getElementById('expenseDateTo').value = '';
    renderExpensesView();
}

// ==========================================
// 4. ANALYTICS & INSIGHTS VIEW
// (Monthly, Quarterly, Half-Yearly, Yearly)
// ==========================================
function renderAnalyticsView() {
    const userId = AppState.currentUser.id;
    const currency = AppState.currentUser.currency || '$';
    const accountId = AppState.selectedAccountFilter;
    const year = AppState.selectedYear;

    // Populate Year selector
    populateAnalyticsYearDropdown();

    // Populate Account Filter for Analytics
    populateAnalyticsAccountDropdown();

    const timeframe = AppState.analyticsTimeframe;

    // Hide all timeframe sub-controls and show current
    document.querySelectorAll('.timeframe-subcontrols').forEach(el => el.classList.add('d-none'));
    const subctrl = document.getElementById(`subctrl-${timeframe}`);
    if (subctrl) subctrl.classList.remove('d-none');

    // Update active tab buttons
    document.querySelectorAll('#analyticsTimeframeTabs .nav-link').forEach(btn => {
        if (btn.getAttribute('data-timeframe') === timeframe) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });

    let stats;
    let trendChartLabels = [];
    let trendChartData = [];
    let trendChartLabel = '';
    let categoryBreakdown = null;

    if (timeframe === 'monthly') {
        const monthSelect = document.getElementById('analyticsMonthSelect');
        if (monthSelect && !monthSelect.dataset.synced) {
            monthSelect.value = String(AppState.selectedMonth);
            monthSelect.dataset.synced = 'true';
        }
        const targetMonth = monthSelect ? parseInt(monthSelect.value, 10) : AppState.selectedMonth;
        stats = AnalyticsEngine.getMonthlyAnalysis(userId, accountId, year, targetMonth);

        trendChartLabels = stats.labels;
        trendChartData = stats.monthlyTotals;
        trendChartLabel = `Monthly Spending for ${year}`;
        categoryBreakdown = stats.categoryBreakdown;

        // Stat Card 1
        document.getElementById('analyticsStat1Title').textContent = `Total in ${stats.selectedMonthName}`;
        document.getElementById('analyticsStat1Val').textContent = `${currency}${stats.selectedMonthTotal.toLocaleString('en-US', { minimumFractionDigits: 2 })}`;
        
        // Stat Card 2
        document.getElementById('analyticsStat2Title').textContent = `Month-over-Month Change`;
        const changeSign = stats.monthOverMonthChange > 0 ? '+' : '';
        const changeClass = stats.monthOverMonthChange > 0 ? 'text-danger' : 'text-success';
        document.getElementById('analyticsStat2Val').innerHTML = `<span class="${changeClass}">${changeSign}${stats.monthOverMonthChange}%</span> <small class="text-muted fs-6">vs ${stats.prevMonthName}</small>`;

        // Stat Card 3
        document.getElementById('analyticsStat3Title').textContent = `Transactions in ${stats.selectedMonthName}`;
        document.getElementById('analyticsStat3Val').textContent = `${stats.selectedMonthCount} entries`;

        const activeViewPdfDesc = document.getElementById('activeViewPdfDesc');
        if (activeViewPdfDesc) activeViewPdfDesc.textContent = `Monthly (${stats.selectedMonthName} ${year})`;

    } else if (timeframe === 'quarterly') {
        const quarterSelect = document.getElementById('analyticsQuarterSelect');
        if (quarterSelect && !quarterSelect.dataset.synced) {
            quarterSelect.value = String(AppState.selectedQuarter);
            quarterSelect.dataset.synced = 'true';
        }
        const targetQuarter = quarterSelect ? parseInt(quarterSelect.value, 10) : AppState.selectedQuarter;
        stats = AnalyticsEngine.getQuarterlyAnalysis(userId, accountId, year, targetQuarter);

        trendChartLabels = stats.quarters.map(q => q.label);
        trendChartData = stats.quarters.map(q => q.total);
        trendChartLabel = `Quarterly Spending (${year})`;
        categoryBreakdown = stats.categoryBreakdown;

        // Stat Card 1
        document.getElementById('analyticsStat1Title').textContent = `Total in ${stats.activeQuarter.short}`;
        document.getElementById('analyticsStat1Val').textContent = `${currency}${stats.activeQuarter.total.toLocaleString('en-US', { minimumFractionDigits: 2 })}`;

        // Stat Card 2
        document.getElementById('analyticsStat2Title').textContent = `Highest Spending Quarter`;
        document.getElementById('analyticsStat2Val').textContent = `${stats.highestQuarter.short} (${currency}${stats.highestQuarter.total.toLocaleString('en-US', { minimumFractionDigits: 2 })})`;

        // Stat Card 3
        document.getElementById('analyticsStat3Title').textContent = `Quarter Transactions`;
        document.getElementById('analyticsStat3Val').textContent = `${stats.activeQuarter.count} entries`;

        const activeViewPdfDesc = document.getElementById('activeViewPdfDesc');
        if (activeViewPdfDesc) activeViewPdfDesc.textContent = `Quarterly (${stats.activeQuarter.short} ${year})`;

    } else if (timeframe === 'halfyearly') {
        const halfSelect = document.getElementById('analyticsHalfSelect');
        if (halfSelect && !halfSelect.dataset.synced) {
            halfSelect.value = String(AppState.selectedHalf);
            halfSelect.dataset.synced = 'true';
        }
        const targetHalf = halfSelect ? parseInt(halfSelect.value, 10) : AppState.selectedHalf;
        stats = AnalyticsEngine.getHalfYearlyAnalysis(userId, accountId, year, targetHalf);

        trendChartLabels = stats.halves.map(h => h.label);
        trendChartData = stats.halves.map(h => h.total);
        trendChartLabel = `Half-Yearly Spending (${year})`;
        categoryBreakdown = stats.categoryBreakdown;

        // Stat Card 1
        document.getElementById('analyticsStat1Title').textContent = `Total in ${stats.activeHalf.short}`;
        document.getElementById('analyticsStat1Val').textContent = `${currency}${stats.activeHalf.total.toLocaleString('en-US', { minimumFractionDigits: 2 })}`;

        // Stat Card 2
        document.getElementById('analyticsStat2Title').textContent = `Annual Share (H1 vs H2)`;
        document.getElementById('analyticsStat2Val').textContent = `H1: ${stats.h1Share}% | H2: ${stats.h2Share}%`;

        // Stat Card 3
        document.getElementById('analyticsStat3Title').textContent = `Half-Year Transactions`;
        document.getElementById('analyticsStat3Val').textContent = `${stats.activeHalf.count} entries`;

        const activeViewPdfDesc = document.getElementById('activeViewPdfDesc');
        if (activeViewPdfDesc) activeViewPdfDesc.textContent = `Half-Yearly (${stats.activeHalf.short} ${year})`;

    } else if (timeframe === 'yearly') {
        stats = AnalyticsEngine.getYearlyAnalysis(userId, accountId, year);

        trendChartLabels = stats.monthlyLabels;
        trendChartData = stats.monthlyTotals;
        trendChartLabel = `All 12 Months of ${year}`;
        categoryBreakdown = stats.categoryBreakdown;

        // Stat Card 1
        document.getElementById('analyticsStat1Title').textContent = `Total Spent in ${year}`;
        document.getElementById('analyticsStat1Val').textContent = `${currency}${stats.totalExpense.toLocaleString('en-US', { minimumFractionDigits: 2 })}`;

        // Stat Card 2
        document.getElementById('analyticsStat2Title').textContent = `Peak Spending Month`;
        document.getElementById('analyticsStat2Val').textContent = `${stats.peakMonthName} (${currency}${stats.peakMonthAmount.toLocaleString('en-US', { minimumFractionDigits: 2 })})`;

        // Stat Card 3
        document.getElementById('analyticsStat3Title').textContent = `Average Monthly Spend`;
        document.getElementById('analyticsStat3Val').textContent = `${currency}${stats.avgMonthlySpend.toLocaleString('en-US', { minimumFractionDigits: 2 })}/mo`;

        const activeViewPdfDesc = document.getElementById('activeViewPdfDesc');
        if (activeViewPdfDesc) activeViewPdfDesc.textContent = `Annual (${year})`;
    }

    // ==========================================
    // TOP CATEGORY SPOTLIGHT & RANKING TABLE
    // ==========================================
    renderTopCategorySpotlight(categoryBreakdown, currency, timeframe);
    renderCategoryRankingTable(categoryBreakdown, currency);

    // ==========================================
    // RENDER CHARTS
    // ==========================================
    renderAnalyticsCharts(trendChartLabels, trendChartData, trendChartLabel, categoryBreakdown);
}

function renderTopCategorySpotlight(categoryBreakdown, currency, timeframe) {
    const spotlightContainer = document.getElementById('topCategorySpotlight');
    if (!spotlightContainer) return;

    const topCat = categoryBreakdown ? categoryBreakdown.topCategory : null;

    if (!topCat) {
        spotlightContainer.innerHTML = `
            <div class="d-flex align-items-center">
                <div class="trophy-badge me-3" style="background: #cbd5e1;">
                    <i class="bi bi-info-circle text-white"></i>
                </div>
                <div>
                    <h5 class="fw-bold mb-1">No Spending Data Found</h5>
                    <p class="text-secondary mb-0">Record expenses in this timeframe to see where most of your money goes.</p>
                </div>
            </div>
        `;
        return;
    }

    spotlightContainer.innerHTML = `
        <div class="row align-items-center">
            <div class="col-12 col-md-8 d-flex align-items-center mb-3 mb-md-0">
                <div class="trophy-badge me-3 flex-shrink-0">
                    <i class="bi bi-trophy-fill"></i>
                </div>
                <div>
                    <div class="badge bg-warning text-dark fw-bold mb-1 px-2 py-1">
                        <i class="bi bi-fire me-1"></i> Top Spending Category (${timeframe.toUpperCase()})
                    </div>
                    <h3 class="fw-bold mb-1 d-flex align-items-center">
                        <span class="rounded-circle d-inline-flex align-items-center justify-content-center me-2" style="width: 32px; height: 32px; background-color: ${topCat.color}25; color: ${topCat.color};">
                            <i class="${topCat.icon}"></i>
                        </span>
                        ${escapeHtml(topCat.name)}
                    </h3>
                    <p class="text-secondary mb-0">
                        You spent <strong>${currency}${topCat.total.toLocaleString('en-US', { minimumFractionDigits: 2 })}</strong> across <strong>${topCat.count}</strong> transactions, which accounts for <span class="badge bg-danger fs-6">${topCat.percentage}%</span> of your entire expenses in this period.
                    </p>
                </div>
            </div>
            <div class="col-12 col-md-4 text-md-end">
                <div class="p-3 bg-white bg-opacity-50 rounded-3 border">
                    <small class="text-muted d-block">Average per transaction</small>
                    <span class="fs-4 fw-bold text-dark">${currency}${topCat.average.toLocaleString('en-US', { minimumFractionDigits: 2 })}</span>
                </div>
            </div>
        </div>
    `;
}

function renderCategoryRankingTable(categoryBreakdown, currency) {
    const tableBody = document.getElementById('categoryRankingTableBody');
    if (!tableBody) return;

    if (!categoryBreakdown || categoryBreakdown.categories.length === 0) {
        tableBody.innerHTML = `
            <tr>
                <td colspan="5" class="text-center py-4 text-muted">
                    No category breakdown available for this timeframe.
                </td>
            </tr>
        `;
        return;
    }

    let html = '';
    categoryBreakdown.categories.forEach((cat, index) => {
        const isTop = index === 0;
        html += `
            <tr class="${isTop ? 'table-warning bg-opacity-25' : ''}">
                <td style="width: 50px;" class="fw-bold text-center">
                    ${isTop ? '<i class="bi bi-trophy-fill text-warning fs-5"></i>' : `#${index + 1}`}
                </td>
                <td>
                    <div class="d-flex align-items-center">
                        <div class="rounded-circle d-flex align-items-center justify-content-center me-2 flex-shrink-0" style="width: 34px; height: 34px; background-color: ${cat.color}20; color: ${cat.color};">
                            <i class="${cat.icon}"></i>
                        </div>
                        <div>
                            <span class="fw-bold">${escapeHtml(cat.name)}</span>
                            ${isTop ? '<span class="badge bg-danger ms-2">Most Expensive</span>' : ''}
                        </div>
                    </div>
                </td>
                <td style="min-width: 150px;">
                    <div class="d-flex justify-content-between small mb-1">
                        <span>Share of spend</span>
                        <span class="fw-bold">${cat.percentage}%</span>
                    </div>
                    <div class="rank-progress">
                        <div class="progress-bar" style="width: ${cat.percentage}%; background-color: ${cat.color};"></div>
                    </div>
                </td>
                <td class="text-center">
                    <span class="badge bg-light text-dark border">${cat.count} txns</span>
                </td>
                <td class="text-end fw-bold text-danger fs-6">
                    ${currency}${cat.total.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                </td>
            </tr>
        `;
    });

    tableBody.innerHTML = html;
}

function renderAnalyticsCharts(labels, data, chartLabel, categoryBreakdown) {
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    const gridColor = isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.06)';
    const textColor = isDark ? '#94a3b8' : '#64748b';

    // 1. Timeframe Trend Chart
    const trendCtx = document.getElementById('analyticsTrendChart');
    if (trendCtx) {
        if (AppState.charts.analyticsTrend) {
            AppState.charts.analyticsTrend.destroy();
        }

        AppState.charts.analyticsTrend = new Chart(trendCtx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: chartLabel,
                    data: data,
                    backgroundColor: 'rgba(79, 70, 229, 0.8)',
                    hoverBackgroundColor: '#4f46e5',
                    borderRadius: 6
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        labels: { color: textColor }
                    }
                },
                scales: {
                    x: { grid: { display: false }, ticks: { color: textColor } },
                    y: { grid: { color: gridColor }, ticks: { color: textColor } }
                }
            }
        });
    }

    // 2. Category Donut Chart
    const catCtx = document.getElementById('analyticsCategoryChart');
    if (catCtx) {
        if (AppState.charts.analyticsCategory) {
            AppState.charts.analyticsCategory.destroy();
        }

        const catLabels = categoryBreakdown ? categoryBreakdown.categories.map(c => c.name) : [];
        const catData = categoryBreakdown ? categoryBreakdown.categories.map(c => c.total) : [];
        const catColors = categoryBreakdown ? categoryBreakdown.categories.map(c => c.color) : [];

        AppState.charts.analyticsCategory = new Chart(catCtx, {
            type: 'doughnut',
            data: {
                labels: catLabels.length ? catLabels : ['No Data'],
                datasets: [{
                    data: catData.length ? catData : [1],
                    backgroundColor: catColors.length ? catColors : ['#e2e8f0'],
                    borderWidth: 2,
                    borderColor: isDark ? '#141d2e' : '#ffffff'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'right',
                        labels: {
                            boxWidth: 12,
                            padding: 12,
                            color: textColor
                        }
                    }
                },
                cutout: '65%'
            }
        });
    }

    // 3. Account-wise Breakdown Bar Chart
    const accCtx = document.getElementById('analyticsAccountChart');
    if (accCtx) {
        if (AppState.charts.analyticsAccount) {
            AppState.charts.analyticsAccount.destroy();
        }

        const breakdown = AnalyticsEngine.getAccountWiseBreakdown(AppState.currentUser.id);
        const accNames = breakdown.accounts.map(a => a.bankName);
        const balances = breakdown.accounts.map(a => a.currentBalance);
        const expenses = breakdown.accounts.map(a => a.totalSpent);

        AppState.charts.analyticsAccount = new Chart(accCtx, {
            type: 'bar',
            data: {
                labels: accNames,
                datasets: [
                    {
                        label: 'Current Balance',
                        data: balances,
                        backgroundColor: '#10b981',
                        borderRadius: 6
                    },
                    {
                        label: 'Total Expenses',
                        data: expenses,
                        backgroundColor: '#ef4444',
                        borderRadius: 6
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'top',
                        labels: { color: textColor }
                    }
                },
                scales: {
                    x: { grid: { display: false }, ticks: { color: textColor } },
                    y: { grid: { color: gridColor }, ticks: { color: textColor } }
                }
            }
        });
    }
}

function populateAnalyticsYearDropdown() {
    const select = document.getElementById('analyticsYearSelect');
    if (!select) return;

    const years = AnalyticsEngine.getAvailableYears(AppState.currentUser.id);
    let html = '';
    years.forEach(y => {
        const isSelected = y === AppState.selectedYear ? 'selected' : '';
        html += `<option value="${y}" ${isSelected}>Year ${y}</option>`;
    });
    select.innerHTML = html;
}

function populateAnalyticsAccountDropdown() {
    const select = document.getElementById('analyticsAccountFilter');
    if (!select) return;

    const accounts = StorageManager.getAccounts(AppState.currentUser.id);
    let html = '<option value="all">All Accounts Combined</option>';
    accounts.forEach(a => {
        const isSelected = a.id === AppState.selectedAccountFilter ? 'selected' : '';
        html += `<option value="${a.id}" ${isSelected}>${escapeHtml(a.bankName)} - ${escapeHtml(a.accountName)}</option>`;
    });
    select.innerHTML = html;
}

// ==========================================
// MODALS & CRUD OPERATIONS
// ==========================================

// --- BANK ACCOUNT MODAL ---
function openAddAccountModal() {
    document.getElementById('accountModalTitle').textContent = 'Add New Bank Account';
    document.getElementById('accountForm').reset();
    document.getElementById('accountIdInput').value = '';
    document.getElementById('accountBalanceContainer').classList.remove('d-none');

    // Hide remove button for new accounts
    const deleteBtn = document.getElementById('deleteAccountFromModalBtn');
    if (deleteBtn) deleteBtn.classList.add('d-none');

    // Populate Account Types
    const typeSelect = document.getElementById('accountTypeInput');
    typeSelect.innerHTML = ACCOUNT_TYPES.map(t => `<option value="${t.id}">${t.label}</option>`).join('');

    // Populate Color Themes
    const themeSelect = document.getElementById('accountThemeInput');
    themeSelect.innerHTML = CARD_THEMES.map(th => `<option value="${th.class}">${th.name}</option>`).join('');

    const modal = new bootstrap.Modal(document.getElementById('accountModal'));
    modal.show();
}

function openEditAccountModal(accountId) {
    const account = StorageManager.getAccountById(AppState.currentUser.id, accountId);
    if (!account) return;

    document.getElementById('accountModalTitle').textContent = 'Edit Bank Account';
    document.getElementById('accountIdInput').value = account.id;
    document.getElementById('accountBankNameInput').value = account.bankName;
    document.getElementById('accountNameInput').value = account.accountName;
    document.getElementById('accountNumberInput').value = account.accountNumber;
    document.getElementById('accountBalanceInput').value = account.currentBalance;

    // Show remove button when editing an existing account
    const deleteBtn = document.getElementById('deleteAccountFromModalBtn');
    if (deleteBtn) {
        deleteBtn.classList.remove('d-none');
        deleteBtn.onclick = () => {
            const modalEl = document.getElementById('accountModal');
            const bsModal = bootstrap.Modal.getInstance(modalEl);
            if (bsModal) bsModal.hide();
            confirmDeleteAccount(accountId);
        };
    }

    const typeSelect = document.getElementById('accountTypeInput');
    typeSelect.innerHTML = ACCOUNT_TYPES.map(t => `<option value="${t.id}" ${t.id === account.accountType ? 'selected' : ''}>${t.label}</option>`).join('');

    const themeSelect = document.getElementById('accountThemeInput');
    themeSelect.innerHTML = CARD_THEMES.map(th => `<option value="${th.class}" ${th.class === account.colorTheme ? 'selected' : ''}>${th.name}</option>`).join('');

    const modal = new bootstrap.Modal(document.getElementById('accountModal'));
    modal.show();
}

async function handleSaveAccount(e) {
    e.preventDefault();
    const userId = AppState.currentUser.id;
    const accountId = document.getElementById('accountIdInput').value;

    const data = {
        bankName: document.getElementById('accountBankNameInput').value,
        accountName: document.getElementById('accountNameInput').value,
        accountType: document.getElementById('accountTypeInput').value,
        accountNumber: document.getElementById('accountNumberInput').value,
        openingBalance: parseFloat(document.getElementById('accountBalanceInput').value) || 0,
        currentBalance: parseFloat(document.getElementById('accountBalanceInput').value) || 0,
        currency: AppState.currentUser.currency || '$',
        colorTheme: document.getElementById('accountThemeInput').value
    };

    try {
        if (accountId) {
            await StorageManager.updateAccount(userId, accountId, data);
            showToast('Bank account updated successfully in database!', 'success');
        } else {
            await StorageManager.addAccount(userId, data);
            showToast('New bank account added successfully to database!', 'success');
        }

        bootstrap.Modal.getInstance(document.getElementById('accountModal')).hide();
        populateNavbarAccountFilter();
        renderActiveView();
    } catch (err) {
        showToast(err.message || 'Error saving bank account.', 'danger');
    }
}

async function confirmDeleteAccount(accountId) {
    const acc = StorageManager.getAccountById(AppState.currentUser.id, accountId);
    if (!acc) return;

    if (confirm(`Are you sure you want to remove "${acc.bankName} (${acc.accountName})"?\n\nWarning: All expenses recorded under this bank account will also be removed from the database!`)) {
        try {
            await StorageManager.deleteAccount(AppState.currentUser.id, accountId);
            showToast(`Bank account "${acc.bankName}" and associated expenses removed from database.`, 'info');
            
            if (AppState.selectedAccountFilter === String(accountId)) {
                AppState.selectedAccountFilter = 'all';
            }
            populateNavbarAccountFilter();
            renderActiveView();
        } catch (err) {
            showToast(err.message || 'Error deleting bank account.', 'danger');
        }
    }
}

// --- DELETE USER PROFILE / ACCOUNT ---
async function confirmDeleteUserAccount() {
    if (!AppState.currentUser) return;
    const userName = AppState.currentUser.name || 'User';

    if (confirm(`⚠️ Are you sure you want to permanently delete your account ("${userName}")?\n\nThis will remove your user login, all your bank accounts, and all tracked expenses from the SQLite database.\nThis action cannot be undone!\n\nDo you want to proceed?`)) {
        const userId = AppState.currentUser.id;
        try {
            await StorageManager.deleteUser(userId);
            AppState.currentUser = null;
            AppState.selectedAccountFilter = 'all';
            showToast('Your user account and all financial data have been permanently removed from the database.', 'warning');
            showAuthView('login');
        } catch (err) {
            showToast(err.message || 'Error deleting account.', 'danger');
        }
    }
}

// --- TOP-UP / ADD FUNDS MODAL ---
function openTopUpModal(accountId) {
    const acc = StorageManager.getAccountById(AppState.currentUser.id, accountId);
    if (!acc) return;

    document.getElementById('topUpAccountId').value = acc.id;
    document.getElementById('topUpAccountName').textContent = `${acc.bankName} - ${acc.accountName}`;
    document.getElementById('topUpCurrentBalance').textContent = `${acc.currency || '$'}${acc.currentBalance.toLocaleString('en-US', { minimumFractionDigits: 2 })}`;
    document.getElementById('topUpAmountInput').value = '';

    const modal = new bootstrap.Modal(document.getElementById('topUpModal'));
    modal.show();
}

async function handleSaveTopUp(e) {
    e.preventDefault();
    const userId = AppState.currentUser.id;
    const accountId = document.getElementById('topUpAccountId').value;
    const amount = parseFloat(document.getElementById('topUpAmountInput').value);

    if (isNaN(amount) || amount <= 0) {
        showToast('Please enter a valid positive amount.', 'warning');
        return;
    }

    try {
        await StorageManager.adjustAccountBalance(userId, accountId, amount);
        showToast(`Added ${AppState.currentUser.currency || '$'}${amount.toFixed(2)} to account balance!`, 'success');

        bootstrap.Modal.getInstance(document.getElementById('topUpModal')).hide();
        populateNavbarAccountFilter();
        renderActiveView();
    } catch (err) {
        showToast(err.message || 'Error depositing funds.', 'danger');
    }
}

// --- EXPENSE MODAL ---
function openAddExpenseModal() {
    const userId = AppState.currentUser.id;
    const accounts = StorageManager.getAccounts(userId);

    if (accounts.length === 0) {
        showToast('Please add at least one bank account first before logging expenses.', 'warning');
        openAddAccountModal();
        return;
    }

    document.getElementById('expenseModalTitle').textContent = 'Add New Expense';
    document.getElementById('expenseForm').reset();
    document.getElementById('expenseIdInput').value = '';

    // Set today's date & time
    const now = new Date();
    document.getElementById('expenseDateInput').value = now.toISOString().split('T')[0];
    document.getElementById('expenseTimeInput').value = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;

    // Populate Account select
    const accSelect = document.getElementById('expenseAccountInput');
    accSelect.innerHTML = accounts.map(a => 
        `<option value="${a.id}" ${AppState.selectedAccountFilter === a.id ? 'selected' : ''}>${escapeHtml(a.bankName)} - ${escapeHtml(a.accountName)} (Balance: ${a.currency}${a.currentBalance.toLocaleString('en-US', { minimumFractionDigits: 2 })})</option>`
    ).join('');

    // Populate Category select
    const catSelect = document.getElementById('expenseCategoryInput');
    catSelect.innerHTML = DEFAULT_CATEGORIES.map(c => 
        `<option value="${c.id}">${c.name}</option>`
    ).join('');

    const modal = new bootstrap.Modal(document.getElementById('expenseModal'));
    modal.show();
}

function openEditExpenseModal(expenseId) {
    const userId = AppState.currentUser.id;
    const expense = StorageManager.getExpenseById(userId, expenseId);
    if (!expense) return;

    const accounts = StorageManager.getAccounts(userId);

    document.getElementById('expenseModalTitle').textContent = 'Edit Expense Details';
    document.getElementById('expenseIdInput').value = expense.id;
    document.getElementById('expenseAmountInput').value = expense.amount;
    document.getElementById('expensePlaceInput').value = expense.place;
    document.getElementById('expensePurposeInput').value = expense.purpose || '';
    document.getElementById('expenseDateInput').value = expense.date;
    document.getElementById('expenseTimeInput').value = expense.time || '12:00';
    document.getElementById('expensePaymentModeInput').value = expense.paymentMode || 'Card';
    document.getElementById('expenseNotesInput').value = expense.notes || '';

    // Populate Account select
    const accSelect = document.getElementById('expenseAccountInput');
    accSelect.innerHTML = accounts.map(a => 
        `<option value="${a.id}" ${a.id === expense.accountId ? 'selected' : ''}>${escapeHtml(a.bankName)} - ${escapeHtml(a.accountName)} (Bal: ${a.currency}${a.currentBalance.toLocaleString('en-US', { minimumFractionDigits: 2 })})</option>`
    ).join('');

    // Populate Category select
    const catSelect = document.getElementById('expenseCategoryInput');
    catSelect.innerHTML = DEFAULT_CATEGORIES.map(c => 
        `<option value="${c.id}" ${c.id === expense.category ? 'selected' : ''}>${c.name}</option>`
    ).join('');

    const modal = new bootstrap.Modal(document.getElementById('expenseModal'));
    modal.show();
}

async function handleSaveExpense(e) {
    e.preventDefault();
    const userId = AppState.currentUser.id;
    const expenseId = document.getElementById('expenseIdInput').value;

    const amount = parseFloat(document.getElementById('expenseAmountInput').value);
    if (isNaN(amount) || amount <= 0) {
        showToast('Please enter a valid expense amount.', 'warning');
        return;
    }

    const data = {
        amount: amount,
        accountId: document.getElementById('expenseAccountInput').value,
        place: document.getElementById('expensePlaceInput').value,
        purpose: document.getElementById('expensePurposeInput').value,
        category: document.getElementById('expenseCategoryInput').value,
        date: document.getElementById('expenseDateInput').value,
        time: document.getElementById('expenseTimeInput').value,
        paymentMode: document.getElementById('expensePaymentModeInput').value,
        notes: document.getElementById('expenseNotesInput').value
    };

    try {
        if (expenseId) {
            await StorageManager.updateExpense(userId, expenseId, data);
            showToast('Expense updated & bank balance adjusted in database.', 'success');
        } else {
            await StorageManager.addExpense(userId, data);
            showToast('Expense recorded & bank balance deducted in database.', 'success');
        }

        bootstrap.Modal.getInstance(document.getElementById('expenseModal')).hide();
        populateNavbarAccountFilter();
        renderActiveView();
    } catch (err) {
        showToast(err.message || 'Error saving expense.', 'danger');
    }
}

async function confirmDeleteExpense(expenseId) {
    if (confirm('Are you sure you want to delete this expense?\nThe amount will be refunded back to the linked bank account balance in the SQLite database.')) {
        try {
            await StorageManager.deleteExpense(AppState.currentUser.id, expenseId);
            showToast('Expense deleted and amount refunded in database.', 'info');
            populateNavbarAccountFilter();
            renderActiveView();
        } catch (err) {
            showToast(err.message || 'Error deleting expense.', 'danger');
        }
    }
}

// ==========================================
// EXPORT TO CSV
// ==========================================
function exportExpensesToCSV() {
    const userId = AppState.currentUser.id;
    const expenses = StorageManager.getExpenses(userId);
    const accounts = StorageManager.getAccounts(userId);
    const accountsMap = {};
    accounts.forEach(a => { accountsMap[a.id] = a; });

    if (expenses.length === 0) {
        showToast('No expenses available to export.', 'warning');
        return;
    }

    let csvContent = 'data:text/csv;charset=utf-8,';
    csvContent += 'Date,Time,Place / Merchant,Purpose,Category,Bank Account,Payment Mode,Amount\n';

    expenses.forEach(e => {
        const cat = DEFAULT_CATEGORIES.find(c => c.id === e.category)?.name || 'Others';
        const acc = accountsMap[e.accountId]?.bankName || 'Unknown';
        const safePlace = `"${(e.place || '').replace(/"/g, '""')}"`;
        const safePurpose = `"${(e.purpose || '').replace(/"/g, '""')}"`;
        
        csvContent += `${e.date},${e.time || ''},${safePlace},${safePurpose},${cat},${acc},${e.paymentMode || ''},${e.amount}\n`;
    });

    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', `SpendWise_Expenses_${new Date().toISOString().split('T')[0]}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    showToast('Expenses exported to CSV successfully!', 'success');
}

// ==========================================
// PDF REPORT DOWNLOAD ENGINE (Monthly, Quarterly, Half-Yearly, Yearly)
// ==========================================
function downloadPdfReport(timeframe = 'monthly', options = {}) {
    const year = options.year !== undefined ? options.year : (AppState.selectedYear || new Date().getFullYear());
    const accountId = options.accountId !== undefined ? options.accountId : (AppState.selectedAccountFilter || 'all');

    let month = options.month;
    if (month === undefined) {
        const monthSelect = document.getElementById('analyticsMonthSelect');
        month = monthSelect ? parseInt(monthSelect.value, 10) : AppState.selectedMonth;
    }

    let quarter = options.quarter;
    if (quarter === undefined) {
        const quarterSelect = document.getElementById('analyticsQuarterSelect');
        quarter = quarterSelect ? parseInt(quarterSelect.value, 10) : AppState.selectedQuarter;
    }

    let half = options.half;
    if (half === undefined) {
        const halfSelect = document.getElementById('analyticsHalfSelect');
        half = halfSelect ? parseInt(halfSelect.value, 10) : AppState.selectedHalf;
    }

    const params = new URLSearchParams();
    params.set('timeframe', timeframe);
    params.set('year', String(year));
    params.set('accountId', String(accountId));

    if (timeframe === 'monthly') {
        params.set('month', String(month));
    } else if (timeframe === 'quarterly') {
        params.set('quarter', String(quarter));
    } else if (timeframe === 'halfyearly') {
        params.set('half', String(half));
    }

    const reportUrl = `/api/reports/pdf/?${params.toString()}`;

    const tfLabels = {
        monthly: 'Monthly',
        quarterly: 'Quarterly',
        halfyearly: 'Half-Yearly',
        yearly: 'Annual'
    };
    showToast(`Generating ${tfLabels[timeframe] || ''} PDF report... Your download will begin momentarily.`, 'info');

    // Trigger file download
    const link = document.createElement('a');
    link.href = reportUrl;
    link.setAttribute('download', '');
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

function openReportModal(timeframe = null) {
    const userId = AppState.currentUser ? AppState.currentUser.id : null;
    const yearSelect = document.getElementById('modalReportYear');
    if (yearSelect && userId) {
        const availableYears = AnalyticsEngine.getAvailableYears(userId);
        yearSelect.innerHTML = availableYears.map(y => `<option value="${y}" ${y === AppState.selectedYear ? 'selected' : ''}>${y}</option>`).join('');
    }

    const accountSelect = document.getElementById('modalReportAccount');
    if (accountSelect && userId) {
        const accounts = StorageManager.getAccounts(userId);
        accountSelect.innerHTML = '<option value="all">All Accounts Combined (Consolidated)</option>' +
            accounts.map(a => `<option value="${a.id}" ${String(a.id) === String(AppState.selectedAccountFilter) ? 'selected' : ''}>${escapeHtml(a.bankName)} - ${escapeHtml(a.accountName)} (${a.accountNumber})</option>`).join('');
    }

    // Set active timeframe radio
    const activeTf = timeframe || AppState.analyticsTimeframe || 'monthly';
    const radioIdMap = {
        monthly: 'modalTfMonthly',
        quarterly: 'modalTfQuarterly',
        halfyearly: 'modalTfHalfYearly',
        yearly: 'modalTfYearly'
    };
    const targetRadio = document.getElementById(radioIdMap[activeTf]);
    if (targetRadio) {
        targetRadio.checked = true;
    }
    updateModalTimeframeContainers(activeTf);

    // Sync sub-selectors with current state
    const monthSelect = document.getElementById('modalReportMonth');
    if (monthSelect) monthSelect.value = String(AppState.selectedMonth);

    const quarterSelect = document.getElementById('modalReportQuarter');
    if (quarterSelect) quarterSelect.value = String(AppState.selectedQuarter);

    const halfSelect = document.getElementById('modalReportHalf');
    if (halfSelect) halfSelect.value = String(AppState.selectedHalf);

    const modalEl = document.getElementById('reportModal');
    if (modalEl) {
        const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
        modal.show();
    }
}

function openReportModalWithTimeframe(timeframe) {
    openReportModal(timeframe);
}

function updateModalTimeframeContainers(timeframe) {
    const monthContainer = document.getElementById('modalReportMonthContainer');
    const quarterContainer = document.getElementById('modalReportQuarterContainer');
    const halfContainer = document.getElementById('modalReportHalfContainer');

    if (monthContainer) monthContainer.classList.toggle('d-none', timeframe !== 'monthly');
    if (quarterContainer) quarterContainer.classList.toggle('d-none', timeframe !== 'quarterly');
    if (halfContainer) halfContainer.classList.toggle('d-none', timeframe !== 'halfyearly');
}

// ==========================================
// SPENDBOT CHATBOT CLIENT ENGINE
// ==========================================
function toggleSpendBot() {
    const win = document.getElementById('spendBotWindow');
    if (!win) return;
    const isHidden = win.classList.contains('d-none');
    if (isHidden) {
        win.classList.remove('d-none');
        const input = document.getElementById('spendBotInput');
        if (input) setTimeout(() => input.focus(), 120);
        scrollSpendBotToBottom();
    } else {
        win.classList.add('d-none');
    }
}

function closeSpendBot() {
    const win = document.getElementById('spendBotWindow');
    if (win) win.classList.add('d-none');
}

function clearSpendBotChat() {
    const messages = document.getElementById('spendBotMessages');
    if (!messages) return;
    const userName = AppState.currentUser?.name || 'there';
    messages.innerHTML = `
        <div class="spendbot-msg bot-msg mb-2">
            <div class="msg-bubble">
                <div class="fw-semibold mb-1"><i class="bi bi-robot text-primary me-1"></i> SpendBot:</div>
                Hello ${escapeHtml(userName)}! Chat history cleared. What financial details would you like to know about your expenses today?
            </div>
            <div class="msg-time small text-muted mt-1">Just now</div>
        </div>
    `;
    resetSpendBotQuickChips([
        "💰 Total Expense",
        "📅 Total Monthly Expense",
        "📊 Qtr Expense",
        "🗓️ Yearly Expense",
        "❄️ Jan Month Expense",
        "🏷️ Category Wise Expense",
        "📈 Max Month Expense",
        "🏆 Max Category Expense"
    ]);
}

function scrollSpendBotToBottom() {
    const container = document.getElementById('spendBotMessages');
    if (container) {
        setTimeout(() => {
            container.scrollTop = container.scrollHeight;
        }, 30);
    }
}

function formatBotMarkdown(text) {
    if (!text) return '';
    let html = escapeHtml(text);
    // Unescape badges if any
    html = html.replace(/&lt;span class=&#039;(badge [^&#039;]+)&#039;&gt;(.*?)&lt;\/span&gt;/g, '<span class="$1">$2</span>');
    html = html.replace(/&lt;span class="badge (.*?)"&gt;(.*?)&lt;\/span&gt;/g, '<span class="badge $1">$2</span>');
    // Bold: **text**
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    // Italics: *text*
    html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');
    // Inline code: `text`
    html = html.replace(/`([^`]+)`/g, '<code class="bg-secondary-subtle px-1 rounded">$1</code>');
    // Bullet points: • item or - item
    html = html.replace(/^[•\-] (.*)$/gm, '<div class="ps-2">• $1</div>');
    // Numbered lists: 1. item
    html = html.replace(/^(\d+)\. (.*)$/gm, '<div class="ps-2"><strong>$1.</strong> $2</div>');
    // Paragraph breaks
    html = html.replace(/\n\n/g, '<div class="my-2"></div>');
    html = html.replace(/\n/g, '<br>');
    return html;
}

function appendSpendBotMessage(sender, content, isHtml = false) {
    const messages = document.getElementById('spendBotMessages');
    if (!messages) return;

    const timeStr = new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
    const msgDiv = document.createElement('div');
    msgDiv.className = `spendbot-msg ${sender}-msg mb-2`;

    const bubbleDiv = document.createElement('div');
    bubbleDiv.className = 'msg-bubble';

    if (isHtml) {
        bubbleDiv.innerHTML = content;
    } else {
        bubbleDiv.textContent = content;
    }

    const timeDiv = document.createElement('div');
    timeDiv.className = 'msg-time small text-muted mt-1';
    timeDiv.textContent = timeStr;

    msgDiv.appendChild(bubbleDiv);
    msgDiv.appendChild(timeDiv);
    messages.appendChild(msgDiv);
    scrollSpendBotToBottom();
}

function resetSpendBotQuickChips(suggestions) {
    const chipsContainer = document.getElementById('spendBotQuickChips');
    if (!chipsContainer || !suggestions || suggestions.length === 0) return;

    chipsContainer.innerHTML = suggestions.map(s => {
        const cleanPrompt = s.replace(/^[^\w\s]+\s*/, '');
        return `<button type="button" class="spendbot-chip btn btn-sm rounded-pill" data-prompt="${escapeHtml(cleanPrompt)}">${escapeHtml(s)}</button>`;
    }).join('');

    // Re-bind click event
    chipsContainer.querySelectorAll('.spendbot-chip').forEach(chip => {
        chip.addEventListener('click', () => {
            const prompt = chip.getAttribute('data-prompt');
            sendSpendBotMessage(prompt);
        });
    });
}

async function sendSpendBotMessage(text) {
    const prompt = (text || '').trim();
    if (!prompt) return;

    // Display user message
    appendSpendBotMessage('user', prompt, false);

    // Clear input
    const input = document.getElementById('spendBotInput');
    if (input) input.value = '';

    // Show typing indicator
    const typingIndicator = document.getElementById('spendBotTyping');
    if (typingIndicator) typingIndicator.classList.remove('d-none');
    scrollSpendBotToBottom();

    try {
        const data = await apiFetch('/api/chat/', {
            method: 'POST',
            body: JSON.stringify({ message: prompt })
        });

        if (typingIndicator) typingIndicator.classList.add('d-none');

        const formattedReply = formatBotMarkdown(data.reply);
        appendSpendBotMessage('bot', formattedReply, true);

        // Dynamically update quick chips with suggested follow-ups
        if (data.suggestions && data.suggestions.length > 0) {
            resetSpendBotQuickChips(data.suggestions);
        }
    } catch (err) {
        if (typingIndicator) typingIndicator.classList.add('d-none');
        appendSpendBotMessage('bot', `⚠️ Sorry, I encountered an error: ${escapeHtml(err.message || 'Please try again.')}`, false);
    }
}

// ==========================================
// TOAST NOTIFICATIONS
// ==========================================
function showToast(message, type = 'info') {
    const toastEl = document.getElementById('appToast');
    const toastBody = document.getElementById('appToastBody');
    if (!toastEl || !toastBody) return;

    toastBody.textContent = message;
    toastEl.className = `toast align-items-center text-bg-${type} border-0`;

    const bsToast = new bootstrap.Toast(toastEl, { delay: 3500 });
    bsToast.show();
}

// ==========================================
// HELPER UTILITIES
// ==========================================
function formatDate(dateStr) {
    if (!dateStr) return '';
    const parts = dateStr.split('-');
    if (parts.length !== 3) return dateStr;
    const date = new Date(parts[0], parts[1] - 1, parts[2]);
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/&/g, '&amp;')
              .replace(/</g, '&lt;')
              .replace(/>/g, '&gt;')
              .replace(/"/g, '&quot;')
              .replace(/'/g, '&#039;');
}

// ==========================================
// EVENT LISTENERS BINDING
// ==========================================
function setupEventListeners() {
    // Theme toggle
    const themeBtn = document.getElementById('themeToggleBtn');
    if (themeBtn) themeBtn.addEventListener('click', toggleTheme);

    // Navigation Links
    document.querySelectorAll('[data-nav-view]').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            const view = btn.getAttribute('data-nav-view');
            navigateTo(view);

            // Auto-collapse mobile navbar if expanded
            const navbarCollapse = document.getElementById('navbarContent');
            if (navbarCollapse && navbarCollapse.classList.contains('show')) {
                const bsCollapse = bootstrap.Collapse.getInstance(navbarCollapse);
                if (bsCollapse) bsCollapse.hide();
            }
        });
    });

    // Global Account Selector in Navbar
    const globalAccSelect = document.getElementById('globalAccountSelector');
    if (globalAccSelect) {
        globalAccSelect.addEventListener('change', (e) => {
            AppState.selectedAccountFilter = e.target.value;
            renderActiveView();
        });
    }

    // Auth: Switch to Register
    const showRegisterBtn = document.getElementById('showRegisterBtn');
    if (showRegisterBtn) {
        showRegisterBtn.addEventListener('click', (e) => {
            e.preventDefault();
            showAuthView('register');
        });
    }

    // Auth: Switch to Login
    const showLoginBtn = document.getElementById('showLoginBtn');
    if (showLoginBtn) {
        showLoginBtn.addEventListener('click', (e) => {
            e.preventDefault();
            showAuthView('login');
        });
    }

    // Auth: Login Form Submit
    const loginForm = document.getElementById('loginForm');
    if (loginForm) {
        loginForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const email = document.getElementById('loginEmail').value;
            const password = document.getElementById('loginPassword').value;

            const res = await StorageManager.login(email, password);
            if (res.success) {
                AppState.currentUser = res.user;
                showToast(`Welcome back, ${res.user.name}!`, 'success');
                showAppShell();
                navigateTo('dashboard');
            } else {
                showToast(res.message, 'danger');
            }
        });
    }

    // Auth: Quick Demo Login Button
    const demoLoginBtn = document.getElementById('demoLoginBtn');
    if (demoLoginBtn) {
        demoLoginBtn.addEventListener('click', async () => {
            const res = await StorageManager.demoLogin();
            if (res.success) {
                AppState.currentUser = res.user;
                showToast('Logged in with Demo Account!', 'success');
                showAppShell();
                navigateTo('dashboard');
            } else {
                showToast(res.message || 'Demo login failed.', 'danger');
            }
        });
    }

    // Auth: Register Form Submit
    const registerForm = document.getElementById('registerForm');
    if (registerForm) {
        registerForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const name = document.getElementById('regName').value;
            const email = document.getElementById('regEmail').value;
            const password = document.getElementById('regPassword').value;
            const currency = document.getElementById('regCurrency').value || '$';

            const res = await StorageManager.register(name, email, password, currency);
            if (res.success) {
                AppState.currentUser = res.user;
                showToast(`Account created successfully! Welcome, ${res.user.name}.`, 'success');
                showAppShell();
                navigateTo('dashboard');
            } else {
                showToast(res.message, 'danger');
            }
        });
    }

    // Logout
    const logoutBtn = document.getElementById('logoutBtn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', async (e) => {
            e.preventDefault();
            await StorageManager.logout();
            AppState.currentUser = null;
            AppState.selectedAccountFilter = 'all';
            showToast('You have been logged out.', 'info');
            showAuthView('login');
        });
    }

    // Reset Demo Data
    const resetDemoBtn = document.getElementById('resetDemoDataBtn');
    if (resetDemoBtn) {
        resetDemoBtn.addEventListener('click', async (e) => {
            e.preventDefault();
            if (confirm('This will reload fresh demo accounts and multi-quarter expenses into the SQLite database. Continue?')) {
                const userId = AppState.currentUser.id;
                await StorageManager.seedDemoData(userId, AppState.currentUser.currency || '$');
                showToast('Sample bank accounts & expenses reloaded in database!', 'success');
                populateNavbarAccountFilter();
                renderActiveView();
            }
        });
    }

    // Form Submissions
    const accForm = document.getElementById('accountForm');
    if (accForm) accForm.addEventListener('submit', handleSaveAccount);

    const expForm = document.getElementById('expenseForm');
    if (expForm) expForm.addEventListener('submit', handleSaveExpense);

    const topUpForm = document.getElementById('topUpForm');
    if (topUpForm) topUpForm.addEventListener('submit', handleSaveTopUp);

    // Expenses Live Filtering
    ['expenseAccountFilter', 'expenseCategoryFilter', 'expenseDateFrom', 'expenseDateTo'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.addEventListener('change', renderExpensesView);
    });

    const searchInput = document.getElementById('expenseSearchInput');
    if (searchInput) {
        searchInput.addEventListener('input', () => {
            renderExpensesView();
        });
    }

    // Analytics Timeframe Tabs (Monthly, Quarterly, Half-Yearly, Yearly)
    document.querySelectorAll('#analyticsTimeframeTabs .nav-link').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            AppState.analyticsTimeframe = btn.getAttribute('data-timeframe');
            renderAnalyticsView();
        });
    });

    // Analytics Subcontrols (Month, Quarter, Half, Year, Account)
    const analyticsYearSelect = document.getElementById('analyticsYearSelect');
    if (analyticsYearSelect) {
        analyticsYearSelect.addEventListener('change', (e) => {
            AppState.selectedYear = parseInt(e.target.value, 10);
            renderAnalyticsView();
        });
    }

    const analyticsMonthSelect = document.getElementById('analyticsMonthSelect');
    if (analyticsMonthSelect) {
        analyticsMonthSelect.addEventListener('change', (e) => {
            AppState.selectedMonth = parseInt(e.target.value, 10);
            renderAnalyticsView();
        });
    }

    const analyticsQuarterSelect = document.getElementById('analyticsQuarterSelect');
    if (analyticsQuarterSelect) {
        analyticsQuarterSelect.addEventListener('change', (e) => {
            AppState.selectedQuarter = parseInt(e.target.value, 10);
            renderAnalyticsView();
        });
    }

    const analyticsHalfSelect = document.getElementById('analyticsHalfSelect');
    if (analyticsHalfSelect) {
        analyticsHalfSelect.addEventListener('change', (e) => {
            AppState.selectedHalf = parseInt(e.target.value, 10);
            renderAnalyticsView();
        });
    }

    const analyticsAccountFilter = document.getElementById('analyticsAccountFilter');
    if (analyticsAccountFilter) {
        analyticsAccountFilter.addEventListener('change', (e) => {
            AppState.selectedAccountFilter = e.target.value;
            // Also synchronize global navbar select
            const globalSelect = document.getElementById('globalAccountSelector');
            if (globalSelect) globalSelect.value = e.target.value;
            renderAnalyticsView();
        });
    }

    // Export CSV Button
    const exportCsvBtn = document.getElementById('exportExpensesCsvBtn');
    if (exportCsvBtn) exportCsvBtn.addEventListener('click', exportExpensesToCSV);

    // PDF Reports Download Buttons
    const downloadActiveViewPdfBtn = document.getElementById('downloadActiveViewPdfBtn');
    if (downloadActiveViewPdfBtn) {
        downloadActiveViewPdfBtn.addEventListener('click', (e) => {
            e.preventDefault();
            downloadPdfReport(AppState.analyticsTimeframe);
        });
    }

    const downloadMonthlyPdfBtn = document.getElementById('downloadMonthlyPdfBtn');
    if (downloadMonthlyPdfBtn) {
        downloadMonthlyPdfBtn.addEventListener('click', (e) => {
            e.preventDefault();
            downloadPdfReport('monthly');
        });
    }

    const downloadQuarterlyPdfBtn = document.getElementById('downloadQuarterlyPdfBtn');
    if (downloadQuarterlyPdfBtn) {
        downloadQuarterlyPdfBtn.addEventListener('click', (e) => {
            e.preventDefault();
            downloadPdfReport('quarterly');
        });
    }

    const downloadHalfYearlyPdfBtn = document.getElementById('downloadHalfYearlyPdfBtn');
    if (downloadHalfYearlyPdfBtn) {
        downloadHalfYearlyPdfBtn.addEventListener('click', (e) => {
            e.preventDefault();
            downloadPdfReport('halfyearly');
        });
    }

    const downloadYearlyPdfBtn = document.getElementById('downloadYearlyPdfBtn');
    if (downloadYearlyPdfBtn) {
        downloadYearlyPdfBtn.addEventListener('click', (e) => {
            e.preventDefault();
            downloadPdfReport('yearly');
        });
    }

    // Modal timeframe radio button switcher
    document.querySelectorAll('input[name="modalReportTimeframe"]').forEach(radio => {
        radio.addEventListener('change', (e) => {
            updateModalTimeframeContainers(e.target.value);
        });
    });

    // Modal Download Submit Button
    const modalDownloadPdfSubmitBtn = document.getElementById('modalDownloadPdfSubmitBtn');
    if (modalDownloadPdfSubmitBtn) {
        modalDownloadPdfSubmitBtn.addEventListener('click', (e) => {
            e.preventDefault();
            const selectedRadio = document.querySelector('input[name="modalReportTimeframe"]:checked');
            const tf = selectedRadio ? selectedRadio.value : 'monthly';
            const yr = document.getElementById('modalReportYear')?.value || AppState.selectedYear;
            const m = document.getElementById('modalReportMonth')?.value;
            const q = document.getElementById('modalReportQuarter')?.value;
            const h = document.getElementById('modalReportHalf')?.value;
            const acc = document.getElementById('modalReportAccount')?.value || 'all';

            downloadPdfReport(tf, {
                year: parseInt(yr, 10),
                month: parseInt(m, 10),
                quarter: parseInt(q, 10),
                half: parseInt(h, 10),
                accountId: acc
            });

            const modalEl = document.getElementById('reportModal');
            if (modalEl) {
                const modal = bootstrap.Modal.getInstance(modalEl);
                if (modal) modal.hide();
            }
        });
    }

    // Delete User Profile / Account
    const deleteUserBtn = document.getElementById('deleteUserAccountBtn');
    if (deleteUserBtn) {
        deleteUserBtn.addEventListener('click', (e) => {
            e.preventDefault();
            confirmDeleteUserAccount();
        });
    }

    // SpendBot Chatbot Event Listeners
    const spendBotToggleBtn = document.getElementById('spendBotToggleBtn');
    if (spendBotToggleBtn) {
        spendBotToggleBtn.addEventListener('click', (e) => {
            e.preventDefault();
            toggleSpendBot();
        });
    }

    const spendBotCloseBtn = document.getElementById('spendBotCloseBtn');
    if (spendBotCloseBtn) {
        spendBotCloseBtn.addEventListener('click', (e) => {
            e.preventDefault();
            closeSpendBot();
        });
    }

    const spendBotClearBtn = document.getElementById('spendBotClearBtn');
    if (spendBotClearBtn) {
        spendBotClearBtn.addEventListener('click', (e) => {
            e.preventDefault();
            clearSpendBotChat();
        });
    }

    const spendBotForm = document.getElementById('spendBotForm');
    if (spendBotForm) {
        spendBotForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const input = document.getElementById('spendBotInput');
            if (input && input.value.trim()) {
                sendSpendBotMessage(input.value.trim());
            }
        });
    }

    document.querySelectorAll('#spendBotQuickChips .spendbot-chip').forEach(chip => {
        chip.addEventListener('click', () => {
            const prompt = chip.getAttribute('data-prompt');
            sendSpendBotMessage(prompt);
        });
    });
}

// Global exposure for inline onclick handlers
window.openAddAccountModal = openAddAccountModal;
window.openEditAccountModal = openEditAccountModal;
window.confirmDeleteAccount = confirmDeleteAccount;
window.confirmDeleteUserAccount = confirmDeleteUserAccount;
window.openTopUpModal = openTopUpModal;
window.openAddExpenseModal = openAddExpenseModal;
window.openEditExpenseModal = openEditExpenseModal;
window.confirmDeleteExpense = confirmDeleteExpense;
window.resetExpenseFilters = resetExpenseFilters;
window.exportExpensesToCSV = exportExpensesToCSV;
window.downloadPdfReport = downloadPdfReport;
window.openReportModal = openReportModal;
window.openReportModalWithTimeframe = openReportModalWithTimeframe;
window.toggleSpendBot = toggleSpendBot;
window.closeSpendBot = closeSpendBot;
window.clearSpendBotChat = clearSpendBotChat;
window.sendSpendBotMessage = sendSpendBotMessage;
