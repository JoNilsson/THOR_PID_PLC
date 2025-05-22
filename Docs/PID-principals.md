# PID Control Principles in the THOR SiC Heater Control System

## Overview

The THOR SiC Heater Control System implements a Proportional-Integral-Derivative (PID) control algorithm to precisely maintain temperatures during various heating stages. This document analyzes the PID implementation and principles as found in the control system code.

## PID Controller Implementation

The system uses a custom `PIDController` class (lines 113-174) that implements the three fundamental components of PID control:

```python
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
```

### Key Parameters

The controller is configured with the following parameters:

- **KP = 2.0** (line 40): Proportional gain - determines how aggressively the system responds to the current error
- **KI = 0.1** (line 41): Integral gain - addresses accumulated error over time to eliminate steady-state offset
- **KD = 0.5** (line 42): Derivative gain - provides damping to reduce overshoot by responding to the rate of change
- **Sample time = 0.5 seconds** (default): Time between PID calculations, balancing responsiveness with stability
- **Output limits**: Maps to 4-20mA control signal (lines 968-969)

## PID Algorithm Mechanics

### 1. Error Calculation

The foundation of the PID algorithm is the error, which is the difference between the setpoint (desired temperature) and the process variable (actual temperature):

```python
error = self.setpoint - process_variable
```

### 2. Proportional Term

The proportional term produces an output proportional to the current error:

```python
p_term = self.kp * error
```

This term provides the immediate correction. With KP=2.0, for every degree of error, the proportional term contributes 2 units to the output.

### 3. Integral Term

The integral term accumulates errors over time:

```python
self.integral += error * elapsed_time
i_term = self.ki * self.integral
```

This term eliminates steady-state error by gradually increasing correction until the setpoint is reached. With KI=0.1, the integral contribution grows slowly, preventing rapid overcorrection.

### 4. Derivative Term

The derivative term responds to the rate of change of the process variable:

```python
derivative = (process_variable - self.last_process_variable) / elapsed_time
d_term = -self.kd * derivative
```

Note that this implementation calculates the derivative on the process variable rather than the error, which provides better stability when the setpoint changes. The negative sign ensures that an increasing temperature (positive derivative) produces a negative contribution, dampening the system.

### 5. Output Calculation and Anti-Windup

The final output is the sum of all three terms:

```python
output = p_term + i_term + d_term
```

This output is constrained to the defined limits:

```python
output = max(self.output_min, min(self.output_max, output))
```

The controller implements anti-windup protection (lines 163-164) to prevent integral term from growing excessively when the output saturates:

```python
if (output == self.output_min or output == self.output_max) and error * output > 0:
    self.integral -= error * elapsed_time
```

This reduces the integral term when the output is at its limits and the error would cause the term to grow further in the same direction.

## System Integration: Inputs and Outputs

### Inputs to the PID Controller

1. **Temperature Readings**: From K-type thermocouples on the P1-04THM module (Slot 1)
   - Acquired via `read_temperature()` function (line 807-816)
   - Passed to the PID controller in the heating state handlers (lines
   691-694, 718-719, 733-735)

2. **Setpoints**: Dynamic temperature targets based on system state
   - WARM_UP_SETPOINT = 100.0°F (line 30)
   - FULL_TEMP_SETPOINT = 150.0°F (line 31)
   - Setpoints are updated when transitioning between states (lines 547, 558, 564)

### Output from the PID Controller

The PID controller outputs a value representing the control signal in the 4-20mA range:

1. **Control Signal Generation**: 
   - PID output maps directly to a 4-20mA signal (lines 968-969)
   - MIN_COUNT = 819 (4mA) and MAX_COUNT = 4095 (20mA) define the DAC range (lines 45-46)

2. **SCR Control**:
   - The 4-20mA signal is sent to the SCR unit via P1-04DAL-1 module (Slot 4, Channel 1)
   - The SCR (Silicon Controlled Rectifier) regulates power to the heater elements
   - HEATING_THRESHOLD = 6.0mA defines the minimum current that activates heating (line 47)

## State-Based Temperature Control

The system implements different temperature setpoints based on the current state:

1. **WARM_UP State**: 
   - Setpoint = 100.0°F
   - Transitions to WARM_UP_COMPLETE when temperature is reached

2. **FULL_TEMP State**: 
   - Setpoint = 150.0°F 
   - Transitions to FULL_TEMP_COMPLETE when temperature is reached

3. **SHUTDOWN State**:
   - Gradually reduces output to safely cool the system
   - Decrements output by 0.1mA per iteration until minimum is reached (lines 797-801)

## PID Tuning Considerations

The current PID parameters (KP=2.0, KI=0.1, KD=0.5) reflect a balanced approach:

1. **Moderate Proportional Gain**: Provides reasonable response to error without excessive overshoot
2. **Low Integral Gain**: Slowly corrects steady-state error without causing oscillation
3. **Moderate Derivative Gain**: Provides damping to reduce overshoot

These values are well-suited for thermal systems, which typically:
- Have significant time delays (thermal inertia)
- Respond slowly to control inputs
- Require gentle control to prevent overshoot

## Safety Aspects of the PID Implementation

The control system incorporates several safety features related to temperature control:

1. **Output Limiting**: 
   - Prevents excessive power application regardless of PID calculation
   - Configured in the PID controller initialization (lines 968-969)

2. **Error Handling**:
   - Temperature reading errors trigger system ERROR state
   - Invalid temperature readings (negative or >2000°F) are caught and reported

3. **State Transitions**:
   - Temperature thresholds include hysteresis (TEMP_HYSTERESIS = 5.0°F, line 34) to prevent oscillation
   - Transitions between heating states only occur when temperature conditions are met

4. **Emergency Shutdown**:
   - In ERROR or SHUTDOWN states, SCR output is immediately set to minimum (4.0mA)
   - E-STOP activation triggers immediate transition to ERROR state

## Performance Optimization

The PID algorithm includes several optimizations:

1. **Sample Time Limiting**: 
   - Only computes new output when sample_time has elapsed (lines 134-135)
   - Prevents excessive computation while ensuring timely updates

2. **Derivative on Measurement**: 
   - Calculates derivative based on process variable rather than error
   - Provides smoother response during setpoint changes

3. **Anti-Windup Protection**: 
   - Prevents integral term from growing excessively when output saturates
   - Resets integral term when setpoint changes (line 174)

## Conclusion

The THOR SiC Heater Control System implements a comprehensive PID control solution that:

1. Provides precise temperature control through all heating phases
2. Balances responsiveness with stability through appropriate PID tuning
3. Implements safety measures to protect the system and operators
4. Integrates with the state machine for complex process control

This implementation demonstrates fundamental PID principles applied to industrial temperature control, with specific adaptations for SCR-based heating elements and K-type thermocouple feedback.