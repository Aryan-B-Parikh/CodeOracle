package com.example.billing;

import static org.junit.Assert.assertEquals;

import org.junit.Test;

public class TaxCalculatorTest {

    @Test
    public void calculatesUsTax() {
        assertEquals(8.0, TaxCalculator.calculateTax(100, "US", false), 0.001);
    }

    @Test
    public void exemptIsZero() {
        assertEquals(0.0, TaxCalculator.calculateTax(100, "IN", true), 0.001);
    }

    @Test(expected = IllegalArgumentException.class)
    public void unknownRegionThrows() {
        TaxCalculator.calculateTax(100, "XX", false);
    }
}
