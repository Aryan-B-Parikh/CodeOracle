package com.example.billing;

import java.util.Map;

public final class TaxCalculator {

    private static final Map<String, Double> RATES =
        Map.of("US", 0.08, "UK", 0.20, "IN", 0.05);

    private TaxCalculator() {
    }

    public static double rateFor(String region) {
        String key = region.toUpperCase();
        if (!RATES.containsKey(key)) {
            throw new IllegalArgumentException("unknown region: " + region);
        }
        return RATES.get(key);
    }

    public static double calculateTax(double amount, String region, boolean exempt) {
        if (exempt) {
            return 0.0;
        }
        return round2(amount * rateFor(region));
    }

    static double round2(double value) {
        return Math.round(value * 100.0) / 100.0;
    }
}
