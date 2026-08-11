package com.example.billing;

public final class Customer {

    private final int id;
    private final String tier;
    private final double spend;

    public Customer(int id, String tier, double spend) {
        this.id = id;
        this.tier = tier;
        this.spend = spend;
    }

    public boolean isVip() {
        return "vip".equals(tier) || spend >= 10000;
    }

    public int getId() {
        return id;
    }

    public String getTier() {
        return tier;
    }

    public double getSpend() {
        return spend;
    }
}
