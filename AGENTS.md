# Agent Instructions for Raspberry Pi IP Display Project

This document provides guidelines for AI agents working on this codebase.

## Python Version

-   The scripts are intended to be compatible with **Python 3.7+**.
-   Please ensure any new code or modifications maintain compatibility with this version range.

## GPIO Pin Numbering

-   The project uses **BCM** pin numbering for `RPi.GPIO`.
-   GPIO mode initialization (`GPIO.setmode(GPIO.BCM)`) and global cleanup (`GPIO.cleanup()`) are now handled by `app/hardware_controller.py` when initialized by a main application script (e.g., `run.py` for the Flask app, or `ip_display_app.py` for the standalone utility).
-   Individual hardware modules (`buzzer_pwm.py`, `lcd_i2c.py`) should not set the GPIO mode or perform global cleanup.
-   When adding new GPIO-related functionality or modifying existing code, ensure BCM numbering is consistently used.

## Libraries

-   **`RPi.GPIO`**: Used for GPIO control, including PWM for the buzzer.
-   **`smbus2`**: Preferred for I2C communication with the LCD. `smbus` is a fallback if `smbus2` is unavailable, but new development should target `smbus2`.
-   Standard Python libraries (`socket`, `time`, `fcntl`, `struct`) are also used.

## Code Style and Structure

-   Follow standard Python PEP 8 guidelines for code style.
-   The project is structured with:
    -   `run.py`: Main Flask application runner. Initializes and manages hardware via `HardwareController`.
    -   `app/hardware_controller.py`: Centralized control for LCD and Buzzer. Handles GPIO setup and cleanup. Provides an interface for the Flask app and other utilities to use hardware. Includes mock mode for development off-RPi.
    -   `app/lcd_i2c.py`: Class for controlling the I2C LCD. (Relies on `smbus2`)
    -   `app/buzzer_pwm.py`: Class for controlling the passive buzzer. (Relies on `RPi.GPIO`)
    -   `ip_display_app.py`: Standalone utility to display IP addresses, now uses `app.hardware_controller.py`.
    -   Flask-specific files (routes, models, forms, templates) are within the `app/` directory.
-   New, distinct hardware-related functionalities should ideally be added to `app/hardware_controller.py` or as methods to the individual device classes if appropriate.
-   Include docstrings for modules, classes, and functions to explain their purpose, arguments, and return values.
-   Add comments to clarify complex or non-obvious code sections.

## Error Handling

-   Implement robust error handling, especially for hardware interactions (I2C, GPIO) and network operations. `app/hardware_controller.py` includes a mock mode to allow development and testing of the Flask application logic even when Raspberry Pi hardware is not present.
-   Use `try...except` blocks to catch potential exceptions and provide informative error messages or graceful failure.
-   GPIO resource cleanup (`GPIO.cleanup()`) is handled by `app.hardware_controller.shutdown_hardware()`, which should be called on application exit (e.g., using `atexit` in `run.py`).

## Testing (Simulated)

-   Since direct hardware testing is not possible for the agent, write code that is logically sound and includes clear comments about assumptions made regarding hardware behavior.
-   The `if __name__ == '__main__':` block in utility modules (`lcd_i2c.py`, `buzzer_pwm.py`) can be used for basic, standalone testing of that module's functionality.

## README.md

-   Keep the `README.md` file updated with any changes to hardware setup, pin connections, software dependencies, or running instructions.
-   Ensure instructions are clear and easy for a user to follow.
