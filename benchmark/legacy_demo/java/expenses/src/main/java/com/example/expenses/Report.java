package com.example.expenses;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public final class Report {

    public static Map<String, Double> byCategory(List<Expense> expenses) {
        Map<String, Double> out = new LinkedHashMap<>();
        for (Expense e : expenses) {
            out.merge(e.category, e.amount, Double::sum);
        }
        return out;
    }

    public static double percentOfBudget(double spent, double budget) {
        if (budget <= 0) {
            throw new IllegalArgumentException("budget must be positive");
        }
        return (spent / budget) * 100.0;
    }

    public static String summaryLine(List<Expense> expenses, double cap) {
        double spent = 0.0;
        for (Expense e : expenses) {
            spent += e.amount;
        }
        double pct = cap > 0 ? (spent / cap * 100.0) : 0.0;
        return String.format("spent=%.2f pct=%.1f", spent, pct);
    }
}
