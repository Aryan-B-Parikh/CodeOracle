package com.example.legacy;

public final class LegacyApp {

    public static void main(String[] args) {
        PaymentService p = new PaymentService("checkout", 5000);
        p.charge(999, 1, "IN");
        System.out.println(AuditLog.transactionCount());
    }
}
