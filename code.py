"""
P1AM-200 PID Temperature Control System - THOR SiC Heater Control System
Author: Johanness A. Nilsson for TERRAFORM INDUSTRIES 2025
This program implements a state-based PID control system that:
1. Reads temperature from K-type thermocouples on P1-04THM (Slot 1)
2. Uses PID control to maintain temperature at various setpoints based on state
3. Controls relay outputs (P1-08TRS, Slot 3) for status indication
4. Controls 4-20mA analog output (P1-04DAL-1, Slot 4, Ch 1) to drive SCR units
5. Reads button inputs from P1-15CDD1 (Slot 5)
6. Monitors current using P1-04AD (Slot 2)

Hardware Configuration:
- P1-02AC power supply
- P1AM-ETH, P1AM-GPIO, P1AM-SERIAL
- P1AM-200 CPU
- Slot 1: P1-04THM with K-type thermocouples
- Slot 2: P1-04AD for 4-20mA current transformer module monitoring
- Slot 3: P1-08TRS for status indicators
- Slot 4: P1-04DAL-1 for SCR control
- Slot 5: P1-15CDD1 for button inputs

Written for controlling a Dwyer-Omega SCR39-48-080-S9

Added Features (May 2025):
- RS-485 Serial control interface
- TCP/IP Network monitoring and data logging
- Manual control mode for direct SCR output manipulation
"""

import time
import P1AM
import board
import digitalio
from blower_monitor import BlowerMonitor

# Import serial control modules
import command_processor
import serial_interface
import network_interface

# Configuration constants
# Temperature setpoints
WARM_UP_SETPOINT = 100.0  # Initial warm-up temperature in degrees F
FULL_TEMP_SETPOINT = 150.0  # Target full operation temperature in degrees F

# Temperature thresholds
TEMP_HYSTERESIS = 5.0  # Hysteresis to prevent threshold oscillation

# Current monitoring thresholds
CURRENT_THRESHOLD = 70.0  # Amperes, SCR output threshold

# PID tuning parameters
KP = 2.0  # Proportional gain
KI = 0.1  # Integral gain
KD = 0.5  # Derivative gain

# Analog output scaling
MIN_COUNT = 819   # Corresponds to 4mA
MAX_COUNT = 4095  # Corresponds to 20mA
HEATING_THRESHOLD = 6.0  # mA - SCR is actively heating when output > this value

# Light pattern parameters
BLINK_INTERVAL_SLOW = 1.0  # Slow blink interval in seconds
BLINK_INTERVAL_FAST = 0.3  # Fast blink interval in seconds
ERROR_BLINK_COUNT = 5      # Number of blinks in error pattern
ERROR_BLINK_INTERVAL = 0.5 # Time between error blinks

# Startup guard time
STARTUP_GUARD_TIME = 2.0  # Time after startup before processing buttons

# System state constants (instead of enum)
class SystemState:
    IDLE = 0
    SELF_CHECK = 1
    SYSTEM_ARMED = 2
    WARM_UP = 3
    WARM_UP_COMPLETE = 4
    FULL_TEMP = 5
    FULL_TEMP_COMPLETE = 6
    ERROR = 7
    SHUTDOWN = 8

    # Dictionary to convert state values to names for display
    NAMES = {
        0: "IDLE",
        1: "SELF_CHECK",
        2: "SYSTEM_ARMED",
        3: "WARM_UP",
        4: "WARM_UP_COMPLETE",
        5: "FULL_TEMP",
        6: "FULL_TEMP_COMPLETE",
        7: "ERROR",
        8: "SHUTDOWN"
    }

    # Define valid state transitions
    VALID_TRANSITIONS = {
        IDLE: [SELF_CHECK, ERROR],
        SELF_CHECK: [IDLE, SYSTEM_ARMED, ERROR],
        SYSTEM_ARMED: [WARM_UP, IDLE, ERROR],
        WARM_UP: [WARM_UP_COMPLETE, SHUTDOWN, ERROR],
        WARM_UP_COMPLETE: [FULL_TEMP, SHUTDOWN, ERROR],
        FULL_TEMP: [FULL_TEMP_COMPLETE, WARM_UP, ERROR],
        FULL_TEMP_COMPLETE: [SHUTDOWN, ERROR],
        ERROR: [IDLE],
        SHUTDOWN: [IDLE, ERROR]
    }

# Button states constants
class ButtonState:
    NOT_PRESSED = 0
    PRESSED = 1
    RELEASED = 2

# Event types
class EventType:
    BUTTON_PRESSED = "BUTTON_PRESSED"
    TEMPERATURE_REACHED = "TEMPERATURE_REACHED"
    SELF_CHECK_COMPLETE = "SELF_CHECK_COMPLETE"
    ERROR_OCCURRED = "ERROR_OCCURRED"
    ESTOP_ACTIVATED = "ESTOP_ACTIVATED"
    ESTOP_CLEARED = "ESTOP_CLEARED"
    TIMEOUT = "TIMEOUT"

# PID Controller class
class PIDController:
    def __init__(self, kp, ki, kd, setpoint, sample_time=0.5, output_min=0, output_max=300):
        self.kp = kp  # Proportional gain
        self.ki = ki  # Integral gain 
        self.kd = kd  # Derivative gain
        self.setpoint = setpoint  # Target temperature
        self.sample_time = sample_time  # Time between PID calculations
        self.output_min = output_min  # Minimum output value
        self.output_max = output_max  # Maximum output value

        # Internal state variables
        self.last_error = 0
        self.integral = 0
        self.last_time = time.monotonic()
        self.last_process_variable = 0

    def compute(self, process_variable):
        current_time = time.monotonic()
        elapsed_time = current_time - self.last_time

        # Only compute if sample_time has elapsed
        if elapsed_time >= self.sample_time:
            # Calculate error
            error = self.setpoint - process_variable

            # Proportional term
            p_term = self.kp * error

            # Integral term (with anti-windup)
            self.integral += error * elapsed_time
            i_term = self.ki * self.integral

            # Derivative term (on process variable, not error)
            derivative = 0
            if elapsed_time > 0:
                derivative = (process_variable - self.last_process_variable) / elapsed_time
            d_term = -self.kd * derivative  # Negative because we want to counteract change

            # Save values for next iteration
            self.last_error = error
            self.last_time = current_time
            self.last_process_variable = process_variable

            # Calculate output
            output = p_term + i_term + d_term

            # Apply output limits
            output = max(self.output_min, min(self.output_max, output))

            # If output is at limits, prevent integral windup
            if (output == self.output_min or output == self.output_max) and error * output > 0:
                self.integral -= error * elapsed_time

            return output

        return None  # No new output if sample time hasn't elapsed

    def update_setpoint(self, new_setpoint):
        """Update the controller setpoint"""
        self.setpoint = new_setpoint
        # Reset integral term to prevent bump in output
        self.integral = 0

# Button handling with robust debouncing
class Button:
    def __init__(self, digital_in, debounce_time=0.05, consistent_readings=3, is_normally_closed=True):
        self.digital_in = digital_in
        self.debounce_time = debounce_time
        self.consistent_readings = consistent_readings
        self.reading_history = [False] * consistent_readings
        self.last_state = False
        self.last_change_time = time.monotonic()
        self.current_state = ButtonState.NOT_PRESSED
        self.previous_state = ButtonState.NOT_PRESSED
        self.is_normally_closed = is_normally_closed
        self.event_fired = False  # Track if event was fired for this press

    def update(self):
        # Read the current value of the button input
        current_reading = self.digital_in.value
        current_time = time.monotonic()

        # Shift history and add new reading
        self.reading_history.pop(0)
        self.reading_history.append(current_reading)

        # Only process if debounce time has elapsed
        if current_time - self.last_change_time > self.debounce_time:
            # Convert reading to a button state
            if (self.is_normally_closed and current_reading) or (not self.is_normally_closed and not current_reading):
                button_pressed = True
            else:
                button_pressed = False

            # Check if all readings in history are consistent
            if all(r == self.reading_history[0] for r in self.reading_history):
                # State has been stable for multiple readings

                # Check if state has changed
                if button_pressed != self.last_state:
                    self.last_change_time = current_time
                    self.last_state = button_pressed

                    if button_pressed:
                        self.previous_state = self.current_state
                        self.current_state = ButtonState.PRESSED
                        self.event_fired = False  # Reset event fired flag
                    else:
                        self.previous_state = self.current_state
                        self.current_state = ButtonState.RELEASED

        # Return current button state
        return self.current_state

    def get_event_and_clear(self):
        """Get an event if a button press hasn't been processed yet"""
        if self.current_state == ButtonState.PRESSED and not self.event_fired:
            self.event_fired = True  # Mark that we've fired an event for this press
            return True
        return False

# Event class for event-driven state machine
class Event:
    def __init__(self, event_type, data=None):
        self.type = event_type
        self.data = data
        self.timestamp = time.monotonic()

    def __str__(self):
        return f"Event(type={self.type}, data={self.data})"

# LED Manager class for handling indicator patterns
class LEDManager:
    def __init__(self, green, amber, blue, red):
        self.green = green
        self.amber = amber
        self.blue = blue
        self.red = red

        # Separate timers and states for each LED
        self.pattern_timers = {
            "green": time.monotonic(),
            "amber": time.monotonic(),
            "blue": time.monotonic(),
            "red": time.monotonic()
        }
        self.pattern_states = {
            "green": False,
            "amber": False,
            "blue": False,
            "red": False
        }

        # Define LED patterns
        self.patterns = {
            "OFF": self._pattern_off,
            "ON": self._pattern_on,
            "SLOW_BLINK": self._pattern_slow_blink,
            "FAST_BLINK": self._pattern_fast_blink,
            "ERROR_BLINK": self._pattern_error_blink
        }

        # Current active patterns for each LED
        self.active_patterns = {
            "green": "OFF",
            "amber": "OFF",
            "blue": "OFF",
            "red": "OFF"
        }

        # Initialize all LEDs to off
        self.reset_all()

    def reset_all(self):
        """Turn off all LEDs"""
        self.green.value = False
        self.amber.value = False
        self.blue.value = False
        self.red.value = False

    def set_pattern(self, led_name, pattern_name):
        """Set a specific pattern for a specific LED"""
        if led_name in ["green", "amber", "blue", "red"] and pattern_name in self.patterns:
            self.active_patterns[led_name] = pattern_name
            print(f"Set {led_name} LED to {pattern_name} pattern")

    def set_state_indication(self, system_state):
        """Configure LED patterns based on current system state"""
        # Reset all patterns first to avoid conflicts
        for led in ["green", "amber", "blue", "red"]:
            self.active_patterns[led] = "OFF"

        # Set patterns based on state
        if system_state == SystemState.IDLE:
            self.active_patterns["green"] = "SLOW_BLINK"

        elif system_state == SystemState.SELF_CHECK:
            self.active_patterns["green"] = "FAST_BLINK"

        elif system_state == SystemState.SYSTEM_ARMED:
            self.active_patterns["green"] = "ON"

        elif system_state == SystemState.WARM_UP:
            self.active_patterns["green"] = "ON"
            self.active_patterns["amber"] = "SLOW_BLINK"

        elif system_state == SystemState.WARM_UP_COMPLETE:
            self.active_patterns["green"] = "ON"
            self.active_patterns["amber"] = "ON"

        elif system_state == SystemState.FULL_TEMP:
            self.active_patterns["green"] = "ON"
            self.active_patterns["blue"] = "SLOW_BLINK"

        elif system_state == SystemState.FULL_TEMP_COMPLETE:
            self.active_patterns["green"] = "ON"
            self.active_patterns["blue"] = "ON"

        elif system_state == SystemState.ERROR:
            self.active_patterns["red"] = "ERROR_BLINK"

        elif system_state == SystemState.SHUTDOWN:
            # Keep current patterns but make them blink
            for led in ["green", "amber", "blue"]:
                if self.active_patterns[led] == "ON":
                    self.active_patterns[led] = "FAST_BLINK"

        print(f"Updated LED patterns for state: {SystemState.NAMES[system_state]}")
        
    def set_manual_mode_indication(self):
        """Configure LED patterns for manual control mode"""
        # Reset all patterns first
        for led in ["green", "amber", "blue", "red"]:
            self.active_patterns[led] = "OFF"
            
        # Manual mode uses alternating amber/blue pattern
        self.active_patterns["amber"] = "SLOW_BLINK"
        self.active_patterns["blue"] = "SLOW_BLINK"
        
        # Offset the timers to make them alternate
        self.pattern_timers["blue"] = time.monotonic() - (BLINK_INTERVAL_SLOW / 2)
        
        print("Updated LED patterns for MANUAL CONTROL mode")

    def update(self):
        """Update all LED states based on their current patterns"""
        current_time = time.monotonic()

        # Update each LED according to its pattern
        if self.active_patterns["green"] != "OFF":
            self.patterns[self.active_patterns["green"]](self.green, "green", current_time)

        if self.active_patterns["amber"] != "OFF":
            self.patterns[self.active_patterns["amber"]](self.amber, "amber", current_time)

        if self.active_patterns["blue"] != "OFF":
            self.patterns[self.active_patterns["blue"]](self.blue, "blue", current_time)

        if self.active_patterns["red"] != "OFF":
            self.patterns[self.active_patterns["red"]](self.red, "red", current_time)

    # Pattern implementation methods
    def _pattern_off(self, led, led_name, current_time):
        led.value = False

    def _pattern_on(self, led, led_name, current_time):
        led.value = True

    def _pattern_slow_blink(self, led, led_name, current_time):
        if current_time - self.pattern_timers[led_name] > BLINK_INTERVAL_SLOW:
            self.pattern_timers[led_name] = current_time
            self.pattern_states[led_name] = not self.pattern_states[led_name]
            led.value = self.pattern_states[led_name]

    def _pattern_fast_blink(self, led, led_name, current_time):
        if current_time - self.pattern_timers[led_name] > BLINK_INTERVAL_FAST:
            self.pattern_timers[led_name] = current_time
            self.pattern_states[led_name] = not self.pattern_states[led_name]
            led.value = self.pattern_states[led_name]

    def _pattern_error_blink(self, led, led_name, current_time):
        if current_time - self.pattern_timers[led_name] > ERROR_BLINK_INTERVAL:
            self.pattern_timers[led_name] = current_time
            self.pattern_states[led_name] = not self.pattern_states[led_name]
            led.value = self.pattern_states[led_name]

    def perform_sequential_test(self):
        """Run a sequential LED test pattern"""
        self.reset_all()

        # Flash each light 3 times sequentially
        for _ in range(3):
            # Green
            self.green.value = True
            time.sleep(0.2)
            self.green.value = False
            time.sleep(0.1)

            # Amber
            self.amber.value = True
            time.sleep(0.2)
            self.amber.value = False
            time.sleep(0.1)

            # Blue
            self.blue.value = True
            time.sleep(0.2)
            self.blue.value = False
            time.sleep(0.1)

            # Red
            self.red.value = True
            time.sleep(0.2)
            self.red.value = False
            time.sleep(0.1)

# Safety Manager to centralize safety checks
class SafetyManager:
    def __init__(self, estop_input):
        self.estop_input = estop_input
        self.previous_estop_state = False
        self.current_temp = None
        self.current_current = None
        self.error_code = 0
        self.error_message = ""
        self.current_warning = ""  # Added to store warnings that don't trigger errors
        self.blower_warning = ""   # Added to store blower-specific warnings

    def check_estop(self):
        """
        Checks if E-STOP is activated
        E-STOP is a normally open switch - when pressed, it pulls the signal LOW
        Returns True if E-STOP is pressed (emergency condition)
        """
        return self.estop_input.value

    def update(self):
        """
        Perform all safety checks and return safety status
        Returns: (is_safe, event) tuple - event will be None if no safety event occurred
        """
        # Check E-STOP first - highest priority
        estop_state = self.check_estop()

        # Detect E-STOP state changes
        if estop_state and not self.previous_estop_state:
            # E-STOP was just activated
            self.error_code = 100
            self.error_message = "EMERGENCY STOP ACTIVATED"
            self.previous_estop_state = estop_state
            print("E-STOP ACTIVATED")
            return False, Event(EventType.ESTOP_ACTIVATED)

        elif not estop_state and self.previous_estop_state:
            # E-STOP was just cleared
            self.previous_estop_state = estop_state
            print("E-STOP CLEARED")
            return True, Event(EventType.ESTOP_CLEARED)

        self.previous_estop_state = estop_state

        # If E-STOP is active, report unsafe
        if estop_state:
            return False, None

        # Add additional safety checks here if needed

        # All checks passed
        return True, None

    def set_error(self, code, message):
        """Set an error condition"""
        self.error_code = code
        self.error_message = message
        print(f"ERROR {code}: {message}")
        return Event(EventType.ERROR_OCCURRED, {"code": code, "message": message})

# State Machine class
class StateMachine:
    def __init__(self, safety_manager, led_manager, pid_controller, scr_output):
        self.current_state = SystemState.IDLE
        self.state_history = []  # Stack of previous states
        self.state_entry_time = time.monotonic()
        self.safety_manager = safety_manager
        self.led_manager = led_manager
        self.pid_controller = pid_controller
        self.scr_output = scr_output

        # Register state handlers
        self.state_handlers = {
            SystemState.IDLE: self._handle_idle,
            SystemState.SELF_CHECK: self._handle_self_check,
            SystemState.SYSTEM_ARMED: self._handle_system_armed,
            SystemState.WARM_UP: self._handle_warm_up,
            SystemState.WARM_UP_COMPLETE: self._handle_warm_up_complete,
            SystemState.FULL_TEMP: self._handle_full_temp,
            SystemState.FULL_TEMP_COMPLETE: self._handle_full_temp_complete,
            SystemState.ERROR: self._handle_error,
            SystemState.SHUTDOWN: self._handle_shutdown
        }

    def is_valid_transition(self, from_state, to_state):
        """Check if a state transition is valid"""
        if to_state in SystemState.VALID_TRANSITIONS.get(from_state, []):
            return True
        return False

    def transition_to(self, new_state, record_history=True):
        """Transition to a new state with proper entry and exit actions"""
        if new_state == self.current_state:
            return

        # Validate the transition
        if not self.is_valid_transition(self.current_state, new_state):
            print(f"ERROR: Invalid state transition from {SystemState.NAMES[self.current_state]} to {SystemState.NAMES[new_state]}")
            return

        print(f"Transitioning from {SystemState.NAMES[self.current_state]} to {SystemState.NAMES[new_state]}")

        # Store state history
        if record_history:
            self.state_history.append(self.current_state)
            if len(self.state_history) > 10:  # Limit history size
                self.state_history.pop(0)

        # Exit actions for current state
        self._exit_state(self.current_state)

        # Change state
        previous_state = self.current_state
        self.current_state = new_state
        self.state_entry_time = time.monotonic()

        # Entry actions for new state
        self._enter_state(new_state, previous_state)
 
    def _enter_state(self, state, previous_state):
        """Perform entry actions for the given state"""
        print(f"Entering {SystemState.NAMES[state]} state")

        # Configure LED patterns for the new state
        self.led_manager.set_state_indication(state)

        # State-specific entry actions
        if state == SystemState.IDLE:
            # Set SCR to minimum value
            self.scr_output.real = 4.0

        elif state == SystemState.SELF_CHECK:
            # Reset PID controller
            self.pid_controller.update_setpoint(WARM_UP_SETPOINT)
            self.pid_controller.integral = 0
            # Set SCR to minimum value
            self.scr_output.real = 4.0

        elif state == SystemState.SYSTEM_ARMED:
            # Set SCR to minimum value
            self.scr_output.real = 4.0

        elif state == SystemState.WARM_UP:
            print(f"Setting warm-up setpoint: {WARM_UP_SETPOINT}°F")
            self.pid_controller.update_setpoint(WARM_UP_SETPOINT)

        elif state == SystemState.WARM_UP_COMPLETE:
            print("Warm-up temperature reached")

        elif state == SystemState.FULL_TEMP:
            print(f"Setting full temperature setpoint: {FULL_TEMP_SETPOINT}°F")
            self.pid_controller.update_setpoint(FULL_TEMP_SETPOINT)

        elif state == SystemState.FULL_TEMP_COMPLETE:
            print("Full temperature reached")

        elif state == SystemState.ERROR:
            # Set SCR to minimum value for safety
            self.scr_output.real = 4.0
            print(f"ERROR {self.safety_manager.error_code}: {self.safety_manager.error_message}")

        elif state == SystemState.SHUTDOWN:
            # Begin graceful shutdown - LED patterns already set
            pass

    def _exit_state(self, state):
        """Perform exit actions for the given state"""
        # State-specific exit actions
        if state == SystemState.SELF_CHECK:
            # Cleanup any self-check resources
            pass

    def return_to_previous(self):
        """Return to the previous state"""
        if self.state_history:
            previous = self.state_history.pop()
            self.transition_to(previous, record_history=False)

    def process_event(self, event):
        """Process an event based on the current state"""
        print(f"Processing event: {event}")

        # Handle global events that apply in any state
        if event.type == EventType.ESTOP_ACTIVATED:
            self.transition_to(SystemState.ERROR)
            return True

        # Let the current state handler process the event
        if self.current_state in self.state_handlers:
            return self.state_handlers[self.current_state](event)

        return False

    def update(self):
        """Update the state machine"""
        # Check safety first
        is_safe, safety_event = self.safety_manager.update()

        # Process any safety events
        if safety_event:
            self.process_event(safety_event)

        # Only run state-specific logic if safe
        if is_safe:
            # Check for state timeouts
            self._check_timeouts()

            # Run the current state handler with no event
            if self.current_state in self.state_handlers:
                self.state_handlers[self.current_state](None)

    def _check_timeouts(self):
        """Check for state timeouts"""
        elapsed_time = time.monotonic() - self.state_entry_time

        # State-specific timeout handling
        if self.current_state == SystemState.SELF_CHECK and elapsed_time >= 3.0:
            self.process_event(Event(EventType.TIMEOUT, {"state": SystemState.SELF_CHECK}))

    # Individual state handlers - return True if event was handled
    def _handle_idle(self, event):
        """Handle IDLE state events"""
        if event is None:
            # No event, just regular update
            return False

        if event.type == EventType.BUTTON_PRESSED:
            if event.data == "INITIALIZE":
                self.transition_to(SystemState.SELF_CHECK)
                return True

        return False

    def _handle_self_check(self, event):
        """Handle SELF_CHECK state events"""
        elapsed_time = time.monotonic() - self.state_entry_time

        if event is None:
            # First time entry actions
            if elapsed_time < 0.1:
                print("Running self-check diagnostic...")
                # Run self check in a non-blocking way
                if run_self_check(self.safety_manager, blower_monitor):
                    # Self-check complete, will wait for timeout to transition
                    pass
            return False
 
        if event.type == EventType.TIMEOUT:
            # Self-check timeout, transition to IDLE
            self.transition_to(SystemState.SYSTEM_ARMED)
            return True

        return False

    def _handle_system_armed(self, event):
        """Handle SYSTEM_ARMED state events"""
        if event is None:
            # No event, just regular update
            return False

        if event.type == EventType.BUTTON_PRESSED:
            if event.data == "START":
                self.transition_to(SystemState.WARM_UP)
                return True

        return False

    def _handle_heating_state(self, temp):
        """Common handler for all heating states"""
        if temp is None:
            return

        # Calculate and apply PID output
        output = self.pid_controller.compute(temp)
        if output is not None:
            self.scr_output.real = output

    def _handle_warm_up(self, event):
        """Handle WARM_UP state events"""
        # First handle common heating behavior
        temp = read_temperature(self.safety_manager)
        self._handle_heating_state(temp)

        if event is None:
            # Check if setpoint reached
            if temp is not None and temp >= WARM_UP_SETPOINT:
                self.transition_to(SystemState.WARM_UP_COMPLETE)
            return False

        if event.type == EventType.BUTTON_PRESSED:
            if event.data == "START":
                self.transition_to(SystemState.SHUTDOWN)
                return True

        elif event.type == EventType.TEMPERATURE_REACHED:
            if event.data == "WARM_UP":
                self.transition_to(SystemState.WARM_UP_COMPLETE)
                return True

        return False

    def _handle_warm_up_complete(self, event):
        """Handle WARM_UP_COMPLETE state events"""
        # Continue with heating behavior
        temp = read_temperature(self.safety_manager)
        self._handle_heating_state(temp)

        if event is None:
            return False

        if event.type == EventType.BUTTON_PRESSED:
            if event.data == "START":
                self.transition_to(SystemState.FULL_TEMP)
                return True

        return False

    def _handle_full_temp(self, event):
        """Handle FULL_TEMP state events"""
        # First handle common heating behavior
        temp = read_temperature(self.safety_manager)
        self._handle_heating_state(temp)

        if event is None:
            # Check if setpoint reached
            if temp is not None and temp >= FULL_TEMP_SETPOINT:
                self.transition_to(SystemState.FULL_TEMP_COMPLETE)
            return False

        if event.type == EventType.BUTTON_PRESSED:
            if event.data == "START":
                self.transition_to(SystemState.WARM_UP)
                return True

        elif event.type == EventType.TEMPERATURE_REACHED:
            if event.data == "FULL_TEMP":
                self.transition_to(SystemState.FULL_TEMP_COMPLETE)
                return True

        return False

    def _handle_full_temp_complete(self, event):
        """Handle FULL_TEMP_COMPLETE state events"""
        # Continue with heating behavior
        temp = read_temperature(self.safety_manager)
        self._handle_heating_state(temp)

        if event is None:
            return False

        if event.type == EventType.BUTTON_PRESSED:
            if event.data == "START":
                self.transition_to(SystemState.SHUTDOWN)
                return True

        return False

    def _handle_error(self, event):
        """Handle ERROR state events"""
        if event is None:
            return False

        if event.type == EventType.BUTTON_PRESSED:
            if event.data == "INITIALIZE" and self.safety_manager.error_code != 100:
                # Reset error state if not E-STOP error
                self.safety_manager.error_code = 0
                self.safety_manager.error_message = ""
                self.transition_to(SystemState.IDLE)
                return True

        elif event.type == EventType.ESTOP_CLEARED:
            if self.safety_manager.error_code == 100:
                # Clear E-STOP error after E-STOP is physically reset
                self.safety_manager.error_code = 0
                self.safety_manager.error_message = ""
                return True

        return False

    def _handle_shutdown(self, event):
        """Handle SHUTDOWN state events"""
        if event is None:
            # Gradually reduce output
            if self.scr_output.real > 4.1:
                self.scr_output.real -= 0.1
            else:
                # Shutdown complete
                self.transition_to(SystemState.IDLE)
            return False

        return False

# Function to read temperature safely
def read_temperature(safety_manager):
    try:
        # Read primary temperature (Slot 1, Channel 1)
        temp = thm_module[1].value
        if temp is None or temp < 0 or temp > 2000:  # Sanity check
            raise ValueError("Invalid temperature reading")
        return temp
    except Exception as e:
        safety_manager.set_error(1, f"Temperature reading error: {e}")
        return None

# Function to read current safely using the 4-20mA current module
def read_current(safety_manager):
    try:
        # Read the 4-20mA signal from Channel 2 of the P1-04AD module
        # (connected to the current transformer module that outputs 4-20mA)
        raw_signal = current_module[2].value

        # Calculate the percentage of full scale (4mA = 0%, 20mA = 100%)
        # First convert raw value to mA
        signal_ma = (raw_signal / MAX_COUNT) * 20.0

        # Store warning message for low signal (open circuit) but don't trigger error
        safety_manager.current_warning = ""

        # Check for signal integrity issues (signal outside 4-20mA range)
        if signal_ma < 3.8:  # Allow for slight measurement error
            # For open circuit, just set a warning message instead of an error
            safety_manager.current_warning = f"Low current signal: {signal_ma:.2f}mA - possible open circuit"
            # Return 0 current when signal is below 4mA range
            return 0.0
        elif signal_ma > 20.2:  # Allow for slight measurement error
            safety_manager.set_error(4, f"Current signal too high: {signal_ma:.2f}mA - possible fault condition")
            return None

        # Convert 4-20mA to 0-100A (using the low range setting of the current module)
        # 4mA = 0A, 20mA = 100A
        current_value = ((signal_ma - 4.0) / 16.0) * 100.0
        if current_value < 0:
            current_value = 0  # Ensure we don't return negative current values

        # Check for overcurrent condition
        if current_value > CURRENT_THRESHOLD:
            safety_manager.set_error(2, f"Overcurrent detected: {current_value:.1f}A")
            return None

        # Return the calculated current value
        return current_value
    except Exception as e:
        safety_manager.set_error(3, f"Current reading error: {e}")
        return None

# Self-check routine
def run_self_check(safety_manager, blower_monitor):
    print("Running self-check diagnostic...")

    # Test all lights in sequence
    led_manager.perform_sequential_test()

    # Check modules
    if len(base.io_modules) < 6:
        safety_manager.set_error(10, "Missing required modules")
        return False

    # Check thermocouple readings
    temp = read_temperature(safety_manager)
    if temp is None:
        safety_manager.set_error(11, "Failed to read temperature during self-check")
        return False
    print(f"Initial temperature reading: {temp:.1f}°F")

    # Check current transformer readings
    current = read_current(safety_manager)
    if current is None:
        # Only fail if it's a real error, not just an open circuit (which returns 0.0)
        safety_manager.set_error(12, "Failed to read current during self-check")
        return False
    print(f"Initial current reading: {current:.2f}A")
    # Display warning if current is 0 but don't fail the self-check
    if current == 0 and safety_manager.current_warning:
        print(f"WARNING: {safety_manager.current_warning} - This is normal if system is not actively heating")

    # Check blower operation
    if blower_monitor:
        blower_success, blower_message = blower_monitor.verify_during_self_check()
        print(f"Blower verification: {blower_message}")

        # If blower is required but not running, fail the self-check
        if not blower_success:
            safety_manager.set_error(101, blower_message)
            safety_manager.blower_warning = blower_message
            return False

    # Test SCR output (brief test at minimum)
    try:
        scr_output.real = 4.0
        time.sleep(0.5)
    except Exception as e:
        safety_manager.set_error(13, f"SCR output test failed: {e}")
        return False

    print("Self-check complete: System ready")
    return True

# Initialize P1AM Base and modules
base = P1AM.Base()
print("P1AM Base initialized")

# List detected modules
print("Detected modules:")
for i in range(1, len(base.io_modules)):
    if base.io_modules[i] is not None:
        print(f"Slot {i}: {base.io_modules[i]}")

# Configure thermocouple module for K-type on all channels
thm_module = base[1]  # P1-04THM in slot 1
thm_module.configure_module((0x40, 0x03, 0x60, 0x05,
                           0x21, 0x01, 0x22, 0x01,
                           0x23, 0x01, 0x24, 0x01,
                           0x00, 0x00, 0x00, 0x00,
                           0x00, 0x00, 0x00, 0x00))

# Set up current monitoring module
# The P1-04AD in slot 2 is now connected to a 4-20mA current transformer module
# Positive connected to Channel 2 input, Negative connected to Channel 10 com input
# The CT module is configured for low range (0-100A)
current_module = base[2]  # P1-04AD in slot 2

# Set up relay module for status indicators
relay_module = base[3]  # P1-08TRS in slot 3
green_light = relay_module[2]   # Green light on NO2
amber_light = relay_module[3]   # Amber light on NO3
blue_light = relay_module[4]    # Blue light on NO4
red_light = relay_module[5]     # Red light on NO5

# Set up analog output module for SCR control
analog_module = base[4]  # P1-04DAL-1 in slot 4
scr_output = analog_module[1]  # Channel 1

# Set up the combo discrete module for button inputs
button_module = base[5]  # P1-15CDD1 in slot 5
# Button inputs (using NC buttons that go HIGH when pressed)
initialize_button_input = button_module.inputs[1]  # Initialize button
start_button_input = button_module.inputs[2]      # Start/Shutdown button
estop_button_input = button_module.inputs[3]      # E-STOP button

# Create button objects with improved debouncing
initialize_button = Button(initialize_button_input, debounce_time=0.05, consistent_readings=3, is_normally_closed=True)
start_button = Button(start_button_input, debounce_time=0.05, consistent_readings=3, is_normally_closed=True)
estop_button = Button(estop_button_input, debounce_time=0.05, consistent_readings=3, is_normally_closed=False)  # E-STOP is normally open

# Initialize PID controller - output directly maps to 4-20mA for SCR control
pid = PIDController(
    kp=KP, 
    ki=KI, 
    kd=KD, 
    setpoint=WARM_UP_SETPOINT,
    sample_time=0.5,
    output_min=4,   # 4mA minimum output
    output_max=20   # 20mA maximum output
)

# Initialize managers
safety_manager = SafetyManager(estop_button_input)

# Initialize blower monitor - after safety_manager is initialized
blower_monitor = BlowerMonitor(
    required_states=[
        SystemState.SELF_CHECK, 
        SystemState.SYSTEM_ARMED,
        SystemState.WARM_UP, 
        SystemState.WARM_UP_COMPLETE,
        SystemState.FULL_TEMP, 
        SystemState.FULL_TEMP_COMPLETE
    ],
    error_callback=safety_manager.set_error
)
led_manager = LEDManager(green_light, amber_light, blue_light, red_light)
state_machine = StateMachine(safety_manager, led_manager, pid, scr_output)

# Initialize interfaces for serial control and data logging
# Command processor needs to be initialized first
command_processor_obj = command_processor.CommandProcessor(state_machine, safety_manager, pid, scr_output)

# Initialize RS-485 serial interface for control
# Using P1AM-SERIAL shield on TX1/RX1 with DE on D13
serial_interface_obj = serial_interface.SerialInterface(
    command_processor=command_processor_obj,
    tx_pin=board.TX1,
    rx_pin=board.RX1,
    de_pin=board.D13,
    baudrate=9600
)

# Initialize TCP/IP network interface for data logging
# Using P1AM-ETH shield with CS pin D4 and reset pin D5
network_interface_obj = network_interface.NetworkInterface(
    command_processor=command_processor_obj,
    cs_pin=board.D4,
    reset_pin=board.D5,
    port=23  # Standard telnet port
)

# Status reporting variables
last_print_time = 0
print_interval = 1.0  # Status print interval in seconds

# Startup time for guard period
startup_time = time.monotonic()

print("System initialized")
print("Beginning control loop...")
print("Press INITIALIZE button (green) to begin")
print("Serial and network interfaces active")

# Main control loop
while True:
    try:
        # Update button states (E-STOP is always monitored regardless of mode)
        initialize_state = initialize_button.update()
        start_state = start_button.update()

        # Apply startup guard time - don't process button events during startup
        current_time = time.monotonic()
        if current_time - startup_time > STARTUP_GUARD_TIME:
            # Check for and process button events - only when not in manual mode
            if not command_processor_obj.manual_mode:
                if initialize_button.get_event_and_clear():
                    print("INITIALIZE button pressed")
                    state_machine.process_event(Event(EventType.BUTTON_PRESSED, "INITIALIZE"))

                if start_button.get_event_and_clear():
                    print("START button pressed")
                    state_machine.process_event(Event(EventType.BUTTON_PRESSED, "START"))

        # Check blower status - keep safety features operational in all modes
        is_blower_safe, blower_event = blower_monitor.check_blower(state_machine.current_state)
        if not is_blower_safe and blower_event:
            state_machine.process_event(blower_event)

        # Update interfaces
        serial_interface_obj.update()
        network_interface_obj.update()
        
        # Only update state machine if not in manual mode
        if not command_processor_obj.manual_mode:
            # Update automatic control mode
            state_machine.update()
            led_manager.update()
        else:
            # In manual mode, update command processor for logging
            command_processor_obj.update()
            
            # In manual mode, we still need to update LEDs
            # But use the manual mode LED pattern
            led_manager.update()

        # Read sensors for status reporting
        current_temp = read_temperature(safety_manager)
        current_reading = read_current(safety_manager)

        # Print status periodically - in both modes
        if current_time - last_print_time >= print_interval:
            # Format temperature and current readings
            temp_str = f"{current_temp:.1f}°F" if current_temp is not None else "ERROR"
            curr_str = f"{current_reading:.2f}A" if current_reading is not None else "ERROR"

            # Status strings
            if command_processor_obj.manual_mode:
                state_str = "MANUAL_CONTROL"
            else:
                state_str = SystemState.NAMES[state_machine.current_state]
                
            output_str = f"{scr_output.real:.2f}mA"

            # LED status
            green_status = "ON" if green_light.value else "OFF"
            amber_status = "ON" if amber_light.value else "OFF"
            blue_status = "ON" if blue_light.value else "OFF"
            red_status = "ON" if red_light.value else "OFF"

            # E-STOP status
            estop_status = "ACTIVATED" if safety_manager.check_estop() else "NORMAL"

            # Blower status
            blower_status = "RUNNING" if blower_monitor.blower_status else "OFF"

            print(f"State: {state_str} | E-STOP: {estop_status} | Blower: {blower_status} | Temp: {temp_str} | Current: {curr_str} | Output: {output_str}")
            print(f"Indicators: Green: {green_status} | Amber: {amber_status} | Blue: {blue_status} | Red: {red_status}")

            # Display any warnings (like current signal warnings)
            if safety_manager.current_warning:
                print(f"WARNING: {safety_manager.current_warning}")

            # Display any blower warnings
            if safety_manager.blower_warning:
                print(f"BLOWER WARNING: {safety_manager.blower_warning}")

            # Display any errors
            if safety_manager.error_code != 0:
                print(f"ERROR {safety_manager.error_code}: {safety_manager.error_message}")

            last_print_time = current_time

    except Exception as e:
        # Unexpected error - ensure safety
        safety_manager.set_error(999, f"Unhandled exception: {e}")
        
        # In manual mode, reset to minimal output and exit manual mode
        if command_processor_obj.manual_mode:
            scr_output.real = 4.0
            command_processor_obj.manual_mode = False
        # Otherwise transition to error state
        else:
            state_machine.transition_to(SystemState.ERROR)
            
        # Reset outputs to safe state
        scr_output.real = 4.0  # Minimum control signal

    # Small delay to prevent CPU hogging
    time.sleep(0.01)