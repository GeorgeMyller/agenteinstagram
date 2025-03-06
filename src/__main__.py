from src.handlers.app import app, disable_firewall

if __name__ == "__main__":
    disable_firewall()
    app.run(host="0.0.0.0", port=5000, debug=True)