import socket
import redis
import sqlite3
import threading
import signal
import sys

DB_FILE = "dns_records.db"
REDIS_CHANNEL = "dns_updates"
PENDING_UPDATES_KEY = "pending_updates"

# Connect to Redis
try:
    redis_client = redis.StrictRedis(host='localhost', port=6379, decode_responses=True)
    redis_client.ping()  # Check if Redis is running
    print("[INFO] Connected to Redis successfully.")
except redis.ConnectionError as e:
    print(f"[ERROR] Could not connect to Redis: {e}")
    sys.exit(1)

# Graceful exit handler
def handle_exit(signal, frame):
    print("\n[INFO] Shutting down Primary DNS Server...")
    sys.exit(0)

signal.signal(signal.SIGINT, handle_exit)

def init_db():
    """Initialize the SQLite database."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dns_records (
            domain TEXT NOT NULL,
            record_type TEXT NOT NULL,
            value TEXT NOT NULL,
            PRIMARY KEY (domain, record_type)
        )
    """)
    conn.commit()
    conn.close()
    print("[INFO] SQLite database initialized.")

def add_record(domain, record_type, value):
    """Add a DNS record to the database."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO dns_records (domain, record_type, value) VALUES (?, ?, ?)
    """, (domain, record_type, value))
    conn.commit()
    conn.close()

    cache_key = f"{domain}:{record_type}"
    redis_client.setex(cache_key, 3600, value)
    redis_client.publish(REDIS_CHANNEL, f"ADD:{domain}:{record_type}:{value}")
    return f"Record added: {record_type} record for {domain} -> {value}"

def update_record(domain, record_type, value):
    """Update a DNS record in the database."""
    return add_record(domain, record_type, value)

def delete_record(domain, record_type):
    """Delete a DNS record from the database."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        DELETE FROM dns_records WHERE domain = ? AND record_type = ?
    """, (domain, record_type))
    conn.commit()
    conn.close()

    cache_key = f"{domain}:{record_type}"
    redis_client.delete(cache_key)
    redis_client.publish(REDIS_CHANNEL, f"DELETE:{domain}:{record_type}")
    return f"Record deleted: {record_type} record for {domain}"

def query_record(domain, record_type):
    """Query a DNS record from the cache or database."""
    cache_key = f"{domain}:{record_type}"
    cached_value = redis_client.get(cache_key)
    if cached_value:
        return f"DNS Response (from cache): {record_type} record for {domain} -> {cached_value}"

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT value FROM dns_records WHERE domain = ? AND record_type = ?
    """, (domain, record_type))
    result = cursor.fetchone()
    conn.close()

    if result:
        redis_client.setex(cache_key, 3600, result[0])
        return f"DNS Response: {record_type} record for {domain} -> {result[0]}"
    return "Record not found."

def handle_pending_updates():
    """Process pending updates from the secondary server."""
    print("[INFO] Checking for pending updates from the secondary server...")
    while True:
        update = redis_client.rpop(PENDING_UPDATES_KEY)
        if not update:
            break  # No more pending updates

        try:
            action, domain, record_type, *value = update.split(":")
            if action == "ADD" or action == "UPDATE":
                add_record(domain, record_type, value[0])
                print(f"[INFO] Processed {action.lower()} for {domain}:{record_type} -> {value[0]}")
            elif action == "DELETE":
                delete_record(domain, record_type)
                print(f"[INFO] Processed delete for {domain}:{record_type}")
            else:
                print(f"[WARN] Unknown action in pending update: {update}")
        except Exception as e:
            print(f"[ERROR] Failed to process pending update: {update} | Error: {e}")

def handle_client(client_socket, client_address):
    """Handle incoming client requests."""
    print(f"[INFO] Connection established with {client_address}")
    try:
        query = client_socket.recv(1024).decode()
        if query.startswith("ADD:"):
            try:
                _, domain, record_type, value = query.split(":")
                response = add_record(domain, record_type, value)
            except ValueError:
                response = "[ERROR] Malformed ADD query. Use the format: ADD:<domain>:<record_type>:<value>"
        elif query.startswith("UPDATE:"):
            try:
                _, domain, record_type, value = query.split(":")
                response = update_record(domain, record_type, value)
            except ValueError:
                response = "[ERROR] Malformed UPDATE query. Use the format: UPDATE:<domain>:<record_type>:<value>"
        elif query.startswith("DELETE:"):
            try:
                _, domain, record_type = query.split(":")
                response = delete_record(domain, record_type)
            except ValueError:
                response = "[ERROR] Malformed DELETE query. Use the format: DELETE:<domain>:<record_type>"
        else:
            try:
                domain, record_type = query.split(":")
                response = query_record(domain, record_type)
            except ValueError:
                response = "[ERROR] Malformed query. Use the format: <domain>:<record_type>"
        client_socket.sendall(response.encode())
    except Exception as e:
        print(f"[ERROR] {e}")
        client_socket.sendall(f"[ERROR] Internal server error: {e}".encode())
    finally:
        client_socket.close()
        print(f"[INFO] Connection closed with {client_address}")

def start_server():
    """Start the primary DNS server."""
    init_db()
    handle_pending_updates()  # Process pending updates on startup
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(("127.0.0.1", 8053))
    server_socket.listen(5)
    print("[INFO] Primary DNS Server is listening on 127.0.0.1:8053...")
    try:
        while True:
            client_socket, client_address = server_socket.accept()
            client_thread = threading.Thread(target=handle_client, args=(client_socket, client_address))
            client_thread.start()
    except KeyboardInterrupt:
        print("\n[INFO] Server shutting down...")
    finally:
        server_socket.close()

if __name__ == "__main__":
    start_server()
