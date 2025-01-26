import socket
import logging
import signal
import sys
import time

PRIMARY_SERVER = ("127.0.0.1", 8053)
SECONDARY_SERVER = ("127.0.0.1", 8054)
RETRY_ATTEMPTS = 3
RETRY_DELAY = 2

# Configure logging
logging.basicConfig(filename="dns_client.log", level=logging.INFO, 
                    format="%(asctime)s - %(levelname)s - %(message)s")

def handle_exit(signal, frame):
    print("\n[INFO] Goodbye!")
    sys.exit(0)

signal.signal(signal.SIGINT, handle_exit)

def validate_query(query):
    query = query.strip().upper()  # Normalize to uppercase
    if query == "QUIT":
        return "QUIT"

    if query.startswith("ADD:"):
        parts = query.split(":")
        if len(parts) == 4:
            return "ADD"
        else:
            print("[ERROR] Malformed ADD query. Example: ADD:example.com:A:192.168.1.1")
            return None
    elif query.startswith("UPDATE:"):
        parts = query.split(":")
        if len(parts) == 4:
            return "UPDATE"
        else:
            print("[ERROR] Malformed UPDATE query. Example: UPDATE:example.com:A:192.168.1.1")
            return None
    elif query.startswith("DELETE:"):
        parts = query.split(":")
        if len(parts) == 3:
            return "DELETE"
        else:
            print("[ERROR] Malformed DELETE query. Example: DELETE:example.com:A")
            return None
    else:
        parts = query.split(":")
        if len(parts) == 2:
            return "QUERY"
        else:
            print("[ERROR] Malformed query. Example: example.com:A")
            return None

def send_query(server_address, query):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.connect(server_address)
            sock.sendall(query.encode())
            response = sock.recv(1024).decode()
            return response
    except ConnectionRefusedError as e:
        logging.warning(f"Failed to connect to {server_address} - {e}")
        print(f"[WARN] Failed to connect to {server_address} - {e}")
        return None

def query_server(query):
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        print(f"[INFO] Sending query to Primary DNS Server...")
        response = send_query(PRIMARY_SERVER, query)
        if response:
            logging.info(f"Query: {query} | Response: {response}")
            return response
        print(f"[WARN] Attempt {attempt}: Failed to connect to Primary Server.")
        print(f"[INFO] Retrying in {RETRY_DELAY} seconds...")
        time.sleep(RETRY_DELAY)

    print("[INFO] Primary server failed. Trying Secondary DNS Server...")
    response = send_query(SECONDARY_SERVER, query)
    if response:
        logging.info(f"Query: {query} | Response: {response}")
        return response

    print("[ERROR] Both servers are unavailable. Please try again later.")
    logging.error(f"Query: {query} | Response: Both servers unavailable.")
    return "[ERROR] Both servers are unavailable."

def main():
    print("[INFO] DNS Client started. Type 'quit' to exit.")
    while True:
        query = input("Enter DNS query or command (e.g., example.com:A, ADD:<domain>:<record_type>:<value>): ")
        query_type = validate_query(query)

        if query_type == "QUIT":
            print("[INFO] Goodbye!")
            break
        elif query_type:
            response = query_server(query)
            print(f"Server response: {response}")

if __name__ == "__main__":
    main()
