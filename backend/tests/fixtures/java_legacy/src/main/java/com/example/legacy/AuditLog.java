package com.example.legacy;

public final class AuditLog {

    private AuditLog() {
    }

    public static int transactionCount() {
        return PaymentService.TRANSACTIONS.size();
    }

    public static void record(String message) {
        System.out.println("AUDIT " + message);
    }
}
