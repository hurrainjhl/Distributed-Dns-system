import socket
import redis
import sqlite3
import threading
import signal
import sys
import time

DB_FILE = "dns_records.db"
REDIS_CHANNEL = "dns_updates"
CACHE_TTL = 3600  # Cache Time-To-Live in seconds
PENDING_UPDATES_KEY = "pending_updates"

# Connect to Redis
try:
    redis_client = redis.StrictRedis(host="localhost", port=6379, db=0, decode_responses=True)
    redis_client.ping()
    print("[INFO] Connected to Redis successfully.")
except redis.ConnectionError as e:
    print(f"[ERROR] Could not connect to Redis: {e}")
    sys.exit(1)


# Graceful exit handler
def handle_exit(signal, frame):
    print("\n[INFO] Shutting down Secondary DNS Server...")
    sys.exit(0)

signal.signal(signal.SIGINT, handle_exit)


def init_db():
    """Initialize the SQLite database."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS dns_records (
            domain TEXT NOT NULL,
            record_type TEXT NOT NULL,
            value TEXT NOT NULL,
            PRIMARY KEY (domain, record_type)
        )
        """
    )
    conn.commit()
    conn.close()
    print("[INFO] SQLite database initialized.")


def add_record(domain, record_type, value):
    """Add a DNS record to the database."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO dns_records (domain, record_type, value) VALUES (?, ?, ?)",
            (domain, record_type, value),
        )
        conn.commit()
        conn.close()

        cache_key = f"{domain}:{record_type}"
        redis_client.setex(cache_key, CACHE_TTL, value)

        # Publish to Redis for primary server sync
        update_message = f"ADD:{domain}:{record_type}:{value}"
        redis_client.publish(REDIS_CHANNEL, update_message)
        redis_client.lpush(PENDING_UPDATES_KEY, update_message)  # Store pending update
        return f"Record added: {record_type} record for {domain} -> {value}"
    except Exception as e:
        return f"[ERROR] Failed to add record: {e}"


def update_record(domain, record_type, value):
    """Update a DNS record in the database."""
    return add_record(domain, record_type, value)


def delete_record(domain, record_type):
    """Delete a DNS record from the database."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM dns_records WHERE domain = ? AND record_type = ?", (domain, record_type)
        )
        conn.commit()
        conn.close()

        cache_key = f"{domain}:{record_type}"
        redis_client.delete(cache_key)

        # Publish to Redis for primary server sync
        update_message = f"DELETE:{domain}:{record_type}"
        redis_client.publish(REDIS_CHANNEL, update_message)
        redis_client.lpush(PENDING_UPDATES_KEY, update_message)  # Store pending update
        return f"Record deleted: {record_type} record for {domain}"
    except Exception as e:
        return f"[ERROR] Failed to delete record: {e}"


def query_record(domain, record_type):
    """Query a DNS record from the cache or database."""
    try:
        cache_key = f"{domain}:{record_type}"
        cached_value = redis_client.get(cache_key)
        if cached_value:
            return f"DNS Response (from cache): {record_type} record for {domain} -> {cached_value}"

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT value FROM dns_records WHERE domain = ? AND record_type = ?", (domain, record_type)
        )
        result = cursor.fetchone()
        conn.close()

        if result:
            redis_client.setex(cache_key, CACHE_TTL, result[0])
            return f"DNS Response: {record_type} record for {domain} -> {result[0]}"
        return "Record not found."
    except Exception as e:
        return f"[ERROR] Failed to query record: {e}"


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
    """Start the secondary DNS server."""
    init_db()

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        server_socket.bind(("127.0.0.1", 8054))
        server_socket.listen(5)
        print("[INFO] Secondary DNS Server is listening on 127.0.0.1:8054...")

        listener_thread = threading.Thread(target=listen_for_updates, daemon=True)
        listener_thread.start()

        while True:
            client_socket, client_address = server_socket.accept()
            client_thread = threading.Thread(target=handle_client, args=(client_socket, client_address))
            client_thread.start()
    except KeyboardInterrupt:
        print("\n[INFO] Server shutting down...")
    except Exception as e:
        print(f"[ERROR] {e}")
    finally:
        server_socket.close()


def listen_for_updates():
    """Listen for updates from Redis."""
    pubsub = redis_client.pubsub()
    pubsub.subscribe(REDIS_CHANNEL)
    print("[INFO] Listening for updates from Primary DNS Server...")
    for message in pubsub.listen():
        if message["type"] == "message":
            update_message = message["data"]
            print(f"[INFO] Received update: {update_message}")
            sync_with_primary(update_message)


def sync_with_primary(update_message):
    """Sync updates from the primary server via Redis."""
    try:
        action, domain, record_type, *value = update_message.split(":")
        cache_key = f"{domain}:{record_type}"

        if action == "ADD" or action == "UPDATE":
            redis_client.setex(cache_key, CACHE_TTL, value[0])
            print(f"[INFO] Synced {action.lower()} operation for {record_type} record of {domain}: {value[0]}")
        elif action == "DELETE":
            redis_client.delete(cache_key)
            print(f"[INFO] Synced delete operation for {record_type} record of {domain}")
        else:
            print(f"[WARN] Unknown action received: {action}")
    except Exception as e:
        print(f"[ERROR] Failed to sync with primary: {e}")


if __name__ == "__main__":
    start_server()
