import time
import socket
import fcntl
import struct
import RPi.GPIO as GPIO

from lcd_i2c import LCD_I2C, DEFAULT_I2C_ADDR
from buzzer_pwm import PassiveBuzzer, DEFAULT_BUZZER_PIN

# Configuration
LCD_I2C_ADDRESS = DEFAULT_I2C_ADDR  # Use the default from lcd_i2c.py or override
BUZZER_GPIO_PIN = DEFAULT_BUZZER_PIN  # Use the default from buzzer_pwm.py or override
IP_REFRESH_INTERVAL = 30  # Seconds
NETWORK_INTERFACES = ['eth0', 'wlan0']  # Interfaces to check for IP

def get_ip_address(ifname):
    """
    Gets the IP address of a given network interface.
    Returns the IP address string or None if not found or interface is down.
    """
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

def get_all_ips(interfaces_to_check):
    """
    Gets IP addresses for a list of interfaces.
    Returns a dictionary {interface_name: ip_address}.
    IP address will be None if not found for an interface.
    """
    ips = {}
    for iface in interfaces_to_check:
        ips[iface] = get_ip_address(iface)
    return ips

def display_ips_on_lcd(lcd, ips_dict):
    """
    Displays IP addresses on the LCD.
    Prioritizes wlan0 then eth0 if both exist for display, or shows multiple if space allows.
    """
    lcd.clear()
    line1_msg = None
    line2_msg = None

    wlan_ip = ips_dict.get('wlan0')
    eth_ip = ips_dict.get('eth0')

    if wlan_ip:
        line1_msg = f"WLAN: {wlan_ip}"
    if eth_ip:
        if line1_msg: # WLAN IP is already on line 1
            line2_msg = f"ETH: {eth_ip}"
        else: # No WLAN IP, put ETH on line 1
            line1_msg = f"ETH: {eth_ip}"

    if not line1_msg and not line2_msg:
        # No IPs found for specified interfaces
        active_ips = [f"{ifname}: {ip}" for ifname, ip in ips_dict.items() if ip]
        if active_ips:
            # Display first available IP if wlan0/eth0 not found but others are
            first_available = active_ips[0]
            if len(first_available) > 16: # Truncate if too long
                 first_available = first_available[:16]
            line1_msg = first_available
            if len(active_ips) > 1 and len(active_ips[1]) <= 16:
                 line2_msg = active_ips[1][:16]
        else:
            line1_msg = "No IP Found"
            line2_msg = "Check Network"

    if line1_msg:
        lcd.message(line1_msg, 1)
    if line2_msg:
        lcd.message(line2_msg, 2)
    elif not line1_msg: # Should not happen if logic above is correct
        lcd.message("Error display", 1)


def main():
    lcd = None
    buzzer = None

    try:
        # Initialize GPIO (using BCM mode is important)
        GPIO.setmode(GPIO.BCM) # Set mode globally for all modules

        # Initialize LCD
        print(f"Initializing LCD at I2C address 0x{LCD_I2C_ADDRESS:02X}...")
        lcd = LCD_I2C(i2c_addr=LCD_I2C_ADDRESS)
        lcd.message("System Booting..", 1)
        lcd.message("Please wait...", 2)
        print("LCD Initialized.")

        # Initialize Buzzer
        print(f"Initializing Buzzer on GPIO {BUZZER_GPIO_PIN}...")
        buzzer = PassiveBuzzer(buzzer_pin=BUZZER_GPIO_PIN)
        print("Buzzer Initialized.")

        # Play startup sound
        print("Playing startup sound...")
        buzzer.startup_sound()

        lcd.clear()
        lcd.message("IP Display Ready", 1)
        time.sleep(1.5)

        last_ips_displayed = {}

        while True:
            current_ips = get_all_ips(NETWORK_INTERFACES)

            # Only update LCD if IPs have changed
            if current_ips != last_ips_displayed:
                print(f"IPs: {current_ips}")
                display_ips_on_lcd(lcd, current_ips)
                last_ips_displayed = current_ips.copy()

                # Optional: Beep if IP changes (can be annoying)
                # if any(current_ips.values()): # Beep if at least one IP is found
                #    buzzer.beep(repeat=1, tone_duration=0.05, frequency=1200)

            # Wait for the refresh interval
            # Implement a way to break this loop cleanly for shutdown if needed
            # For now, Ctrl+C is the way.
            for _ in range(IP_REFRESH_INTERVAL):
                time.sleep(1) # Sleep in 1s intervals to make Ctrl+C more responsive

    except KeyboardInterrupt:
        print("\nShutting down...")
        if buzzer:
            buzzer.play_tone(200, 0.1) # Short low beep for shutdown
            buzzer.play_tone(150, 0.1)
        if lcd:
            lcd.clear()
            lcd.backlight(True) # Ensure backlight is on for message
            lcd.message("System Off", 1)
            time.sleep(1) # Give time to read
            lcd.backlight(False) # Turn off backlight
            lcd.display_off()
    except Exception as e:
        print(f"An error occurred: {e}")
        if lcd:
            lcd.clear()
            try:
                lcd.message("Error Occurred", 1)
                # Try to display a snippet of the error if it fits
                error_str = str(e)[:16]
                lcd.message(error_str, 2)
            except Exception asex:
                print(f"Further error during LCD error display: {asex}")
        if buzzer:
            try:
                buzzer.alert_sound() # Play alert sound on error
            except Exception as bex:
                print(f"Error playing buzzer alert: {bex}")
    finally:
        print("Cleaning up GPIO...")
        if buzzer: # Buzzer cleanup does not call GPIO.cleanup() itself
            buzzer.cleanup()
        # LCD class does not directly use RPi.GPIO, so no specific cleanup for it here
        # other than turning it off.
        GPIO.cleanup() # Clean up all GPIO channels used
        print("GPIO cleanup complete. Exiting.")

if __name__ == "__main__":
    main()
# End of ip_display_app.py
