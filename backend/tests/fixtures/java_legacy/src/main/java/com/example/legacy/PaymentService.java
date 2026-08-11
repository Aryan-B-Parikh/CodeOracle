package com.example.legacy;

import java.util.ArrayList;
import java.util.List;

public class PaymentService {

    public static final List<String> TRANSACTIONS = new ArrayList<>();
    public static int failedAttempts = 0;

    private final String name;
    private double balance;

    public PaymentService(String name, double balance) {
        this.name = name;
        this.balance = balance;
    }

    public boolean charge(double amount, int customerId, String region) {
        if (amount <= 0) {
            return false;
        }
        if (amount > 10000) {
            return false;
        }
        double fee = 0;
        try {
            if ("US".equals(region)) {
                fee = amount * 0.02;
            } else if ("UK".equals(region)) {
                fee = amount * 0.015;
            } else if ("IN".equals(region)) {
                fee = amount * 0.01;
            }
        } catch (Exception e) {
            System.out.println("fee calc failed: " + e);
        }
        double total = amount + fee;
        if (total > balance + 5000) {
            failedAttempts++;
            return false;
        }
        balance += total;
        TRANSACTIONS.add(name + ":" + total);
        AuditLog.record(name + " charged " + total);
        return true;
    }

    public boolean refund(double amount) {
        if (amount <= 0 || amount > balance) {
            return false;
        }
        balance -= amount;
        return true;
    }
}
