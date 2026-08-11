package com.example.billing;

import java.util.List;
import java.util.Map;

public final class Invoice {

    public static double subtotal(List<Map<String, Double>> items) {
        double total = 0.0;
        for (Map<String, Double> item : items) {
            total += item.get("price") * item.get("quantity");
        }
        return total;
    }

    public static double discount(double subtotal, Customer customer) {
        if (subtotal > 10000) {
            return subtotal * 0.10;
        }
        if (customer.isVip()) {
            return subtotal * 0.05;
        }
        return 0.0;
    }

    public static double total(double subtotal, Customer customer, String region, boolean exempt) {
        double disc = discount(subtotal, customer);
        double tax = TaxCalculator.calculateTax(subtotal - disc, region, exempt);
        return TaxCalculator.round2(subtotal - disc + tax);
    }
}
