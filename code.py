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
- Slot 2: P1-04AD for current transformer monitoring
- Slot 3: P1-08TRS for status indicators
- Slot 4: P1-04DAL-1 for SCR control
- Slot 5: P1-15CDD1 for button inputs

Written for controlling a Dwyer-Omega SCR39-48-080-S9
"""

import time
import P1AM
from P1AM.constants import *

# System state constants (instead of enum)
class SystemState:
    IDLE = 0
    SELF_CHECK = 1
    WARM_UP = 2
    WARM_UP_COMPLETE = 3
    FULL_TEMP = 4
    FULL_TEMP_COMPLETE = 5
    ERROR = 6
    SHUTDOWN = 7
    
    # Dictionary to convert state values to names for display
    NAMES = {
        0: "IDLE",
        1: "SELF_CHECK",
        2: "WARM_UP",
        3: "WARM_UP_COMPLETE",
        4: "FULL_TEMP",
        5: "FULL_TEMP_COMPLETE",
        6: "ERROR",
        7: "SHUTDOWN"
    }

# Button states constants
class ButtonState:
    NOT_PRESSED = 0
    PRESSED = 1
    RELEASED = 2

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

# Button handling with debouncing
class Button:
    def __init__(self, digital_in, debounce_time=0.05, is_normally_closed=True):
        self.digital_in = digital_in
        self.debounce_time = debounce_time
        self.last_state = False
        self.last_change_time = time.monotonic()
        self.current_state = ButtonState.NOT_PRESSED
        self.is_normally_closed = is_normally_closed
    
    def update(self):
        # Read the current value of the button input
        current_reading = self.digital_in.value
        current_time = time.monotonic()
        
        # Only process if debounce time has elapsed
        if current_time - self.last_change_time > self.debounce_time:
            # Check if state has changed
            if current_reading != self.last_state:
                self.last_change_time = current_time
                self.last_state = current_reading
                
                # For NC buttons - when HIGH, the button is pressed (path to ground broken)
                # For NO buttons - when LOW, the button is pressed (path to ground made)
                if (self.is_normally_closed and current_reading) or (not self.is_normally_closed and not current_reading):
                    self.current_state = ButtonState.PRESSED
                else:
                    self.current_state = ButtonState.RELEASED
            else:
                # Reset to not pressed after processing the edge
                if self.current_state == ButtonState.PRESSED or self.current_state == ButtonState.RELEASED:
                    self.current_state = ButtonState.NOT_PRESSED
        
        return self.current_state

# Configuration constants
# Temperature setpoints
WARM_UP_SETPOINT = 100.0  # Initial warm-up temperature in degrees F
FULL_TEMP_SETPOINT = 150.0  # Target full operation temperature in degrees F

# Temperature thresholds
TEMP_HYSTERESIS = 5.0  # Hysteresis to prevent threshold oscillation

# Current monitoring thresholds
CURRENT_THRESHOLD = 180.0  # Amperes - SCR output threshold (assuming 200A max)

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

# Create button objects
initialize_button = Button(initialize_button_input, is_normally_closed=True)
start_button = Button(start_button_input, is_normally_closed=True)
estop_button = Button(estop_button_input, is_normally_closed=False)  # E-STOP is normally open

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

# Variables for system state control
current_state = SystemState.IDLE
previous_state = None
state_entry_time = time.monotonic()
last_print_time = 0
print_interval = 1.0  # Status print interval in seconds
led_pattern_timer = time.monotonic()
led_pattern_state = False  # Toggle state for blinking

# Error handling variables
error_code = 0
error_message = ""

# Set all lights off initially
green_light.value = False
amber_light.value = False
blue_light.value = False
red_light.value = False

# Function to check E-STOP status
def check_estop():
    """
    Checks if E-STOP is activated
    E-STOP is a normally open switch - when pressed, it pulls the signal LOW
    Returns True if E-STOP is pressed (emergency condition)
    """
    return not estop_button_input.value  # NOT because LOW = pressed for NO switch

# Function to read temperature safely
def read_temperature():
    # First check E-STOP
    if check_estop():
        set_error(100, "EMERGENCY STOP ACTIVATED")
        return None
        
    try:
        # Read primary temperature (Slot 1, Channel 1)
        temp = thm_module[1].value
        if temp is None or temp < 0 or temp > 2000:  # Sanity check
            raise ValueError("Invalid temperature reading")
        return temp
    except Exception as e:
        set_error(1, f"Temperature reading error: {e}")
        return None

# Function to read current safely
def read_current():
    # First check E-STOP
    if check_estop():
        set_error(100, "EMERGENCY STOP ACTIVATED")
        return None
        
    try:
        # Read current transformer values
        ct1 = current_module[1].value  # Phase 1 current
        ct2 = current_module[2].value  # Phase 2 current
        ct3 = current_module[3].value  # Phase 3 current
        
        # Convert raw values to amperes (scaling depends on CT setup)
        # This scaling would need to be calibrated for the specific CTs used
        current_a = ct1 * 0.333 # Example scaling for 200A/0.333V CT
        current_b = ct2 * 0.333
        current_c = ct3 * 0.333
        
        # Check for overcurrent condition
        if (current_a > CURRENT_THRESHOLD or 
            current_b > CURRENT_THRESHOLD or 
            current_c > CURRENT_THRESHOLD):
            set_error(2, f"Overcurrent detected: A={current_a:.1f}, B={current_b:.1f}, C={current_c:.1f}")
            return None
            
        # Return average current for monitoring
        return (current_a + current_b + current_c) / 3
    except Exception as e:
        set_error(3, f"Current reading error: {e}")
        return None

# Error handling function
def set_error(code, message):
    global error_code, error_message, current_state
    error_code = code
    error_message = message
    if current_state != SystemState.ERROR:
        print(f"ERROR {code}: {message}")
        # Transition to error state
        transition_to_state(SystemState.ERROR)

# State transition function
def transition_to_state(new_state):
    global current_state, previous_state, state_entry_time
    if new_state != current_state:
        previous_state = current_state
        current_state = new_state
        state_entry_time = time.monotonic()
        
        # State entry actions
        if new_state == SystemState.IDLE:
            print("Entering IDLE state")
            # Set SCR to minimum value
            scr_output.real = 4.0
            # Turn off all status lights except slow flashing green
            amber_light.value = False
            blue_light.value = False
            red_light.value = False
            
        elif new_state == SystemState.SELF_CHECK:
            print("Entering SELF_CHECK state")
            # Reset PID controller
            pid.update_setpoint(WARM_UP_SETPOINT)
            pid.integral = 0
            # Turn off all lights during self-check initialization
            green_light.value = False
            amber_light.value = False
            blue_light.value = False
            red_light.value = False
            # Set SCR to minimum value
            scr_output.real = 4.0
            
        elif new_state == SystemState.WARM_UP:
            print(f"Entering WARM_UP state, setpoint: {WARM_UP_SETPOINT}°F")
            pid.update_setpoint(WARM_UP_SETPOINT)
            # Set status lights
            green_light.value = True
            amber_light.value = False
            blue_light.value = False
            red_light.value = False
            
        elif new_state == SystemState.WARM_UP_COMPLETE:
            print("Warm-up temperature reached")
            # Set status lights
            green_light.value = True
            amber_light.value = True  # Solid amber indicates warm-up complete
            blue_light.value = False
            red_light.value = False
            
        elif new_state == SystemState.FULL_TEMP:
            print(f"Entering FULL_TEMP state, setpoint: {FULL_TEMP_SETPOINT}°F")
            pid.update_setpoint(FULL_TEMP_SETPOINT)
            # Set status lights
            green_light.value = True
            amber_light.value = False
            blue_light.value = False
            red_light.value = False
            
        elif new_state == SystemState.FULL_TEMP_COMPLETE:
            print("Full temperature reached")
            # Set status lights
            green_light.value = True
            amber_light.value = False
            blue_light.value = True  # Solid blue indicates full temp reached
            red_light.value = False
            
        elif new_state == SystemState.ERROR:
            print(f"Entering ERROR state: {error_message}")
            # Set SCR to minimum value
            scr_output.real = 4.0
            # Turn off all status lights except red
            green_light.value = False
            amber_light.value = False
            blue_light.value = False
            # Red light will flash in the error state handler
            
        elif new_state == SystemState.SHUTDOWN:
            print("Entering SHUTDOWN state")
            # Begin graceful shutdown
            # Keep status lights according to previous state
            # SCR output will be gradually reduced in the shutdown state handler

# Handle the sequential light pattern for self-check
def perform_sequential_light_test():
    # Flash each light 3 times sequentially
    for _ in range(3):
        # Green
        green_light.value = True
        time.sleep(0.2)
        green_light.value = False
        time.sleep(0.1)
        
        # Amber
        amber_light.value = True
        time.sleep(0.2)
        amber_light.value = False
        time.sleep(0.1)
        
        # Blue
        blue_light.value = True
        time.sleep(0.2)
        blue_light.value = False
        time.sleep(0.1)
        
        # Red
        red_light.value = True
        time.sleep(0.2)
        red_light.value = False
        time.sleep(0.1)

# Self-check routine
def run_self_check():
    print("Running self-check diagnostic...")
    # Test all lights in sequence
    perform_sequential_light_test()
    
    # Check modules
    if len(base.io_modules) < 6:
        set_error(10, "Missing required modules")
        return False
    
    # Check thermocouple readings
    temp = read_temperature()
    if temp is None:
        set_error(11, "Failed to read temperature during self-check")
        return False
    print(f"Initial temperature reading: {temp:.1f}°F")
    
    # Check current transformer readings
    current = read_current()
    if current is None:
        set_error(12, "Failed to read current during self-check")
        return False
    print(f"Initial current reading: {current:.2f}A")
    
    # Test SCR output (brief test at minimum)
    try:
        scr_output.real = 4.0
        time.sleep(0.5)
    except Exception as e:
        set_error(13, f"SCR output test failed: {e}")
        return False
    
    print("Self-check complete: System armed")
    return True

# Update LED patterns based on current state
def update_leds():
    global led_pattern_timer, led_pattern_state
    current_time = time.monotonic()
    
    # Update LED patterns based on current state
    if current_state == SystemState.IDLE:
        # Slow flashing green in IDLE
        if current_time - led_pattern_timer > BLINK_INTERVAL_SLOW:
            led_pattern_timer = current_time
            led_pattern_state = not led_pattern_state
            green_light.value = led_pattern_state
    
    elif current_state == SystemState.SELF_CHECK:
        # Fast flashing green during self-check
        if current_time - led_pattern_timer > BLINK_INTERVAL_FAST:
            led_pattern_timer = current_time
            led_pattern_state = not led_pattern_state
            green_light.value = led_pattern_state
    
    elif current_state == SystemState.WARM_UP:
        # Green steady, amber flashing during warm-up
        if current_time - led_pattern_timer > BLINK_INTERVAL_SLOW:
            led_pattern_timer = current_time
            led_pattern_state = not led_pattern_state
            amber_light.value = led_pattern_state
    
    elif current_state == SystemState.FULL_TEMP:
        # Green steady, blue flashing during full-temp ramp
        if current_time - led_pattern_timer > BLINK_INTERVAL_SLOW:
            led_pattern_timer = current_time
            led_pattern_state = not led_pattern_state
            blue_light.value = led_pattern_state
    
    elif current_state == SystemState.ERROR:
        # Flash red in ERROR state
        if current_time - led_pattern_timer > ERROR_BLINK_INTERVAL:
            led_pattern_timer = current_time
            led_pattern_state = not led_pattern_state
            red_light.value = led_pattern_state
    
    elif current_state == SystemState.SHUTDOWN:
        # During shutdown, flash all active lights
        if current_time - led_pattern_timer > BLINK_INTERVAL_FAST:
            led_pattern_timer = current_time
            led_pattern_state = not led_pattern_state
            if green_light.value:
                green_light.value = led_pattern_state
            if amber_light.value:
                amber_light.value = led_pattern_state
            if blue_light.value:
                blue_light.value = led_pattern_state

# Handle state-specific logic and transitions
def handle_current_state():
    global current_state
    
    # First and foremost, check E-STOP directly using the check_estop function
    # This ensures we detect E-STOP activation immediately, regardless of button logic
    if check_estop():
        # EMERGENCY STOP takes precedence over everything
        if current_state != SystemState.ERROR or error_code != 100:
            set_error(100, "EMERGENCY STOP ACTIVATED")
        # E-STOP is activated - don't process any other inputs
        # Just update the LED indicators and return
        update_leds()
        return
    
    # Read other inputs
    initialize_button_state = initialize_button.update()
    start_button_state = start_button.update()
    
    # Regular state-specific logic, only processed if E-STOP is not activated
    if current_state == SystemState.IDLE:
        # In IDLE, only respond to INITIALIZE button
        if initialize_button_state == ButtonState.PRESSED:
            transition_to_state(SystemState.SELF_CHECK)
    
    elif current_state == SystemState.SELF_CHECK:
        # Run self-check routine on first entry to state
        elapsed_in_state = time.monotonic() - state_entry_time
        if elapsed_in_state < 0.1:  # Just entered state
            if run_self_check():
                # Self-check passed, transition to armed state (still in SELF_CHECK)
                # Will transition out on next iteration
                pass
            else:
                # Self-check failed, error state is already set by run_self_check
                pass
        elif elapsed_in_state >= 3.0:  # Give time for self-check to complete
            # Transition to IDLE after successful self-check
            transition_to_state(SystemState.IDLE)
    
    elif current_state == SystemState.WARM_UP:
        # Check if we've reached warm-up temperature
        temp = read_temperature()
        if temp is not None and temp >= WARM_UP_SETPOINT:
            transition_to_state(SystemState.WARM_UP_COMPLETE)
        
        # Check for START button to initiate shutdown
        if start_button_state == ButtonState.PRESSED:
            transition_to_state(SystemState.SHUTDOWN)
    
    elif current_state == SystemState.WARM_UP_COMPLETE:
        # In warm-up complete, START button begins full-temp ramp
        if start_button_state == ButtonState.PRESSED:
            transition_to_state(SystemState.FULL_TEMP)
    
    elif current_state == SystemState.FULL_TEMP:
        # Check if we've reached full temperature
        temp = read_temperature()
        if temp is not None and temp >= FULL_TEMP_SETPOINT:
            transition_to_state(SystemState.FULL_TEMP_COMPLETE)
        
        # Check for START button to return to warm-up
        if start_button_state == ButtonState.PRESSED:
            transition_to_state(SystemState.WARM_UP)
    
    elif current_state == SystemState.FULL_TEMP_COMPLETE:
        # In full-temp complete, START button initiates shutdown
        if start_button_state == ButtonState.PRESSED:
            transition_to_state(SystemState.SHUTDOWN)
    
    elif current_state == SystemState.ERROR:
        # In ERROR state, can only transition back to IDLE after acknowledgment and NO E-STOP
        if error_code != 100 and initialize_button_state == ButtonState.PRESSED:
            # Reset error state (if not E-STOP)
            error_code = 0
            error_message = ""
            transition_to_state(SystemState.IDLE)
        # Note: If error_code is 100 (E-STOP), we can only clear it when E-STOP is not activated
    
    elif current_state == SystemState.SHUTDOWN:
        # Gradually reduce output to prevent thermal shock
        if scr_output.real > 4.1:  # If above minimum
            scr_output.real -= 0.1  # Gradually reduce
        else:
            # Shutdown complete
            transition_to_state(SystemState.IDLE)
    
    # Update LEDs based on current state
    update_leds()

print(f"System initialized.")
print("Beginning control loop...")
print("Press INITIALIZE button (green) to begin")

# Main control loop
while True:
    try:
        # Check E-STOP status first - this has highest priority
        estop_active = check_estop()
        
        # If E-STOP is activated and we're not already in ERROR state with E-STOP code,
        # immediately transition to ERROR state
        if estop_active and (current_state != SystemState.ERROR or error_code != 100):
            set_error(100, "EMERGENCY STOP ACTIVATED")
            # Set SCR to minimum immediately
            scr_output.real = 4.0
            
        # Handle state machine
        handle_current_state()
        
        # Only proceed with normal operations if E-STOP is not active
        if not estop_active:
            # Read current temperature 
            current_temp = read_temperature()
            
            # Read current
            current_reading = read_current()
            
            # Only run PID control in active heating states and if no errors
            if (current_state == SystemState.WARM_UP or 
                current_state == SystemState.WARM_UP_COMPLETE or
                current_state == SystemState.FULL_TEMP or
                current_state == SystemState.FULL_TEMP_COMPLETE) and error_code == 0:
                
                if current_temp is not None:
                    # Calculate PID output
                    output = pid.compute(current_temp)
                    
                    # Apply control output if calculated
                    if output is not None:
                        # Set SCR control signal (4-20mA)
                        scr_output.real = output
                        
                        # Update heating indicator state for status reporting
                        is_heating = scr_output.real > HEATING_THRESHOLD
        else:
            # E-STOP is active, ensure SCR output is at minimum
            scr_output.real = 4.0
            current_temp = None
            current_reading = None
            
        # Print status every second
        current_time = time.monotonic()
        if current_time - last_print_time >= print_interval:
            # Format temperature and current readings
            temp_str = f"{current_temp:.1f}°F" if current_temp is not None else "ERROR"
            curr_str = f"{current_reading:.2f}A" if current_reading is not None else "ERROR"
            
            # Status strings
            state_str = SystemState.NAMES[current_state]
            output_str = f"{scr_output.real:.2f}mA" if current_state not in [SystemState.IDLE, SystemState.ERROR] else "OFF"
            
            # LED status
            green_status = "ON" if green_light.value else "OFF"
            amber_status = "ON" if amber_light.value else "OFF"
            blue_status = "ON" if blue_light.value else "OFF"
            red_status = "ON" if red_light.value else "OFF"
            
            # E-STOP status
            estop_status = "ACTIVATED" if estop_active else "NORMAL"
            
            print(f"State: {state_str} | E-STOP: {estop_status} | Temp: {temp_str} | Current: {curr_str} | Output: {output_str}")
            print(f"Indicators: Green: {green_status} | Amber: {amber_status} | Blue: {blue_status} | Red: {red_status}")
            
            if error_code != 0:
                print(f"ERROR {error_code}: {error_message}")
            
            last_print_time = current_time
            
    except Exception as e:
        # Unexpected error - transition to ERROR state
        set_error(999, f"Unhandled exception: {e}")
        # Reset outputs to safe state
        scr_output.real = 4.0  # Minimum control signal
    
    # Small delay to prevent CPU hogging
    time.sleep(0.01)