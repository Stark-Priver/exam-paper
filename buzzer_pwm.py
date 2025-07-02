import RPi.GPIO as GPIO
import time

# GPIO pin for the buzzer (using BCM numbering)
# GPIO 18 is chosen as it supports hardware PWM
DEFAULT_BUZZER_PIN = 18

class PassiveBuzzer:
    def __init__(self, buzzer_pin=DEFAULT_BUZZER_PIN):
        self.buzzer_pin = buzzer_pin
        self.pwm = None

        # GPIO.setmode will be handled by the main application script.
        # This module assumes GPIO mode has been set to BCM.
        # It also assumes GPIO.setup for the pin will be done by this module,
        # but global cleanup will be handled by the main application.

        try:
            GPIO.setup(self.buzzer_pin, GPIO.OUT)
        except RuntimeError as e:
            # This can happen if GPIO.setmode() hasn't been called yet.
            # Or if the pin is already in use with a conflicting setup.
            print(f"Error setting up buzzer pin {self.buzzer_pin}: {e}")
            print("Ensure GPIO.setmode(GPIO.BCM) is called in your main application before initializing the buzzer.")
            raise # Re-raise the exception to signal failure to the caller

        GPIO.output(self.buzzer_pin, GPIO.LOW) # Ensure buzzer is off initially
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
        # For standalone testing, we need to set GPIO mode and cleanup here.
        # In an application, the main script would handle this.
        GPIO.setmode(GPIO.BCM)
        print("Initializing Buzzer (standalone test)...")
        buzzer = PassiveBuzzer(DEFAULT_BUZZER_PIN)
        print(f"Buzzer Initialized on GPIO {DEFAULT_BUZZER_PIN} (standalone test).")

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
            print("Cleaning up buzzer GPIO (standalone test)...")
            buzzer.cleanup() # This now only stops PWM and sets pin LOW
        GPIO.cleanup() # Full cleanup for standalone test
        print("Buzzer test finished (standalone test).")

# End of buzzer_pwm.py
