package com.example.billing;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public final class Database {

    private static final Map<String, List<Map<String, Object>>> TABLES = new HashMap<>();
    private static boolean connected = false;

    private Database() {
    }

    public static void connect() {
        connected = true;
    }

    public static void insert(String table, Map<String, Object> row) {
        TABLES.computeIfAbsent(table, k -> new ArrayList<>()).add(row);
    }

    public static List<Map<String, Object>> all(String table) {
        return new ArrayList<>(TABLES.getOrDefault(table, List.of()));
    }

    public static boolean isConnected() {
        return connected;
    }
}
