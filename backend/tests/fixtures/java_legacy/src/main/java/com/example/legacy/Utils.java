package com.example.legacy;

public final class Utils {

    private Utils() {
    }

    public static double legacyCalc(double a, double b, double c) {
        double r;
        if (a > 100) {
            r = a * 0.1;
        } else {
            r = 0;
        }
        return a + b + c - r;
    }

    public static int parseAmount(String s) {
        int x = 0;
        for (char ch : s.toCharArray()) {
            if (Character.isDigit(ch)) {
                x = x * 10 + (ch - '0');
            }
        }
        return x;
    }
}
