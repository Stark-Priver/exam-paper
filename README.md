# Raspberry Pi Face Recognition Based Attendance System with LCD/Buzzer Feedback

This project is a Flask-based web application for managing student attendance using facial recognition. It integrates with Raspberry Pi hardware (I2C LCD and Passive Buzzer) to provide real-time feedback during the attendance process and can display system status like IP address.

## Features

**Core Application (Flask Web Interface):**
-   Admin login and dashboard.
-   Venue Management: Add, edit, delete examination venues.
-   Student Management: Add, edit, delete students with photo uploads for facial recognition (face presence validated using `deepface`).
-   Exam Management: Create, edit, delete exams (subject, date, time), linking them to specific venues.
-   Exam Registration: Register students for specific exams.
-   Live Authentication: Real-time facial recognition (using `deepface` with dlib-free models) during exams using a webcam.
    -   Visual feedback on the web interface (bounding boxes, student names, eligibility status).
-   Logging: Records authentication attempts (Verified_Eligible, Verified_Not_Eligible, Unknown_Student) with timestamps.
-   Log Viewing: Paginated and sortable view of authentication logs.

**Raspberry Pi Hardware Integration (LCD & Buzzer):**
-   **On Flask App Start:**
    -   LCD displays "Flask App Ready" (or similar) and the Raspberry Pi's IP address and port.
    -   Buzzer plays a startup sound.
-   **During Live Authentication:**
    -   LCD displays student's eligibility status (e.g., "Eligible: [Name]", "Not Eligible", "Unknown Face") and Student ID.
    -   Buzzer provides audible cues (e.g., confirmation beep for eligible, alert beep for not eligible/unknown).
-   **On Flask App Shutdown:**
    -   LCD displays "Server Offline" (or similar).
    -   Buzzer plays a shutdown sound.
    -   GPIO resources are cleaned up.
-   **Standalone IP Display Utility (`ip_display_app.py`):**
    -   A separate script that uses the same hardware controller to display current IP addresses, similar to the original project functionality. This can be run independently of the Flask application.
-   **Mock Hardware Mode:**
    -   If RPi-specific libraries are not found (e.g., when developing on a non-RPi machine), the hardware controller switches to a mock mode, printing actions to the console instead of interacting with physical hardware. This allows the Flask application to run and be tested without a Raspberry Pi.

## Hardware Requirements

-   Raspberry Pi (tested with Raspberry Pi 3 Model A+, should work on others with GPIO)
-   16x2 I2C LCD Display (HD44780 compatible with PCF8574/PCF8574A I2C backpack)
-   Passive Piezo Buzzer
-   Jumper Wires
-   Optional: Breadboard

## Pin Connections

### I2C LCD Display

-   **LCD VCC** to Raspberry Pi **5V** (e.g., Pin 2 or 4)
-   **LCD GND** to Raspberry Pi **GND** (e.g., Pin 6)
-   **LCD SDA** to Raspberry Pi **SDA (GPIO 2)** (Pin 3)
-   **LCD SCL** to Raspberry Pi **SCL (GPIO 3)** (Pin 5)

*Note: The I2C address for the LCD is commonly `0x27` (for PCF8574A) or `0x3F` (for PCF8574). The script defaults to `0x27`. You can verify this using the command below.*

### Passive Buzzer

-   **Buzzer Positive (+)** to Raspberry Pi **GPIO 18 (BCM)** (Pin 12)
-   **Buzzer Negative (-)** to Raspberry Pi **GND** (e.g., Pin 14, 20, etc.)

*Note: GPIO 18 is chosen as it supports hardware PWM, which is good for generating tones.*

## Software Setup

### 1. Enable I2C Interface

If you haven't already, enable the I2C interface on your Raspberry Pi:

1.  Open a terminal and run:
    ```bash
    sudo raspi-config
    ```
2.  Navigate to `Interface Options` (or `Interfacing Options` on older versions).
3.  Select `I2C`.
4.  Choose `<Yes>` to enable the I2C interface.
5.  Select `<Finish>` and reboot your Raspberry Pi if prompted.

### 2. Install Dependencies

Open a terminal on your Raspberry Pi and run the following commands:

```bash
# Update package list
sudo apt-get update

# Install system-level dependencies for I2C, Python smbus, build tools, and OpenCV dependencies
# DeepFace may require additional libraries for some of its models/backends if not using the defaults.
# TensorFlow (used by some DeepFace models) might need specific system libraries like libatlas-base-dev, etc.
# Ensure your Raspberry Pi OS is up to date.
sudo apt-get install -y python3-smbus i2c-tools build-essential cmake libjpeg-dev libpng-dev libtiff-dev libavcodec-dev libavformat-dev libswscale-dev libv4l-dev libxvidcore-dev libx264-dev libgtk-3-dev libatlas-base-dev gfortran python3-dev

# Install necessary Python libraries using pip
# It's recommended to use a virtual environment
# python3 -m venv venv
# source venv/bin/activate
pip3 install --upgrade pip
pip3 install -r requirements.txt
```
The `requirements.txt` file should include:
- Flask
- Flask-Login
- Flask-SQLAlchemy
- Flask-Migrate
- Flask-WTF
- python-dotenv
- RPi.GPIO (for Raspberry Pi)
- smbus2 (for Raspberry Pi I2C)
- opencv-python
- deepface
- numpy
- Werkzeug
- SQLAlchemy
- click # Often a Flask dependency, good to list if directly used or for commands
- gunicorn (optional, for production deployment)

*Note: The system now uses `deepface` for facial recognition, configured with dlib-free models (e.g., VGG-Face with OpenCV detector by default in the current code). `deepface` will download required model weights on its first use for a specific model, so an internet connection will be needed at that point.*
*`smbus2` is preferred for I2C. If it causes issues, `python3-smbus` (system package) provides the `smbus` module.*
*TensorFlow is a dependency of `deepface` for many models. Installation on Raspberry Pi can sometimes be tricky; ensure you have enough space and memory. If `pip install deepface` has issues with TensorFlow, you might need to install a specific TensorFlow Lite version or a version compatible with your Raspberry Pi's architecture separately.*

### 3. Check LCD I2C Address (Optional but Recommended)

To confirm the I2C address of your LCD module, run:
```bash
sudo i2cdetect -y 1
```
(For very old Raspberry Pi Model B Rev 1, use `sudo i2cdetect -y 0`)

You should see a table of I2C addresses. Your LCD will likely appear as `27` or `3f`. If it's different from the default `0x27` in `lcd_i2c.py` and `ip_display_app.py`, you'll need to update the `DEFAULT_I2C_ADDR` or `LCD_I2C_ADDRESS` constant in the scripts.

## Running the Application

### Initial Setup

1.  **Clone the repository:**
    ```bash
    git clone <repository_url>
    cd <repository_directory>
    ```

2.  **Create a `.flaskenv` file** (optional, for development environment variables):
    ```
    FLASK_APP=run.py
    FLASK_ENV=development # Use 'production' for production
    # DATABASE_URL=sqlite:///site.db # Example, can be configured in config.py
    # SECRET_KEY=your_very_secret_key # Should be set for sessions
    ```
    *Ensure `SECRET_KEY` is set to a strong random value, especially for production.*

3.  **Initialize the Database (Flask-Migrate):**
    ```bash
    # If using a virtual environment, activate it first: source venv/bin/activate
    flask db init  # Run only once to initialize migrations folder (if it doesn't exist)
    flask db migrate -m "Create initial database schema or descriptive message for current changes." # e.g., "Add Venue model"
    flask db upgrade # Apply migrations to the database
    ```
    *Note: If you have run `flask db init` before, you only need `migrate` and `upgrade` for new changes.*

4.  **Create an Admin User:**
    ```bash
    flask create-admin <admin_username> <admin_password>
    ```
    Replace `<admin_username>` and `<admin_password>` with your desired credentials.

### Running the Flask Web Application

Navigate to the project's root directory in the terminal.

```bash
# If using a virtual environment, activate it: source venv/bin/activate
python3 run.py
```
The application will typically start on `http://0.0.0.0:5000/`.
-   The LCD (if connected and on a Raspberry Pi) will display a startup message and the server's IP address.
-   The buzzer will play a startup sound.
-   Access the web interface through a browser on a device connected to the same network, using the Raspberry Pi's IP address (e.g., `http://<RaspberryPi_IP>:5000/`).

To stop the Flask application, press `Ctrl+C` in the terminal where it's running.
-   The LCD will display a shutdown message.
-   The buzzer will play a shutdown sound.
-   GPIO resources will be cleaned up.

### Running the Standalone IP Display Utility

If you only want to display the IP address on the LCD without running the full web application:
```bash
python3 ip_display_app.py
```
This script uses the same hardware controller for LCD and buzzer operations. Press `Ctrl+C` to stop it.

## Troubleshooting

-   **No display on LCD / `IOError: [Errno 121] Remote I/O error`**:
    -   Check all wiring connections, especially SDA, SCL, VCC, and GND for the LCD.
    -   Verify the I2C address using `i2cdetect` and ensure it matches the one in the script.
    -   Ensure I2C is enabled via `raspi-config`.
-   **Buzzer not working**:
    -   Check wiring for the buzzer, ensuring correct polarity if it's a piezo buzzer (though passive ones are often non-polarized, some modules might have markings).
    -   Ensure the correct GPIO pin (BCM 18 / Pin 12) is used.
-   **`ImportError: No module named smbus2` (or `smbus`)**:
    -   Ensure you have installed the library using `pip3 install smbus2`.
-   **`RuntimeError: Please set pin numbering mode using GPIO.setmode(GPIO.BOARD) or GPIO.setmode(GPIO.BCM)` (when running `buzzer_pwm.py` standalone for testing)**:
    -   The `app.hardware_controller.py` (used by `run.py` and `ip_display_app.py`) handles `GPIO.setmode(GPIO.BCM)`.
    -   If testing `buzzer_pwm.py` directly, its `if __name__ == '__main__':` block now includes `GPIO.setmode(GPIO.BCM)` and `GPIO.cleanup()` for that specific test scenario.
-   **IP Address shows "None", "No IP Found", or "?.?.?.?" on LCD**:
    -   Ensure your Raspberry Pi is connected to the network (Ethernet or Wi-Fi).
    -   Check if the network interfaces (`eth0`, `wlan0`) are active and configured. Use `ifconfig` or `ip a` to check their status.
    -   The IP detection method in `app.hardware_controller.py` and `run.py` tries its best but might not cover all network configurations.
-   **Flask Application Errors (e.g., database issues, template not found)**:
    -   Check the terminal output where `python3 run.py` is executing for detailed Flask error messages.
    -   Ensure all dependencies in `requirements.txt` are installed correctly in your environment.
    -   Verify database setup and migrations (`flask db upgrade`).
-   **Facial Recognition Issues (using DeepFace)**:
    -   Ensure `deepface` and `opencv-python` are installed correctly.
    -   **First Run Model Downloads**: `deepface` downloads model weights (e.g., for VGG-Face, Facenet) the first time a specific model is used. Ensure your Raspberry Pi has an internet connection for this initial setup. These are typically stored in `~/.deepface/weights`.
    -   **Provide Clear Photos**: Use clear, well-lit, frontal photos for student registration. The `process_student_image` utility now attempts to validate if a face is detectable using `deepface`.
    -   **Webcam**: Check webcam connectivity (`ls /dev/video*`) and permissions. The `initialize_camera` function in `app/routes.py` tries common camera indices.
    -   **Performance on Raspberry Pi**:
        -   Real-time recognition with `deepface` can be resource-intensive on a Raspberry Pi.
        -   Consider adjusting camera resolution (e.g., to 320x240) and FPS in `app/routes.py` inside `initialize_camera()`.
        -   The choice of `detector_backend` and `model_name` in `app/face_rec_utils.py` (e.g., `DEEPFACE_DETECTOR_BACKEND`, `DEEPFACE_MODEL_NAME`) significantly impacts performance and accuracy. Experiment with alternatives if needed (e.g., `ssd` detector, `SFace` model).
        -   Frame skipping is currently disabled in `generate_frames` (`frame_skip = 0`) but can be enabled to reduce processing load.
    -   **TensorFlow Issues**: If `deepface` installation or runtime fails due to TensorFlow, you might need to find a specific TensorFlow wheel (`.whl`) compatible with your Raspberry Pi's OS and Python version, install it manually, and then reinstall `deepface`. Check the `deepface` library's documentation or GitHub issues for Raspberry Pi-specific advice.

Enjoy your integrated attendance system!
