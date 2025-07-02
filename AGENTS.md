# Agent Instructions for Raspberry Pi IP Display Project

This document provides guidelines for AI agents working on this codebase.

## Python Version

-   The scripts are intended to be compatible with **Python 3.7+**.
-   Please ensure any new code or modifications maintain compatibility with this version range.

## GPIO Pin Numbering

-   The project uses **BCM** pin numbering for `RPi.GPIO`. This is explicitly set in `ip_display_app.py`.
-   When adding new GPIO-related functionality or modifying existing code, ensure BCM numbering is consistently used.

## Libraries

-   **`RPi.GPIO`**: Used for GPIO control, including PWM for the buzzer.
-   **`smbus2`**: Preferred for I2C communication with the LCD. `smbus` is a fallback if `smbus2` is unavailable, but new development should target `smbus2`.
-   Standard Python libraries (`socket`, `time`, `fcntl`, `struct`) are also used.

## Code Style and Structure

-   Follow standard Python PEP 8 guidelines for code style.
-   The project is structured with:
    -   `ip_display_app.py`: Main application logic.
    -   `lcd_i2c.py`: Class for controlling the I2C LCD.
    -   `buzzer_pwm.py`: Class for controlling the passive buzzer.
-   New, distinct functionalities should ideally be encapsulated in their own modules or classes if appropriate.
-   Include docstrings for modules, classes, and functions to explain their purpose, arguments, and return values.
-   Add comments to clarify complex or non-obvious code sections.

## Error Handling

-   Implement robust error handling, especially for hardware interactions (I2C, GPIO) and network operations.
-   Use `try...except` blocks to catch potential exceptions and provide informative error messages or graceful failure.
-   Ensure GPIO resources are cleaned up properly using `GPIO.cleanup()` in a `finally` block in the main application script.

## Testing (Simulated)

-   Since direct hardware testing is not possible for the agent, write code that is logically sound and includes clear comments about assumptions made regarding hardware behavior.
-   The `if __name__ == '__main__':` block in utility modules (`lcd_i2c.py`, `buzzer_pwm.py`) can be used for basic, standalone testing of that module's functionality.

## README.md

-   Keep the `README.md` file updated with any changes to hardware setup, pin connections, software dependencies, or running instructions.
-   Ensure instructions are clear and easy for a user to follow.
