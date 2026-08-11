package com.example.expenses;

public final class Expense {

    public final String category;
    public final double amount;
    public final String note;

    public Expense(String category, double amount, String note) {
        this.category = category;
        this.amount = amount;
        this.note = note;
    }

    public Expense(String category, double amount) {
        this(category, amount, "");
    }

    public boolean isValid() {
        return amount > 0 && category != null && !category.trim().isEmpty();
    }
}
