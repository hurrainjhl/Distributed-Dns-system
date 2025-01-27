# Distributed DNS System

## Overview
The Distributed DNS System is a robust, scalable project designed to manage DNS records efficiently across multiple servers. This project features a primary and secondary server architecture, along with client-side interactions for querying, adding, updating, and deleting DNS records. The system incorporates a web interface for user-friendly management and utilizes Redis for caching and inter-server communication.

---

## Project Structure
The project is organized into the following directories and files:

### Backend
Handles the server-side logic for DNS management.
- **`primary_server.py`**: Contains the code for the primary DNS server.
- **`secondary_server.py`**: Contains the code for the secondary DNS server.
- **`client.py`**: Allows client-side interactions with the DNS servers.
- **`dns_records.db`**: SQLite database file to store DNS records persistently.

### Static
Contains static assets like CSS for the web interface.
- **`css/style.css`**: Defines the styles for the web pages.

### Templates
Contains HTML templates for rendering the web interface.
- **`add.html`**: Page for adding DNS records.
- **`delete.html`**: Page for deleting DNS records.
- **`login.html`**: Login page for user authentication.
- **`update.html`**: Page for updating existing DNS records.
- **`query.html`**: Page for querying DNS records.
- **`dashboard.html`**: Dashboard for managing DNS records.
- **`base.html`**: Base template for consistent design across pages.

### Root Files
- **`app.py`**: Main application file that handles routing and connects the frontend to the backend.

---

## Features
- **Distributed Architecture**: Separation of primary and secondary DNS servers for redundancy.
- **Caching with Redis**: Reduces query response times by caching DNS records.
- **Web Interface**: Intuitive HTML pages for managing DNS records.
- **CRUD Operations**:
  - Add new DNS records.
  - Update existing DNS records.
  - Delete DNS records.
  - Query DNS records.
- **Real-time Synchronization**: Updates between primary and secondary servers are synchronized via Redis.
- **SQLite Database**: Persistent storage of DNS records.

---

## How It Works
### Backend Servers
1. **Primary Server**: Manages the authoritative database of DNS records and publishes updates to the secondary server via Redis.
2. **Secondary Server**: Syncs with the primary server and handles client queries using cached data.

### Client Interaction
Clients communicate with the servers using the following commands:
- **Add Record**: `ADD:<domain>:<record_type>:<value>`
- **Update Record**: `UPDATE:<domain>:<record_type>:<value>`
- **Delete Record**: `DELETE:<domain>:<record_type>`
- **Query Record**: `<domain>:<record_type>`

### Web Interface
Users can log in and manage DNS records using the web interface, which provides options to:
- View existing records.
- Add new records.
- Update or delete records.
- Query records.

---

## Installation and Usage
### Prerequisites
- Python 3.x
- Redis Server
- SQLite
- Required Python libraries (install via `requirements.txt`):
  ```bash
  pip install -r requirements.txt
  ```

### Setup
1. Clone the repository:
   ```bash
   git clone <https://github.com/hurrainjhl/Distributed-Dns-system>
   ```
2. Navigate to the project directory:
   ```bash
   cd distributed-dns-system
   ```
3. Initialize the SQLite database:
   ```bash
   python primary_server.py
   ```
4. Start the Redis server.

### Running the Servers
1. Start the primary server:
   ```bash
   python primary_server.py
   ```
2. Start the secondary server:
   ```bash
   python secondary_server.py
   ```
3. Run the web application:
   ```bash
   python app.py
   ```

### Access the Web Interface
Open a web browser and navigate to:
```
http://127.0.0.1:5000
```

---

## Contributions
Contributions are welcome! Feel free to fork the repository and submit pull requests.


---

## Acknowledgements
Special thanks to all contributors and open-source libraries used in this project.
