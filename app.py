from flask import Flask, render_template, request, redirect, url_for, session, flash
import socket

app = Flask(__name__)
app.secret_key = "your_secret_key"

# Hardcoded credentials
USERNAME = "admin"
PASSWORD = "admin"

PRIMARY_SERVER = ("127.0.0.1", 8053)
SECONDARY_SERVER = ("127.0.0.1", 8054)

def send_query_to_server(query, fallback=False, operation="query"):
    """Send query to the appropriate server based on operation."""
    server = SECONDARY_SERVER if fallback else PRIMARY_SERVER
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.connect(server)
            sock.sendall(query.encode())
            response = sock.recv(1024).decode()
            return response
    except Exception as e:
        if not fallback:
            # Fallback to secondary server for ALL operations
            return send_query_to_server(query, fallback=True, operation=operation)
        return f"[ERROR] Could not connect to the {('secondary' if fallback else 'primary')} server: {e}"

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username == USERNAME and password == PASSWORD:
            session["logged_in"] = True
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid credentials. Please try again.")
    return render_template("login.html")

@app.route("/dashboard")
def dashboard():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    return render_template("dashboard.html")

@app.route("/query", methods=["GET", "POST"])
def query():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    response = None
    if request.method == "POST":
        domain = request.form.get("domain")
        record_type = request.form.get("record_type")
        query = f"{domain}:{record_type}"
        response = send_query_to_server(query, operation="query")
    return render_template("query.html", response=response)

@app.route("/add", methods=["GET", "POST"])
def add():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    response = None
    if request.method == "POST":
        domain = request.form.get("domain")
        record_type = request.form.get("record_type")
        value = request.form.get("value")
        query = f"ADD:{domain}:{record_type}:{value}"
        response = send_query_to_server(query, operation="add")
    return render_template("add.html", response=response)

@app.route("/update", methods=["GET", "POST"])
def update():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    response = None
    if request.method == "POST":
        domain = request.form.get("domain")
        record_type = request.form.get("record_type")
        value = request.form.get("value")
        query = f"UPDATE:{domain}:{record_type}:{value}"
        response = send_query_to_server(query, operation="update")
    return render_template("update.html", response=response)

@app.route("/delete", methods=["GET", "POST"])
def delete():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    response = None
    if request.method == "POST":
        domain = request.form.get("domain")
        record_type = request.form.get("record_type")
        query = f"DELETE:{domain}:{record_type}"
        response = send_query_to_server(query, operation="delete")
    return render_template("delete.html", response=response)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

if __name__ == "__main__":
    app.run(debug=True)
