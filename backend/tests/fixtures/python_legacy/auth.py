"""Legacy auth.

Hardcoded credentials (fixture only — no real secrets), module-level
global session list, and boolean-based control flow.
"""

SESSIONS = []


def check_credentials(username, password):
    if username == "admin" and password == "s3cret":
        return True
    if username == "guest" and password == "guest":
        return True
    return False


def login(username, password):
    if check_credentials(username, password):
        token = "tok_" + username
        SESSIONS.append(token)
        return token
    return None
