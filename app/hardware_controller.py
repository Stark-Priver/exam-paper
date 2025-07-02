import time
import socket
import fcntl
import struct
try:
    import RPi.GPIO as GPIO
    from .lcd_i2c import LCD_I2C, DEFAULT_I2C_ADDR # Use relative import
    from .buzzer_pwm import PassiveBuzzer, DEFAULT_BUZZER_PIN # Use relative import
    RPI_HW_AVAILABLE = True
except (ImportError, RuntimeError) as e:
    print(f"Warning: Raspberry Pi specific hardware modules (RPi.GPIO, smbus) not found or error during import: {e}. Hardware controller will operate in mock mode.")
    RPI_HW_AVAILABLE = False

# Configuration
LCD_I2C_ADDRESS = DEFAULT_I2C_ADDR if RPI_HW_AVAILABLE else 0x27
BUZZER_GPIO_PIN = DEFAULT_BUZZER_PIN if RPI_HW_AVAILABLE else 18
NETWORK_INTERFACES = ['eth0', 'wlan0']  # Interfaces to check for IP

# Global hardware component instances
lcd = None
buzzer = None
gpio_initialized = False

def _get_ip_address(ifname):
    """
    Gets the IP address of a given network interface.
    Returns the IP address string or None if not found or interface is down.
    Mock implementation if not on RPi or network utils fail.
    """
    if not RPI_HW_AVAILABLE: # Or more specific check for socket availability if needed
        print(f"Mock mode: _get_ip_address({ifname}) -> returning '127.0.0.1' or None")
        if ifname == 'eth0':
            return '192.168.1.101' # Example
        elif ifname == 'wlan0':
            return '192.168.1.102' # Example
        return None

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        addr = socket.inet_ntoa(fcntl.ioctl(
            s.fileno(),
            0x8915,  # SIOCGIFADDR
            struct.pack('256s', ifname[:15].encode('utf-8'))
        )[20:24])
        return addr
    except IOError: # Interface not found or not up
        return None
    except Exception as e:
        print(f"Error getting IP for {ifname}: {e}")
        return None

def init_hardware(app_name="Flask App", server_ip="<IP_Pending>", server_port="<Port>"):
    """
    Initializes GPIO, LCD, and Buzzer.
    Displays a startup message on the LCD.
    Plays a startup sound.
    """
    global lcd, buzzer, gpio_initialized

    if not RPI_HW_AVAILABLE:
        print("Mock mode: init_hardware() called. Simulating hardware initialization.")
        # Create mock objects if needed for further interaction
        class MockLCD:
            def message(self, text, line, col=0): print(f"MockLCD: Line {line}, Col {col}: {text}")
            def clear(self): print("MockLCD: clear()")
            def backlight(self, on): print(f"MockLCD: backlight({on})")
            def display_off(self): print("MockLCD: display_off()")
        class MockBuzzer:
            def startup_sound(self): print("MockBuzzer: startup_sound()")
            def play_tone(self, freq, dur): print(f"MockBuzzer: play_tone({freq}Hz, {dur}s)")
            def cleanup(self): print("MockBuzzer: cleanup()")

        lcd = MockLCD()
        buzzer = MockBuzzer()
        gpio_initialized = True # Simulate success

        lcd.message(app_name, 1)
        lcd.message(f"{server_ip}:{server_port}", 2)
        buzzer.startup_sound()
        print("Mock hardware initialized.")
        return True

    if gpio_initialized:
        print("Hardware already initialized.")
        return True

    try:
        GPIO.setmode(GPIO.BCM)
        gpio_initialized = True
        print("GPIO mode set to BCM.")

        # Initialize LCD
        try:
            print(f"Initializing LCD at I2C address 0x{LCD_I2C_ADDRESS:02X}...")
            lcd = LCD_I2C(i2c_addr=LCD_I2C_ADDRESS)
            lcd.message("LCD Init OK", 1)
            print("LCD Initialized.")
            time.sleep(0.5)
        except Exception as e:
            print(f"Error initializing LCD: {e}")
            lcd = None # Ensure lcd is None if init fails

        # Initialize Buzzer
        try:
            print(f"Initializing Buzzer on GPIO {BUZZER_GPIO_PIN}...")
            buzzer = PassiveBuzzer(buzzer_pin=BUZZER_GPIO_PIN)
            print("Buzzer Initialized.")
            buzzer.beep(repeat=2, tone_duration=0.05, pause_duration=0.05, frequency=1500)
            if lcd:
                lcd.message("Buzzer Init OK", 2)
            time.sleep(0.5)
        except Exception as e:
            print(f"Error initializing Buzzer: {e}")
            if lcd:
                lcd.clear()
                lcd.message("Buzzer Init FAIL", 1)
                time.sleep(1)
            buzzer = None # Ensure buzzer is None if init fails

        if lcd and buzzer:
            print("LCD and Buzzer OK for Flask App.")
            lcd.clear()
            lcd.message(app_name[:16], 1) # Ensure app_name fits
            ip_info = f"{server_ip}:{server_port}"
            lcd.message(ip_info[:16], 2) # Ensure IP info fits
            buzzer.startup_sound()
            print(f"Displayed: {app_name} | {ip_info}")
        elif lcd:
            lcd.clear()
            lcd.message(app_name[:16], 1, 0)
            lcd.message("No Buzzer", 2, 0)
            print(f"Displayed: {app_name} | No Buzzer")
        elif buzzer:
            print("LCD failed, Buzzer OK. Playing alert for LCD failure.")
            buzzer.alert_sound()
        else:
            print("CRITICAL: Both LCD and Buzzer failed to initialize for Flask app.")
            return False

        return True

    except Exception as e:
        print(f"Error in init_hardware: {e}")
        gpio_initialized = False # Ensure this is false if setmode fails
        return False

def shutdown_hardware():
    """
    Cleans up GPIO resources, turns off LCD, and plays a shutdown sound.
    """
    global lcd, buzzer, gpio_initialized

    print("Shutting down hardware...")
    if not RPI_HW_AVAILABLE:
        print("Mock mode: shutdown_hardware() called.")
        if buzzer: buzzer.play_tone(100, 0.2) # Simulate shutdown sound
        if lcd:
            lcd.clear()
            lcd.message("Server Offline", 1)
            lcd.backlight(False)
            lcd.display_off()
        print("Mock hardware shutdown complete.")
        return

    if buzzer:
        try:
            buzzer.play_tone(200, 0.1) # Short low beep for shutdown
            buzzer.play_tone(150, 0.1)
            buzzer.cleanup() # Module specific cleanup
        except Exception as e:
            print(f"Error during buzzer shutdown: {e}")

    if lcd:
        try:
            lcd.clear()
            lcd.backlight(True)
            lcd.message("Server Offline", 1)
            time.sleep(1)
            lcd.backlight(False)
            lcd.display_off()
        except Exception as e:
            print(f"Error during LCD shutdown: {e}")

    if gpio_initialized:
        try:
            GPIO.cleanup() # Global GPIO cleanup
            print("GPIO cleanup complete.")
            gpio_initialized = False
        except Exception as e:
            print(f"Error during GPIO cleanup: {e}")
    else:
        print("GPIO was not initialized or already cleaned up.")
    print("Hardware shutdown sequence finished.")

def display_message(line1, line2="", clear_first=True):
    """Displays messages on the LCD. If LCD is not available, prints to console."""
    if not RPI_HW_AVAILABLE and not (lcd and hasattr(lcd, 'message')): # Check if mock lcd was created
        print(f"MockLCD Display: L1: '{line1}', L2: '{line2}'")
        return

    if lcd:
        try:
            if clear_first:
                lcd.clear()
            if line1 is not None: # Allow clearing and setting only one line
                lcd.message(str(line1)[:16], 1) # Max 16 chars
            if line2 is not None:
                lcd.message(str(line2)[:16], 2) # Max 16 chars
        except Exception as e:
            print(f"Error displaying message on LCD: {e}")
    else:
        print("LCD not available. Message not displayed on hardware.")
        print(f"Intended LCD L1: {line1}")
        print(f"Intended LCD L2: {line2}")


def play_sound(sound_type="beep"):
    """Plays a predefined sound on the buzzer. If not available, prints to console."""
    if not RPI_HW_AVAILABLE and not (buzzer and hasattr(buzzer, 'beep')): # Check if mock buzzer was created
        print(f"MockBuzzer: play_sound('{sound_type}')")
        return

    if buzzer:
        try:
            if sound_type == "beep":
                buzzer.beep()
            elif sound_type == "startup":
                buzzer.startup_sound()
            elif sound_type == "alert":
                buzzer.alert_sound()
            elif sound_type == "confirmation":
                buzzer.confirmation_beep()
            elif sound_type == "double_confirmation":
                buzzer.double_confirmation_beep()
            else:
                print(f"Unknown sound type: {sound_type}")
        except Exception as e:
            print(f"Error playing sound on buzzer: {e}")
    else:
        print(f"Buzzer not available. Sound '{sound_type}' not played on hardware.")

def get_ip_addresses_string():
    """
    Returns a string with current IP addresses, formatted for single-line display.
    e.g., "E:192.168.1.5 W:None"
    """
    if not RPI_HW_AVAILABLE:
        return "E:127.0.0.1 W:N/A" # Mock IP string

    ips = {}
    for iface in NETWORK_INTERFACES:
        ips[iface] = _get_ip_address(iface)

    eth_ip = ips.get('eth0')
    wlan_ip = ips.get('wlan0')

    display_str = ""
    if eth_ip:
        display_str += f"E:{eth_ip} "
    if wlan_ip:
        display_str += f"W:{wlan_ip}"

    if not display_str:
        return "No IP Found"

    return display_str.strip()[:16] # Ensure it fits 16 chars

# Example standalone usage for testing hardware_controller.py itself
if __name__ == '__main__':
    print("Testing hardware_controller.py...")

    # Attempt to get server IP for display (useful if running this on the device)
    # This is a simple way, might not always work depending on network config
    hostname = socket.gethostname()
    try:
        local_ip = socket.gethostbyname(hostname)
    except socket.gaierror:
        local_ip = "?.?.?.?" # Fallback if hostname doesn't resolve easily

    if init_hardware("Test App", local_ip, "5000"):
        print("Hardware initialized successfully for test.")
        display_message("Controller Test", "Running...", clear_first=False) # Append to init message
        time.sleep(2)

        current_ips_str = get_ip_addresses_string()
        display_message("IP Info:", current_ips_str)
        print(f"IPs displayed: {current_ips_str}")
        time.sleep(3)

        play_sound("confirmation")
        time.sleep(1)
        play_sound("alert")
        time.sleep(2)

        display_message("Test Complete!", "Shutting down...")
        print("Test complete. Shutting down hardware.")
    else:
        print("Hardware initialization failed for test.")

    shutdown_hardware()
    print("hardware_controller.py test finished.")
