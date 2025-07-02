import smbus2 as smbus # Or import smbus if smbus2 is not available
import time

# I2C Address of the LCD (PCF8574A backpack default is 0x27, PCF8574 is 0x3F)
# User should verify with `i2cdetect -y 1`
DEFAULT_I2C_ADDR = 0x27

# LCD Commands
LCD_CLEARDISPLAY = 0x01
LCD_RETURNHOME = 0x02
LCD_ENTRYMODESET = 0x04
LCD_DISPLAYCONTROL = 0x08
LCD_CURSORSHIFT = 0x10
LCD_FUNCTIONSET = 0x20
LCD_SETCGRAMADDR = 0x40
LCD_SETDDRAMADDR = 0x80

# Flags for display entry mode
LCD_ENTRYRIGHT = 0x00
LCD_ENTRYLEFT = 0x02
LCD_ENTRYSHIFTINCREMENT = 0x01
LCD_ENTRYSHIFTDECREMENT = 0x00

# Flags for display on/off control
LCD_DISPLAYON = 0x04
LCD_DISPLAYOFF = 0x00
LCD_CURSORON = 0x02
LCD_CURSOROFF = 0x00
LCD_BLINKON = 0x01
LCD_BLINKOFF = 0x00

# Flags for display/cursor shift
LCD_DISPLAYMOVE = 0x08
LCD_CURSORMOVE = 0x00
LCD_MOVERIGHT = 0x04
LCD_MOVELEFT = 0x00

# Flags for function set
LCD_8BITMODE = 0x10
LCD_4BITMODE = 0x00
LCD_2LINE = 0x08
LCD_1LINE = 0x00
LCD_5x10DOTS = 0x04
LCD_5x8DOTS = 0x00

# Flags for backlight control (PCF8574 specific)
LCD_BACKLIGHT = 0x08  # P3
LCD_NOBACKLIGHT = 0x00

# Bit positions for I2C backpack (PCF8574)
# P0: RS (Register Select)
# P1: RW (Read/Write) - Not used for write-only operations to LCD
# P2: EN (Enable)
# P3: Backlight LED
# P4: D4
# P5: D5
# P6: D6
# P7: D7

En = 0b00000100  # Enable bit
Rw = 0b00000010  # Read/Write bit (not used)
Rs = 0b00000001  # Register select bit

class LCD_I2C:
    def __init__(self, i2c_addr=DEFAULT_I2C_ADDR, bus_number=1, backlight_on=True):
        self.i2c_addr = i2c_addr
        self.bus = smbus.SMBus(bus_number)
        self._backlight_val = LCD_BACKLIGHT if backlight_on else LCD_NOBACKLIGHT

        # Initialise display
        self._write(0x33, 0) # Initialization sequence for 4-bit mode
        self._write(0x32, 0) # Initialization sequence for 4-bit mode
        self._write(0x06, 0) # Entry mode set: increment cursor, no shift
        self._write(LCD_FUNCTIONSET | LCD_2LINE | LCD_5x8DOTS | LCD_4BITMODE, 0) # Function set: 2 line, 5x8 dots, 4-bit mode
        self._write(LCD_DISPLAYCONTROL | LCD_DISPLAYON | LCD_CURSOROFF | LCD_BLINKOFF, 0) # Display control: display on, cursor off, blink off
        self._write(LCD_CLEARDISPLAY, 0) # Clear display
        time.sleep(0.002) # Clearing display takes a bit longer

    def _i2c_write_byte(self, byte_data):
        """Writes a single byte to the I2C bus."""
        self.bus.write_byte(self.i2c_addr, byte_data)
        time.sleep(0.0001) # Small delay for command processing

    def _strobe(self, data):
        """Clocks EN to latch command."""
        self._i2c_write_byte(data | En | self._backlight_val)
        time.sleep(0.0005)
        self._i2c_write_byte(((data & ~En) | self._backlight_val))
        time.sleep(0.0001)

    def _write_four_bits(self, data):
        """Writes four bits to LCD."""
        self._i2c_write_byte(data | self._backlight_val)
        self._strobe(data)

    def _write(self, cmd, mode=Rs): # mode = Rs for data, 0 for command
        """Writes a command or data to the LCD. cmd is the command/data, mode is Rs bit."""
        # Send high nibble
        self._write_four_bits(mode | (cmd & 0xF0))
        # Send low nibble
        self._write_four_bits(mode | ((cmd << 4) & 0xF0))

    def message(self, text, line=1, col=0):
        """
        Send string to display.
        text: string to display
        line: line number (1 or 2)
        col: column number (0-15)
        """
        if line == 1:
            addr = 0x80
        elif line == 2:
            addr = 0xC0
        else:
            # Default to line 1 if invalid line number
            addr = 0x80
            print(f"Warning: Invalid line number {line}. Defaulting to line 1.")

        addr += col
        self._write(addr, 0) # Set DDRAM address

        for char in text:
            self._write(ord(char), Rs)

    def clear(self):
        """Clears the display."""
        self._write(LCD_CLEARDISPLAY, 0)
        time.sleep(0.002) # Clearing display command takes longer

    def set_cursor(self, line, col):
        """
        Set cursor position.
        line: line number (1 or 2)
        col: column number (0-15)
        """
        if line == 1:
            addr = 0x80
        elif line == 2:
            addr = 0xC0
        else:
            # Default to line 1 if invalid line number
            addr = 0x80
            print(f"Warning: Invalid line number {line} for cursor. Defaulting to line 1.")

        addr += col
        self._write(addr, 0)

    def backlight(self, on):
        """Turn backlight on or off."""
        if on:
            self._backlight_val = LCD_BACKLIGHT
        else:
            self._backlight_val = LCD_NOBACKLIGHT
        self._i2c_write_byte(self._backlight_val) # Activate backlight setting immediately

    def display_on(self):
        self._write(LCD_DISPLAYCONTROL | LCD_DISPLAYON | LCD_CURSOROFF | LCD_BLINKOFF, 0)

    def display_off(self):
        self._write(LCD_DISPLAYCONTROL | LCD_DISPLAYOFF, 0)

    def cursor_on(self):
        self._write(LCD_DISPLAYCONTROL | LCD_DISPLAYON | LCD_CURSORON, 0)

    def cursor_off(self):
        self._write(LCD_DISPLAYCONTROL | LCD_DISPLAYON | LCD_CURSOROFF, 0)

    def blink_on(self):
        self._write(LCD_DISPLAYCONTROL | LCD_DISPLAYON | LCD_CURSORON | LCD_BLINKON, 0)

    def blink_off(self):
        self._write(LCD_DISPLAYCONTROL | LCD_DISPLAYON | LCD_CURSORON | LCD_BLINKOFF, 0)

# Example usage (for testing - this would typically be in the main script)
if __name__ == '__main__':
    try:
        print("Initializing LCD...")
        lcd = LCD_I2C(i2c_addr=DEFAULT_I2C_ADDR, bus_number=1)
        print("LCD Initialized.")

        lcd.message("Hello, World!", 1)
        lcd.message("RPI LCD Test", 2)
        time.sleep(3)

        lcd.backlight(False)
        time.sleep(2)
        lcd.backlight(True)
        time.sleep(2)

        print("Clearing display...")
        lcd.clear()
        lcd.message("IP Address:", 1)
        lcd.message("192.168.1.100", 2) # Example IP
        time.sleep(3)

        lcd.clear()
        lcd.message("Testing Cursor", 1)
        lcd.cursor_on()
        time.sleep(2)
        lcd.blink_on()
        time.sleep(2)
        lcd.set_cursor(2, 5)
        lcd.message("Here", 2, 5)
        time.sleep(3)

        lcd.clear()
        lcd.backlight(True) # Ensure backlight is on before finishing
        lcd.message("Test Complete!", 1)

    except Exception as e:
        print(f"Error: {e}")
        print("Please ensure the LCD is connected correctly and I2C is enabled.")
        print(f"Attempted I2C address: 0x{DEFAULT_I2C_ADDR:02X}")
        print("Use 'sudo i2cdetect -y 1' (or 0 for older Pis) to check the address.")
    finally:
        # In a real application, cleanup GPIO if this module also handled it.
        # Here, the main script would handle RPi.GPIO cleanup.
        print("LCD test finished.")
        if 'lcd' in locals():
            lcd.clear() # Clear display before exit
            # lcd.backlight(False) # Optionally turn off backlight
            pass

# End of lcd_i2c.py
