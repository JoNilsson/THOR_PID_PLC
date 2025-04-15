"""
P1AM-200 PID Temperature Control System
Author: Johanness A. Nilsson for TERRAFORM INDUSTRIES 2025
This program implements a PID control system that:
1. Reads temperature from a K-type thermocouple on P1-04THM (Slot 1, Ch 1)
2. Uses PID control to maintain temperature at setpoint
3. Controls relay output (P1-08TRS, Slot 3, Ch 1) when temperature threshold is reached
4. Controls 4-20mA analog output (P1-04DAL-1, Slot 4, Ch 1) to drive an SCR

Hardware Configuration:
- P1-02AC power supply
- P1AM-ETH, P1AM-GPIO, P1AM-SERIAL
- P1AM-200 CPU
- Slot 1: P1-04THM with K-type thermocouple on Ch 1
- Slot 2: P1-04AD
- Slot 3: P1-08TRS
- Slot 4: P1-04DAL-1

Written for controlling a Dwyer-Omega SCR39-48-080-S9
"""

import time
import P1AM
from P1AM.constants import *

# PID Controller class
class PIDController:
    def __init__(self, kp, ki, kd, setpoint, sample_time=0.1, output_min=0, output_max=100):
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

# Configuration constants
TEMP_SETPOINT = 150.0  # Target temperature in degrees F
TEMP_THRESHOLD = 140.0  # Temperature at which to trigger the relay
TEMP_HYSTERESIS = 5.0  # Hysteresis to prevent relay chatter

# PID tuning parameters (these need to be tuned for your specific system)
KP = 2.0  # Proportional gain
KI = 0.1  # Integral gain
KD = 0.01  # Derivative gain

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

# Set up relay module
relay_module = base[3]  # P1-08TRS in slot 3
threshold_relay = relay_module[1]  # Channel 1: Temperature threshold indicator
pid_active_relay = relay_module[2]  # Channel 2: PID loop running indicator
heating_relay = relay_module[3]  # Channel 3: SCR heating active indicator
error_relay = relay_module[4]  # Channel 4: Error/fault indicator

# Set up analog output module for SCR control
analog_module = base[4]  # P1-04DAL-1 in slot 4
scr_output = analog_module[1]  # Channel 1

# Set up the combo discrete module
combo_module = base[5]  # P1-15CDD1 in slot 5
# Note: This is a combo module with both inputs and outputs
# For inputs, we'll use: combo_module.inputs[channel]
# For outputs, we'll use: combo_module.outputs[channel]

# Initialize PID controller - output directly maps to 4-20mA for SCR control
pid = PIDController(
    kp=KP, 
    ki=KI, 
    kd=KD, 
    setpoint=TEMP_SETPOINT,
    output_min=4,   # 4mA minimum output
    output_max=20   # 20mA maximum output
)

# Variables for loop tracking
last_print_time = 0
print_interval = 1.0  # Status print interval in seconds

# Heating threshold - when SCR output is significantly above minimum
HEATING_THRESHOLD = 6.0  # mA - SCR is actively heating when output > this value

# Error blinking pattern parameters
BLINK_COUNT = 5  # Number of blinks per cycle
BLINK_INTERVAL = 0.5  # Time between blink transitions in seconds
BLINK_REST = 1.0  # Rest time after completing blink cycle

# Error handling function
def blink_error_relay():
    """Blinks the error relay in the specified pattern"""
    for _ in range(BLINK_COUNT):
        error_relay.value = True
        time.sleep(BLINK_INTERVAL)
        error_relay.value = False
        time.sleep(BLINK_INTERVAL)
    time.sleep(BLINK_REST)

# Set initial relay states
threshold_relay.value = False
pid_active_relay.value = True  # PID loop is active as soon as program starts
heating_relay.value = False
error_relay.value = False

print(f"System initialized. Setpoint: {TEMP_SETPOINT}°F")
print("Beginning control loop...")
print("Press Ctrl+C to stop program")

# Main control loop
while True:
    try:
        # Read current temperature (Slot 1, Channel 1)
        current_temp = thm_module[1].value
        
        # Calculate PID output
        output = pid.compute(current_temp)
        
        # Apply control output if calculated
        if output is not None:
            # Set SCR control signal (4-20mA)
            scr_output.real = output
            
            # Control temperature threshold relay
            if current_temp >= TEMP_THRESHOLD:
                threshold_relay.value = True  # Close relay when above threshold
            elif current_temp < (TEMP_THRESHOLD - TEMP_HYSTERESIS):
                threshold_relay.value = False  # Open relay when below threshold - hysteresis
                
            # Control heating indicator relay based on SCR output
            if scr_output.real > HEATING_THRESHOLD:
                heating_relay.value = True  # SCR is actively heating
            else:
                heating_relay.value = False  # SCR is not actively heating
        
        # Print status every second
        current_time = time.monotonic()
        if current_time - last_print_time >= print_interval:
            threshold_status = "ON" if threshold_relay.value else "OFF"
            pid_status = "ON" if pid_active_relay.value else "OFF"
            heating_status = "ON" if heating_relay.value else "OFF"
            error_status = "ON" if error_relay.value else "OFF"
            print(f"Temp: {current_temp:.1f}°F | Output: {scr_output.real:.2f}mA | Threshold: {threshold_status} | PID: {pid_status} | Heating: {heating_status} | Error: {error_status}")
            last_print_time = current_time
            
    except Exception as e:
        print(f"Error: {e}")
        # Reset outputs to safe state
        threshold_relay.value = False
        pid_active_relay.value = False
        heating_relay.value = False
        scr_output.real = 4.0  # Minimum control signal
        
        # Blink error relay pattern
        blink_error_relay()
    
    # Small delay to prevent CPU hogging
    time.sleep(0.01)
