package com.example.modern;

import java.util.List;
import static java.util.Collections.emptyList;
import java.io.*;

class Customer {
    public String name() {
        return "base";
    }
}

/**
 * Premium customer.
 *
 * @param tier tier code
 * @return discount as fraction
 */
class PremiumCustomer extends Customer implements Serializable, Comparable<PremiumCustomer> {
    public double discount() {
        return 0.2;
    }

    @Override
    public int compareTo(PremiumCustomer other) {
        return 0;
    }
}

interface Shape extends Cloneable {
    double area();
}

enum Color implements Serializable {
    RED,
    GREEN;

    public String hex() {
        return "#FF0000";
    }
}

record Point(int x, int y) implements Serializable {
    public int sum() {
        return x + y;
    }
}

@interface Marker {
    String value() default "x";
}
