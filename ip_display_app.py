# This script is now a wrapper around the hardware_controller for standalone IP display.
# The core logic for hardware interaction has been moved to app.hardware_controller.

import time
import sys

# Adjust path to import from parent directory's 'app' package if run directly from project root
# This might be needed if you run `python ip_display_app.py` from the root,
# and `app` is not automatically in the Python path.
# However, if `ip_display_app.py` is moved into `app` or project is structured as a package,
# this might not be necessary or might need adjustment.
# For simplicity, assuming it can find 'app.hardware_controller' if project root is in PYTHONPATH
# or if this script is run as part of a package.
try:
    from app.hardware_controller import (
        init_hardware,
        shutdown_hardware,
        display_message,
        play_sound,
        get_ip_addresses_string,
        RPI_HW_AVAILABLE
    )
except ImportError:
    # Try adding project root to path if running script directly from its location
    # and app folder is sibling to it. This is a common scenario.
    # This is a bit of a hack for standalone script execution.
    # Better to run as `python -m ip_display_app` if it's part of a package,
    # or ensure PYTHONPATH is set.
    import os
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    try:
        from app.hardware_controller import (
            init_hardware,
            shutdown_hardware,
            display_message,
            play_sound,
            get_ip_addresses_string,
            RPI_HW_AVAILABLE
        )
    except ImportError as e:
        print("Error: Could not import 'app.hardware_controller'.")
        print("Make sure this script is run from the project root directory or the 'app' package is in PYTHONPATH.")
        print(f"Details: {e}")
        sys.exit(1)


IP_REFRESH_INTERVAL = 30  # Seconds

def main_ip_display():
    print("Starting Standalone IP Display (using hardware_controller)...")

    # Initialize hardware with a specific name for this utility
    if not init_hardware(app_name="IP Display Util", server_ip="", server_port=""):
        print("Failed to initialize hardware via controller. Exiting IP display utility.")
        # shutdown_hardware() # Call shutdown to attempt cleanup if partial init occurred
        return

    if not RPI_HW_AVAILABLE:
        print("Running in MOCK hardware mode. Check console for simulated LCD/Buzzer output.")

    try:
        last_ip_str = ""
        display_message("IP Display Util", "Fetching IP...", clear_first=True)
        play_sound("startup") # Play startup sound via controller
        time.sleep(1)

        while True:
            current_ip_str = get_ip_addresses_string() # Use controller's IP fetcher

            if current_ip_str != last_ip_str:
                print(f"IPs: {current_ip_str}")
                display_message("IP:", current_ip_str, clear_first=True) # Display using controller
                last_ip_str = current_ip_str

            # Wait for the refresh interval, sleeping in 1s chunks for responsiveness
            for _ in range(IP_REFRESH_INTERVAL):
                time.sleep(1)
                # In a more complex app, you might check for an exit signal here

    except KeyboardInterrupt:
        print("\nStandalone IP Display shutting down (Ctrl+C pressed)...")
    except Exception as e:
        print(f"An error occurred in Standalone IP Display: {e}")
        if RPI_HW_AVAILABLE:
            display_message("IP Display Error", str(e)[:16], clear_first=True)
            play_sound("alert")
    finally:
        print("Calling hardware shutdown via controller...")
        # The shutdown_hardware function from the controller will handle LCD messages, sounds, and GPIO cleanup.
        shutdown_hardware()
        print("Standalone IP Display finished.")

if __name__ == "__main__":
    main_ip_display()
