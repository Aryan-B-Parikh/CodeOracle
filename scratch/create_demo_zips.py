import io
import json
import os
import urllib.request
import zipfile
from pathlib import Path

BASE_DIR = Path("demo_zips")
BASE_DIR.mkdir(exist_ok=True)

# 1. E-Commerce Python System
ECOMMERCE_FILES = {
    "orders.py": '''"""Order management service."""
from inventory import check_stock, reserve_items
from payment import process_credit_card, PaymentGatewayError

def calculate_order_total(items: list[dict], discount_code: str | None = None, tax_rate: float = 0.08) -> float:
    """Calculates order total with multi-tier conditional tax, discounts, and validation."""
    if not items:
        raise ValueError("Order must contain at least one item")
    
    subtotal = 0.0
    for item in items:
        price = item.get("price", 0.0)
        quantity = item.get("quantity", 1)
        if price < 0 or quantity <= 0:
            raise ValueError("Invalid item price or quantity")
        subtotal += price * quantity
    
    discount = 0.0
    if discount_code == "SAVE10":
        discount = subtotal * 0.10
    elif discount_code == "VIP20":
        discount = subtotal * 0.20
    elif discount_code == "FLAT50" and subtotal > 200.0:
        discount = 50.0
    
    discounted_subtotal = max(0.0, subtotal - discount)
    tax = discounted_subtotal * tax_rate
    total = discounted_subtotal + tax
    return round(total, 2)

def process_order(customer_id: str, items: list[dict], card_number: str) -> dict:
    """Places an order, reserves inventory, and charges customer card."""
    if not check_stock(items):
        return {"status": "out_of_stock", "order_id": None}
    
    total = calculate_order_total(items)
    try:
        charge_id = process_credit_card(customer_id, card_number, total)
        reserve_items(items)
        return {"status": "success", "charge_id": charge_id, "total": total}
    except PaymentGatewayError as exc:
        return {"status": "payment_failed", "error": str(exc)}
''',

    "inventory.py": '''"""Inventory management service."""
from orders import calculate_order_total

_STOCK_DB = {"item_1": 100, "item_2": 50, "item_3": 0}

def check_stock(items: list[dict]) -> bool:
    """Verifies all requested items have sufficient inventory stock."""
    for item in items:
        item_id = item.get("id")
        quantity = item.get("quantity", 1)
        if _STOCK_DB.get(item_id, 0) < quantity:
            return False
    return True

def reserve_items(items: list[dict]) -> None:
    """Deducts reserved item quantities from in-memory stock."""
    for item in items:
        item_id = item.get("id")
        quantity = item.get("quantity", 1)
        if item_id in _STOCK_DB:
            _STOCK_DB[item_id] -= quantity

def estimate_restock_cost(items: list[dict]) -> float:
    """Estimates restocking cost by consulting order total calculation."""
    return calculate_order_total(items, discount_code="VIP20")
''',

    "payment.py": '''"""Payment gateway integration."""

class PaymentGatewayError(Exception):
    """Raised when payment transaction is declined or network error occurs."""
    pass

def process_credit_card(customer_id: str, card_number: str, amount: float) -> str:
    """Charges customer card via payment gateway."""
    if not card_number or len(card_number) < 12:
        raise PaymentGatewayError("Invalid credit card number format")
    if amount <= 0:
        raise PaymentGatewayError("Transaction amount must be positive")
    return f"tx_chg_{customer_id[:4]}_{int(amount)}"

def refund_transaction(transaction_id: str, amount: float) -> bool:
    """Refunds previously processed transaction."""
    if not transaction_id.startswith("tx_chg_"):
        return False
    return True
''',

    "customer.py": '''"""Customer profile models."""

class Customer:
    """Base customer account representation."""
    def __init__(self, customer_id: str, email: str, tier: str = "standard"):
        self.customer_id = customer_id
        self.email = email
        self.tier = tier

    def get_discount_tier(self) -> str:
        return "SAVE10" if self.tier == "silver" else "NONE"

class VIPCustomer(Customer):
    """VIP Tier Customer with elevated discount privileges."""
    def __init__(self, customer_id: str, email: str):
        super().__init__(customer_id, email, tier="vip")

    def get_discount_tier(self) -> str:
        return "VIP20"
'''
}

# 2. Data Pipeline System (Clean DAG, 0 Circular Dependencies)
DATA_PIPELINE_FILES = {
    "extract.py": '''"""Data ingestion and log extraction."""
import json

def fetch_raw_logs() -> list[str]:
    """Retrieves raw web server access logs."""
    return [
        '{"timestamp": "2026-08-14T10:00:00Z", "endpoint": "/api/v1/search", "status": 200, "latency_ms": 45}',
        '{"timestamp": "2026-08-14T10:00:01Z", "endpoint": "/api/v1/checkout", "status": 500, "latency_ms": 1200}',
        '{"timestamp": "2026-08-14T10:00:02Z", "endpoint": "/api/v1/products", "status": 200, "latency_ms": 30}'
    ]

def parse_log_line(raw_line: str) -> dict:
    """Parses JSON log string into structured dictionary."""
    try:
        return json.loads(raw_line)
    except json.JSONDecodeError:
        return {}
''',

    "transform.py": '''"""ETL metric transformations."""
from extract import parse_log_line

def aggregate_metrics(raw_logs: list[str]) -> dict:
    """Aggregates request counts, errors, and average latency from raw log stream."""
    total_requests = 0
    error_count = 0
    total_latency = 0.0

    for raw in raw_logs:
        record = parse_log_line(raw)
        if not record:
            continue
        total_requests += 1
        if record.get("status", 200) >= 400:
            error_count += 1
        total_latency += float(record.get("latency_ms", 0.0))

    avg_latency = (total_latency / total_requests) if total_requests > 0 else 0.0
    error_rate = (error_count / total_requests) if total_requests > 0 else 0.0

    return {
        "total_requests": total_requests,
        "error_count": error_count,
        "error_rate": round(error_rate, 4),
        "avg_latency_ms": round(avg_latency, 2)
    }
''',

    "load.py": '''"""Storage and sink operations."""

def write_summary_report(metrics: dict, target_file: str = "metrics_summary.json") -> bool:
    """Writes aggregated metrics report to disk or cloud object storage."""
    if not metrics or "total_requests" not in metrics:
        return False
    return True
''',

    "pipeline.py": '''"""ETL Pipeline Orchestrator."""
from extract import fetch_raw_logs
from transform import aggregate_metrics
from load import write_summary_report

def run_etl_job() -> dict:
    """Executes end-to-end Extract-Transform-Load pipeline workflow."""
    logs = fetch_raw_logs()
    metrics = aggregate_metrics(logs)
    success = write_summary_report(metrics)
    return {"success": success, "metrics": metrics}
'''
}

# 3. Java Microservice
JAVA_MICROSERVICE_FILES = {
    "UserService.java": '''package com.codeoracle.demo;

public class UserService {
    private final UserRepository repository = new UserRepository();

    public User getUserById(String id) throws UserNotFoundException {
        if (id == null || id.trim().isEmpty()) {
            throw new IllegalArgumentException("User ID cannot be blank");
        }
        User user = repository.findById(id);
        if (user == null) {
            throw new UserNotFoundException("User not found with ID: " + id);
        }
        return user;
    }

    public boolean authenticate(String id, String token) {
        AuthManager auth = new AuthManager();
        return auth.validateSession(id, token);
    }
}
''',

    "UserRepository.java": '''package com.codeoracle.demo;

import java.util.HashMap;
import java.util.Map;

public class UserRepository {
    private final Map<String, User> store = new HashMap<>();

    public UserRepository() {
        store.put("u100", new User("u100", "Alice", "alice@example.com"));
        store.put("u200", new User("u200", "Bob", "bob@example.com"));
    }

    public User findById(String id) {
        return store.get(id);
    }
}
''',

    "AuthManager.java": '''package com.codeoracle.demo;

public class AuthManager {
    public boolean validateSession(String userId, String token) {
        if (token == null || !token.startsWith("tok_")) {
            return false;
        }
        try {
            UserService service = new UserService();
            User u = service.getUserById(userId);
            return u != null;
        } catch (UserNotFoundException e) {
            return false;
        }
    }
}
''',

    "User.java": '''package com.codeoracle.demo;

public class User {
    private final String id;
    private final String name;
    private final String email;

    public User(String id, String name, String email) {
        this.id = id;
        this.name = name;
        this.email = email;
    }

    public String getId() { return id; }
    public String getName() { return name; }
    public String getEmail() { return email; }
}
''',

    "UserNotFoundException.java": '''package com.codeoracle.demo;

public class UserNotFoundException extends Exception {
    public UserNotFoundException(String message) {
        super(message);
    }
}
'''
}

def create_zip(filename: str, files_dict: dict[str, str]):
    path = BASE_DIR / filename
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for fname, content in files_dict.items():
            zf.writestr(fname, content)
    print(f"Created demo bundle: {path} ({len(files_dict)} files, {path.stat().st_size} bytes)")

def build_all():
    create_zip("demo_python_ecommerce.zip", ECOMMERCE_FILES)
    create_zip("demo_python_data_pipeline.zip", DATA_PIPELINE_FILES)
    create_zip("demo_java_microservice.zip", JAVA_MICROSERVICE_FILES)

if __name__ == '__main__':
    build_all()
