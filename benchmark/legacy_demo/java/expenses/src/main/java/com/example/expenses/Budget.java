package com.example.expenses;

import java.util.List;

public final class Budget {

    private final double monthlyCap;
    private final double categoryCap;

    public Budget(double monthlyCap, double categoryCap) {
        this.monthlyCap = monthlyCap;
        this.categoryCap = categoryCap;
    }

    public double categoryTotal(List<Expense> expenses, String category) {
        double total = 0.0;
        for (Expense e : expenses) {
            if (e.category.equals(category)) {
                total += e.amount;
            }
        }
        return total;
    }

    public double total(List<Expense> expenses) {
        double t = 0.0;
        for (Expense e : expenses) {
            t += e.amount;
        }
        return t;
    }

    public String status(double spent) {
        if (spent > monthlyCap) {
            return "OVER_BUDGET";
        }
        if (spent > monthlyCap * 0.8) {
            return "WARNING";
        }
        return "OK";
    }

    public boolean allows(Expense e, List<Expense> all) {
        double categorySpent = categoryTotal(all, e.category);
        if (categorySpent + e.amount > categoryCap) {
            return false;
        }
        if (total(all) + e.amount > monthlyCap) {
            return false;
        }
        return e.amount > 0;
    }
}
