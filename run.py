import click
import atexit
import socket # For getting local IP
from app import create_app, db
from app.models import User, Student, Exam, Log # Import models to ensure they are known to Flask-Migrate
from app.hardware_controller import init_hardware, shutdown_hardware, display_message, play_sound, RPI_HW_AVAILABLE

app = create_app()

# --- Hardware Integration ---
def get_local_ip_for_display():
    """Attempts to get the local IP address for display purposes."""
    s = None
    try:
        # Try connecting to an external server to find the primary interface IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80)) # Google DNS
        ip = s.getsockname()[0]
    except Exception:
        # Fallback: Try getting IP from hostname (might be 127.0.0.1 or internal)
        try:
            hostname = socket.gethostname()
            ip = socket.gethostbyname(hostname)
        except socket.gaierror:
            ip = "?.?.?.?" # If all else fails
    finally:
        if s:
            s.close()
    return ip

def initialize_app_hardware():
    """Initializes hardware components when the Flask app starts."""
    if RPI_HW_AVAILABLE:
        server_ip = get_local_ip_for_display()
        # Assuming Flask runs on port 5000 by default if not specified
        server_port = app.config.get("SERVER_PORT", "5000")
        if init_hardware(app_name=app.name.capitalize(), server_ip=server_ip, server_port=str(server_port)):
            print("Hardware initialized successfully for Flask app.")
            # Optional: display_message can be called here if a specific startup message is desired beyond init_hardware's default
        else:
            print("Hardware initialization failed for Flask app.")
    else:
        print("Flask app running in mock hardware mode (RPi hardware not detected/initialized).")

def cleanup_app_hardware():
    """Cleans up hardware components when the Flask app shuts down."""
    if RPI_HW_AVAILABLE:
        print("Shutting down hardware on Flask app exit...")
        shutdown_hardware()
    else:
        print("Flask app (mock hardware mode) is shutting down.")

# Register hardware initialization and cleanup
# Note: init_hardware is called before app.run() to ensure it's done at startup.
# atexit handles cleanup on normal interpreter exit.

# --- End Hardware Integration ---

@app.shell_context_processor
def make_shell_context():
    return {'db': db, 'User': User, 'Student': Student, 'Exam': Exam, 'Log': Log}

@app.cli.command("create-admin")
@click.argument("username")
@click.argument("password")
def create_admin_command(username, password):
    """Creates a new admin user."""
    if User.query.filter_by(username=username).first():
        print(f"Admin user {username} already exists.")
        return
    admin = User(username=username)
    admin.set_password(password)
    db.session.add(admin)
    db.session.commit()
    print(f"Admin user {username} created successfully.")

if __name__ == '__main__':
    # Initialize hardware before starting the Flask development server
    initialize_app_hardware()
    # Register cleanup function to be called on exit
    atexit.register(cleanup_app_hardware)

    # Get host and port from Flask config or use defaults
    # HOST and PORT can be set in config.py or via environment variables typically
    host = app.config.get('HOST', '0.0.0.0')
    port = app.config.get('PORT', 5000)
    debug = app.config.get('DEBUG', False)

    print(f"Starting Flask app on {host}:{port} (Debug: {debug})")
    app.run(host=host, port=port, debug=debug)
