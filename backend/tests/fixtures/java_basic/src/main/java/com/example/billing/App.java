package com.example.billing;

public final class App {

    public static void main(String[] args) {
        Database.connect();
        Customer c = new Customer(1, "standard", 12000);
        System.out.println(Invoice.total(15000, c, "IN", false));
    }
}
