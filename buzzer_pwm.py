import RPi.GPIO as GPIO
import time

# GPIO pin for the buzzer (using BCM numbering)
# GPIO 18 is chosen as it supports hardware PWM
DEFAULT_BUZZER_PIN = 18

class PassiveBuzzer:
    def __init__(self, buzzer_pin=DEFAULT_BUZZER_PIN):
        self.buzzer_pin = buzzer_pin
        self.pwm = None

        # Set up GPIO mode
        # Using BCM mode for GPIO pin numbering
        # Check current mode to avoid conflicts if already set by another module
        current_gpio_mode = GPIO.getmode()
        if current_gpio_mode is None:
            GPIO.setmode(GPIO.BCM)
            # print("GPIO mode set to BCM by Buzzer module.")
        elif current_gpio_mode != GPIO.BCM:
            # This case should ideally be handled by a central GPIO manager
            # or ensure all modules agree on a mode.
            # For now, we'll print a warning if a different mode is already set.
            print(f"Warning: GPIO mode was already set to {current_gpio_mode}. Buzzer expected BCM.")
            print("This might lead to incorrect pin assignments if not managed.")
            # Attempting to switch mode here could break other parts of an application.
            # The main script should manage GPIO mode setup.
            # However, for standalone buzzer use, we might force it.
            # For now, we assume the main script handles global GPIO.setmode(GPIO.BCM)

        GPIO.setup(self.buzzer_pin, GPIO.OUT)
        GPIO.output(self.buzzer_pin, GPIO.LOW) # Ensure buzzer is off initially

    def _start_pwm(self, frequency, duty_cycle=50):
        """Starts PWM on the buzzer pin."""
        if frequency <= 0:
            # print("Frequency must be positive.")
            return
        if self.pwm:
            self.pwm.stop() # Stop existing PWM if any

        self.pwm = GPIO.PWM(self.buzzer_pin, frequency)
        self.pwm.start(duty_cycle) # Start PWM with 50% duty cycle

    def _stop_pwm(self):
        """Stops PWM on the buzzer pin."""
        if self.pwm:
            self.pwm.stop()
        GPIO.output(self.buzzer_pin, GPIO.LOW) # Ensure pin is low after stopping

    def play_tone(self, frequency, duration):
        """
        Plays a tone at a given frequency for a given duration.
        frequency: Frequency in Hz.
        duration: Duration in seconds.
        """
        if frequency <= 0:
            # print("Frequency must be positive for play_tone.")
            return
        self._start_pwm(frequency)
        time.sleep(duration)
        self._stop_pwm()

    def beep(self, repeat=1, tone_duration=0.1, pause_duration=0.1, frequency=1000):
        """
        Plays a series of beeps.
        repeat: Number of beeps.
        tone_duration: Duration of each beep in seconds.
        pause_duration: Duration of pause between beeps in seconds.
        frequency: Frequency of the beep in Hz.
        """
        for _ in range(repeat):
            self.play_tone(frequency, tone_duration)
            if repeat > 1:
                 time.sleep(pause_duration)

    def startup_sound(self):
        """Plays a more complex startup sound."""
        notes = [
            (262, 0.15), # C4
            (330, 0.15), # E4
            (392, 0.15), # G4
            (523, 0.30)  # C5
        ]
        for freq, dur in notes:
            self.play_tone(freq, dur)
            time.sleep(0.05) # Short pause between notes

    def alert_sound(self):
        """Plays an alert sound."""
        self.beep(repeat=3, tone_duration=0.05, pause_duration=0.05, frequency=2000)

    def confirmation_beep(self, frequency=1500, duration=0.1):
        """Plays a short confirmation beep."""
        self.play_tone(frequency, duration)

    def double_confirmation_beep(self, frequency=1500, tone_duration=0.07, pause_duration=0.07):
        """Plays two short confirmation beeps."""
        self.beep(repeat=2, tone_duration=tone_duration, pause_duration=pause_duration, frequency=frequency)

    def cleanup(self):
        """Cleans up GPIO resources used by the buzzer."""
        self._stop_pwm()
        # GPIO.cleanup(self.buzzer_pin) # Cleanup specific channel
        # Note: Main script should handle global GPIO.cleanup() if this is part of a larger app
        # to avoid cleaning up pins used by other components.
        # For now, this cleanup is specific to the buzzer pin if used standalone.
        # print(f"Buzzer GPIO {self.buzzer_pin} cleaned up.")
        pass # Let main script handle global cleanup.


# Example usage (for testing - this would typically be in the main script)
if __name__ == '__main__':
    buzzer = None # Initialize to None for finally block
    try:
        print("Initializing Buzzer...")
        # GPIO.setmode(GPIO.BCM) # Ensure BCM mode is set for standalone test
        buzzer = PassiveBuzzer(DEFAULT_BUZZER_PIN)
        print(f"Buzzer Initialized on GPIO {DEFAULT_BUZZER_PIN}.")

        print("Playing a single tone (A4 - 440Hz for 0.5s)...")
        buzzer.play_tone(440, 0.5)
        time.sleep(0.5)

        print("Playing beeps...")
        buzzer.beep(repeat=3, tone_duration=0.1, pause_duration=0.1, frequency=1000)
        time.sleep(0.5)

        print("Playing startup sound...")
        buzzer.startup_sound()
        time.sleep(0.5)

        print("Playing alert sound...")
        buzzer.alert_sound()
        time.sleep(0.5)

        print("Buzzer test complete.")

    except Exception as e:
        print(f"Error: {e}")
        print("Please ensure the buzzer is connected correctly to GPIO pin.")
    except KeyboardInterrupt:
        print("\nTest interrupted by user.")
    finally:
        if buzzer:
            print("Cleaning up buzzer GPIO...")
            buzzer.cleanup()
        # GPIO.cleanup() # Clean up all GPIO channels if this script was the sole GPIO user
        print("Buzzer test finished.")

# End of buzzer_pwm.py
