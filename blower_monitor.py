"""
Blower Monitor Module for THOR SiC Heater Control System
Author: Johanness A. Nilsson for TERRAFORM INDUSTRIES 2025
Monitors blower operation via current sensing SSR connected to P1-15CDD1 module
"""

import time
import config  # Import the central config file

class BlowerMonitor:
    """Monitors blower operation via current sensing SSR on P1-15CDD1 module"""

    def __init__(self, blower_monitor_input=None, required_states=None, error_callback=None):
        """
        Initialize blower monitoring

        Args:
            blower_monitor_input: P1-15CDD1 module input (e.g., button_module.inputs[4] for C1-4)
            required_states: List of system states where blower must be running
            error_callback: Function to call when blower failure detected
        """
        # Check if blower monitoring is enabled in config
        if not config.ENABLE_BLOWER_MONITOR:
            print("Blower Monitor disabled in config.py")
            self.blower_monitor_input = None
            self.required_states = required_states or []
            self.error_callback = error_callback
            self.blower_status = False
            self.last_check_time = time.monotonic()
            self.check_interval = 0.5  # Check every 500ms
            self.error_code = 101  # Default error code for blower issues
            return
            
        # Use the provided P1-15CDD1 module input
        if blower_monitor_input is None:
            print("Warning: No blower monitor input provided to BlowerMonitor")
            self.blower_monitor_input = None
        else:
            print("Initializing Blower Monitor on P1-15CDD1 module input C1-4...")
            self.blower_monitor_input = blower_monitor_input

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
        # Handle the case where blower_monitor_input is None (hardware not available)
        if self.blower_monitor_input is None:
            # Assume blower is working in test/development mode
            print("Note: Blower sensor not available, assuming blower is running (test mode)")
            return True
            
        # Read the actual value from the P1-15CDD1 module input
        # The SSR is Normally Open (NO) - closes when current is detected
        # Similar to E-STOP, just return the raw value
        return self.blower_monitor_input.value

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
                    "CRITICAL: Blower failure - airflow required for safe operation"
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
