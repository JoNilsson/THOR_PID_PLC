"""
Blower Monitor Module for THOR SiC Heater Control System
Author: Johanness A. Nilsson for TERRAFORM INDUSTRIES 2025
Monitors blower operation via current sensing SSR on GPIO Pin 14
"""

import time
import board
import digitalio

class BlowerMonitor:
    """Monitors blower operation via current sensing SSR on GPIO Pin 14"""

    def __init__(self, required_states=None, error_callback=None):
        """
        Initialize blower monitoring

        Args:
            required_states: List of system states where blower must be running
            error_callback: Function to call when blower failure detected
        """
        # Standard CircuitPython digitalio for GPIO access
        # try to access GPIO Pin 14 on the P1AM-GPIO shield
        # Docs on Py P1AM GPIO are sparese, so using some boilerplate micropython methods
        try:
            # D14 = GPIO digital pin 14
            self.blower_pin = digitalio.DigitalInOut(board.D14)
            self.blower_pin.direction = digitalio.Direction.INPUT
            self.blower_pin.pull = digitalio.Pull.UP  # Pull-up, so LOW means current detected
        except (AttributeError, ValueError) as e:
            # If D14 isn't available directly, try using a generic pin reference
            import microcontroller
            self.blower_pin = digitalio.DigitalInOut(microcontroller.pin.P14)
            self.blower_pin.direction = digitalio.Direction.INPUT
            self.blower_pin.pull = digitalio.Pull.UP

        self.required_states = required_states or []
        self.error_callback = error_callback
        self.blower_status = False
        self.last_check_time = time.monotonic()
        self.check_interval = 0.5  # Check every 500ms
        self.error_code = 101  # Default error code for blower issues

    def is_blower_running(self):
        """
        Check if blower is running based on current sensor
        Returns True if running, False if not
        """
        # LOW signal (False) means current detected == blower running
        # Invert value; SSR closes (LOW) when current is detected
        return not self.blower_pin.value

    def check_blower(self, current_state):
        """
        Check if blower is running and required for current state

        Args:
            current_state: Current system state

        Returns:
            (is_safe, error_event) tuple - error_event will be None if no issues
        """
        current_time = time.monotonic()

        # Only check at specified intervals to avoid overload
        if current_time - self.last_check_time < self.check_interval:
            return True, None

        self.last_check_time = current_time
        self.blower_status = self.is_blower_running()

        # Check if blower needs to be running in this state
        if current_state in self.required_states and not self.blower_status:
            if self.error_callback:
                return False, self.error_callback(
                    self.error_code, 
                    "Blower not running - airflow required for operation"
                )
            return False, None

        return True, None

    def verify_during_self_check(self):
        """
        Verify blower operation during system self-check
        Returns (success, message) tuple
        """
        blower_running = self.is_blower_running()
        self.blower_status = blower_running

        if blower_running:
            return True, "Blower operation verified"
        else:
            return False, "Blower not running - check blower power and connections"
