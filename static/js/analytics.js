/**
 * SpendWise - Analytics & Reporting Engine
 * Calculates Monthly, Quarterly, Half-Yearly, and Yearly breakdowns,
 * identifies top spending categories, and aggregates cross-account expenses.
 */

class AnalyticsEngine {
    /**
     * Parses year, month (0-indexed), and day safely without timezone drift
     */
    static parseDateParts(dateStr) {
        if (!dateStr) return { year: NaN, month: NaN, day: NaN };
        const dateOnly = String(dateStr).split('T')[0];
        const parts = dateOnly.split('-');
        if (parts.length === 3) {
            return {
                year: parseInt(parts[0], 10),
                month: parseInt(parts[1], 10) - 1,
                day: parseInt(parts[2], 10)
            };
        }
        const d = new Date(dateStr);
        return {
            year: d.getFullYear(),
            month: d.getMonth(),
            day: d.getDate()
        };
    }

    /**
     * Filters expenses by user, optional accountId, and year
     */
    static getFilteredExpenses(userId, accountId = 'all', year = null) {
        let expenses = StorageManager.getExpenses(userId);

        if (accountId && accountId !== 'all') {
            expenses = expenses.filter(e => e.accountId === accountId);
        }

        if (year) {
            expenses = expenses.filter(e => {
                const parts = this.parseDateParts(e.date);
                return parts.year === parseInt(year, 10);
            });
        }

        return expenses;
    }

    /**
     * Get list of unique available years from expenses
     */
    static getAvailableYears(userId) {
        const expenses = StorageManager.getExpenses(userId);
        const currentYear = new Date().getFullYear();
        const yearsSet = new Set([currentYear]);

        expenses.forEach(e => {
            if (e.date) {
                const parts = this.parseDateParts(e.date);
                if (!isNaN(parts.year)) yearsSet.add(parts.year);
            }
        });

        return Array.from(yearsSet).sort((a, b) => b - a);
    }

    /**
     * Computes Category Breakdown and identifies Top Category
     */
    static getCategoryBreakdown(expenses) {
        const categoryMap = {};
        let totalExpense = 0;

        // Initialize with default categories
        DEFAULT_CATEGORIES.forEach(cat => {
            categoryMap[cat.id] = {
                id: cat.id,
                name: cat.name,
                icon: cat.icon,
                color: cat.color,
                total: 0,
                count: 0,
                percentage: 0
            };
        });

        // Tally up
        expenses.forEach(e => {
            const catId = e.category || 'others';
            if (!categoryMap[catId]) {
                categoryMap[catId] = {
                    id: catId,
                    name: catId.charAt(0).toUpperCase() + catId.slice(1),
                    icon: 'bi-tag',
                    color: '#6c757d',
                    total: 0,
                    count: 0,
                    percentage: 0
                };
            }
            const amt = parseFloat(e.amount) || 0;
            categoryMap[catId].total += amt;
            categoryMap[catId].count += 1;
            totalExpense += amt;
        });

        // Compute percentages and sort descending
        const breakdownList = Object.values(categoryMap)
            .filter(item => item.total > 0)
            .map(item => {
                item.total = Math.round(item.total * 100) / 100;
                item.percentage = totalExpense > 0 ? Math.round((item.total / totalExpense) * 1000) / 10 : 0;
                item.average = item.count > 0 ? Math.round((item.total / item.count) * 100) / 100 : 0;
                return item;
            })
            .sort((a, b) => b.total - a.total);

        const topCategory = breakdownList.length > 0 ? breakdownList[0] : null;

        return {
            totalExpense: Math.round(totalExpense * 100) / 100,
            transactionCount: expenses.length,
            categories: breakdownList,
            topCategory: topCategory
        };
    }

    /**
     * MONTHLY ANALYSIS
     * Computes stats for each of the 12 months in a given year,
     * plus focused stats for the chosen month (0-11).
     */
    static getMonthlyAnalysis(userId, accountId = 'all', year, targetMonth = null) {
        const expenses = this.getFilteredExpenses(userId, accountId, year);
        const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
        const fullMonthNames = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];

        const monthlyTotals = new Array(12).fill(0);
        const monthlyCounts = new Array(12).fill(0);
        const monthlyExpensesMap = Array.from({ length: 12 }, () => []);

        expenses.forEach(e => {
            const parts = this.parseDateParts(e.date);
            const m = parts.month;
            if (m >= 0 && m < 12) {
                const amt = parseFloat(e.amount) || 0;
                monthlyTotals[m] += amt;
                monthlyCounts[m] += 1;
                monthlyExpensesMap[m].push(e);
            }
        });

        // Round totals
        for (let i = 0; i < 12; i++) {
            monthlyTotals[i] = Math.round(monthlyTotals[i] * 100) / 100;
        }

        const selectedMonthIdx = targetMonth !== null ? parseInt(targetMonth, 10) : new Date().getMonth();
        const selectedMonthExpenses = monthlyExpensesMap[selectedMonthIdx];
        const selectedMonthBreakdown = this.getCategoryBreakdown(selectedMonthExpenses);

        // Previous month comparison
        const prevMonthIdx = selectedMonthIdx === 0 ? 11 : selectedMonthIdx - 1;
        const prevMonthTotal = monthlyTotals[prevMonthIdx];
        const currentMonthTotal = monthlyTotals[selectedMonthIdx];
        let monthOverMonthChange = 0;
        if (prevMonthTotal > 0) {
            monthOverMonthChange = Math.round(((currentMonthTotal - prevMonthTotal) / prevMonthTotal) * 1000) / 10;
        }

        // Daily breakdown for selected month
        const daysInMonth = new Date(year, selectedMonthIdx + 1, 0).getDate();
        const dailyTotals = new Array(daysInMonth).fill(0);
        selectedMonthExpenses.forEach(e => {
            const parts = this.parseDateParts(e.date);
            const day = parts.day;
            if (day >= 1 && day <= daysInMonth) {
                dailyTotals[day - 1] += parseFloat(e.amount) || 0;
            }
        });

        return {
            year,
            selectedMonthIndex: selectedMonthIdx,
            selectedMonthName: fullMonthNames[selectedMonthIdx],
            labels: monthNames,
            monthlyTotals,
            monthlyCounts,
            selectedMonthTotal: currentMonthTotal,
            selectedMonthCount: monthlyCounts[selectedMonthIdx],
            prevMonthTotal,
            prevMonthName: fullMonthNames[prevMonthIdx],
            monthOverMonthChange,
            categoryBreakdown: selectedMonthBreakdown,
            dailyLabels: Array.from({ length: daysInMonth }, (_, i) => `${i + 1}`),
            dailyTotals: dailyTotals.map(v => Math.round(v * 100) / 100),
            topCategory: selectedMonthBreakdown.topCategory
        };
    }

    /**
     * QUARTERLY ANALYSIS
     * Q1: Jan-Mar (months 0,1,2)
     * Q2: Apr-Jun (months 3,4,5)
     * Q3: Jul-Sep (months 6,7,8)
     * Q4: Oct-Dec (months 9,10,11)
     */
    static getQuarterlyAnalysis(userId, accountId = 'all', year, targetQuarter = 1) {
        const expenses = this.getFilteredExpenses(userId, accountId, year);
        const quarters = [
            { id: 1, label: 'Q1 (Jan - Mar)', short: 'Q1', months: [0, 1, 2], total: 0, count: 0, expenses: [] },
            { id: 2, label: 'Q2 (Apr - Jun)', short: 'Q2', months: [3, 4, 5], total: 0, count: 0, expenses: [] },
            { id: 3, label: 'Q3 (Jul - Sep)', short: 'Q3', months: [6, 7, 8], total: 0, count: 0, expenses: [] },
            { id: 4, label: 'Q4 (Oct - Dec)', short: 'Q4', months: [9, 10, 11], total: 0, count: 0, expenses: [] }
        ];

        expenses.forEach(e => {
            const parts = this.parseDateParts(e.date);
            const m = parts.month;
            const q = quarters.find(item => item.months.includes(m));
            if (q) {
                const amt = parseFloat(e.amount) || 0;
                q.total += amt;
                q.count += 1;
                q.expenses.push(e);
            }
        });

        quarters.forEach(q => {
            q.total = Math.round(q.total * 100) / 100;
        });

        const activeQ = quarters.find(q => q.id === parseInt(targetQuarter, 10)) || quarters[0];
        const activeQuarterBreakdown = this.getCategoryBreakdown(activeQ.expenses);

        // Highest spending quarter of the year
        const sortedQuarters = [...quarters].sort((a, b) => b.total - a.total);
        const highestQuarter = sortedQuarters[0];

        // Quarter over quarter comparison
        const prevQuarterId = activeQ.id === 1 ? null : activeQ.id - 1;
        const prevQuarter = prevQuarterId ? quarters.find(q => q.id === prevQuarterId) : null;
        let qoqChange = 0;
        if (prevQuarter && prevQuarter.total > 0) {
            qoqChange = Math.round(((activeQ.total - prevQuarter.total) / prevQuarter.total) * 1000) / 10;
        }

        return {
            year,
            quarters,
            activeQuarter: activeQ,
            highestQuarter,
            prevQuarter,
            qoqChange,
            categoryBreakdown: activeQuarterBreakdown,
            topCategory: activeQuarterBreakdown.topCategory,
            labels: quarters.map(q => q.short),
            totals: quarters.map(q => q.total)
        };
    }

    /**
     * HALF-YEARLY ANALYSIS
     * H1: Jan - Jun (months 0 to 5)
     * H2: Jul - Dec (months 6 to 11)
     */
    static getHalfYearlyAnalysis(userId, accountId = 'all', year, targetHalf = 1) {
        const expenses = this.getFilteredExpenses(userId, accountId, year);
        const halves = [
            { id: 1, label: 'H1 (Jan - Jun)', short: 'H1', months: [0, 1, 2, 3, 4, 5], total: 0, count: 0, expenses: [] },
            { id: 2, label: 'H2 (Jul - Dec)', short: 'H2', months: [6, 7, 8, 9, 10, 11], total: 0, count: 0, expenses: [] }
        ];

        expenses.forEach(e => {
            const parts = this.parseDateParts(e.date);
            const m = parts.month;
            const half = halves.find(h => h.months.includes(m));
            if (half) {
                const amt = parseFloat(e.amount) || 0;
                half.total += amt;
                half.count += 1;
                half.expenses.push(e);
            }
        });

        halves.forEach(h => {
            h.total = Math.round(h.total * 100) / 100;
        });

        const activeHalf = halves.find(h => h.id === parseInt(targetHalf, 10)) || halves[0];
        const activeHalfBreakdown = this.getCategoryBreakdown(activeHalf.expenses);

        // Comparison between H1 and H2
        const totalYear = halves[0].total + halves[1].total;
        const h1Share = totalYear > 0 ? Math.round((halves[0].total / totalYear) * 100) : 0;
        const h2Share = totalYear > 0 ? Math.round((halves[1].total / totalYear) * 100) : 0;

        return {
            year,
            halves,
            activeHalf,
            h1Share,
            h2Share,
            categoryBreakdown: activeHalfBreakdown,
            topCategory: activeHalfBreakdown.topCategory,
            labels: halves.map(h => h.short),
            totals: halves.map(h => h.total)
        };
    }

    /**
     * YEARLY ANALYSIS
     * Full year aggregation, 12-month graph, annual category breakdown,
     * and the definitive TOP SPENDING CATEGORY of the year.
     */
    static getYearlyAnalysis(userId, accountId = 'all', year) {
        const expenses = this.getFilteredExpenses(userId, accountId, year);
        const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
        const monthlyTotals = new Array(12).fill(0);

        let totalExpense = 0;

        expenses.forEach(e => {
            const parts = this.parseDateParts(e.date);
            const m = parts.month;
            const amt = parseFloat(e.amount) || 0;
            if (m >= 0 && m < 12) {
                monthlyTotals[m] += amt;
            }
            totalExpense += amt;
        });

        for (let i = 0; i < 12; i++) {
            monthlyTotals[i] = Math.round(monthlyTotals[i] * 100) / 100;
        }

        const categoryBreakdown = this.getCategoryBreakdown(expenses);

        // Find peak spending month
        let peakMonthIdx = 0;
        let peakMonthAmount = monthlyTotals[0];
        monthlyTotals.forEach((amt, idx) => {
            if (amt > peakMonthAmount) {
                peakMonthAmount = amt;
                peakMonthIdx = idx;
            }
        });

        // Average monthly spend
        const avgMonthlySpend = Math.round((totalExpense / 12) * 100) / 100;

        return {
            year,
            totalExpense: Math.round(totalExpense * 100) / 100,
            transactionCount: expenses.length,
            monthlyLabels: monthNames,
            monthlyTotals,
            peakMonthName: monthNames[peakMonthIdx],
            peakMonthAmount,
            avgMonthlySpend,
            categoryBreakdown,
            topCategory: categoryBreakdown.topCategory
        };
    }

    /**
     * ACCOUNT-WISE BREAKDOWN
     * Calculates total spent and balance per individual account
     */
    static getAccountWiseBreakdown(userId) {
        const accounts = StorageManager.getAccounts(userId);
        const expenses = StorageManager.getExpenses(userId);

        const accountStats = accounts.map(acc => {
            const accExpenses = expenses.filter(e => e.accountId === acc.id);
            const totalSpent = accExpenses.reduce((sum, e) => sum + (parseFloat(e.amount) || 0), 0);
            return {
                id: acc.id,
                bankName: acc.bankName,
                accountName: acc.accountName,
                accountNumber: acc.accountNumber,
                accountType: acc.accountType,
                colorTheme: acc.colorTheme,
                currency: acc.currency,
                currentBalance: Math.round(acc.currentBalance * 100) / 100,
                totalSpent: Math.round(totalSpent * 100) / 100,
                transactionCount: accExpenses.length
            };
        });

        const totalBalanceAll = accountStats.reduce((sum, a) => sum + a.currentBalance, 0);
        const totalSpentAll = accountStats.reduce((sum, a) => sum + a.totalSpent, 0);

        return {
            accounts: accountStats,
            totalBalanceAll: Math.round(totalBalanceAll * 100) / 100,
            totalSpentAll: Math.round(totalSpentAll * 100) / 100
        };
    }
}

window.AnalyticsEngine = AnalyticsEngine;
