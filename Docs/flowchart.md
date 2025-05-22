**Technical Report** `Terraform Industries`  
**THOR PID-PLC Operational Flowchart V1.1**

Author [Johanness Nilsson](mailto:johanness.nilsson@terraformindustries.com)  
Date: 2025-04-30

This document provides comprehensive documentation for the THOR SiC Heater Control System, which manages temperature regulation using a P1AM-200 PLC with PID control.

## Overview

The THOR Temperature Control System is designed to provide precise control over the array of 12 silicon carbide (SiC) heating elements using a programmable logic controller, the [**P1AM-200**](https://drive.google.com/open?id=1O5YNwyYIEl-qYq0pGG7m0gbB4kYj8btH). The system implements a state-based control flow with multiple operational modes and safety features.

## Hardware Components

- **PLC Controller**: P1AM-200 programmable logic controller

  - **MODULES**:
  - **Thermocouple Module**: [**P1-04THM**](https://facts-engineering.github.io/modules/P1-04THM/P1-04THM.html?python) in slot 1 for temperature sensing
  - **Analog Input Module**: [**P1-04AD**](https://facts-engineering.github.io/modules/P1-04AD/P1-04AD.html?python) in slot 2 for reading in the signals from the 3 Current Transformers (0.333Vac signal may need to be conditioned first?)
  - **Relay Module**: [**P1-08TRS**](https://facts-engineering.github.io/modules/P1-08TRS/P1-08TRS.html?python) in slot 3 for safety indicator control
  - **Analog Output Module**: [**P1-04DAL-1**](https://facts-engineering.github.io/modules/P1-04DAL-1/P1-04DAL-1.html?python) in slot 4 for SCR control (4-20mA signal)
  - **Discrete DC Input/Output Module**: [**P1-15CDD1**](https://facts-engineering.github.io/modules/P1-15CDD1/P1-15CDD1.html?python) in slot 5 for input signals from the interface buttons (+24Vdc sink)

- **Split-Core Current Transformers**: ACTL-0750-200, 200A / 0.333Vac for current sensing and monitoring, system over-current detection, three total, one per phase
- **K-Type Thermocouples**: 4 Omega M12KIN-¼-U-6-D Inconel TC units for temperature sensing, PID loop tuning to maintain optimal system temperature.
- **Heating Elements**: 12 SiC heaters controlled via 3 SCR (Silicon-Controlled Rectifier) channels on a single trigger input channel.

## Control Interface

The system is operated through three primary control buttons:

### E-STOP Mushroom Button (RED)

- **Connection**: The E-STOP button is and NC SPST switch connected to the P1-15CDD1 in Slot 5, input 3
- **Function**: Emergency shutdown
- **Operation**: When pressed, the path to ground is broke, the signal is pulled high, the PLC immediately stops all heating operations and transitions to ERROR state
- **Visual Indicator**: Red light flashing
- **Safety Feature**: The switch must be physically twisted to reset, and the INITIALIZE button pressed once to re-initialize and self-check before the system can be restarted in heating modes.

### INITIALIZE Button (GREEN)

- **Connection**: The Initialize button is a momentary NC type switch connected to the P1-15CDD1 in Slot 5, on input 1
- **Function**: System arming & system reset
- **Operation**: When pressed, the path to ground is momentarily broke, the signal is pulled high, the PLC initiates self-check sequence from IDLE state
- **Visual Indicator**: Green light flashing during self-check, solid when armed
- **Secondary Function**: When pressed, the button resets system after an emergency shutdown or error condition

### START / SHUTDOWN Button (AMBER)

- **Connection**: The START / SHUTDOWN button is a momentary NC type switch connected to the P1-15CDD1 in Slot 5, on input 2 and like the other input buttons when pressed the signal goes high.
- **Function**: Multi-function control
- **Operations**:
  - After self-check: Starts warm-up sequence
  - During warm-up: Initiates graceful shutdown
  - After warm-up complete: Begins full-power ramp-up
  - During full-power operation: Returns to warm-up state
- **Visual Indicators**:
  - Green light slow flashing: System powered on, Idle state
  - Green light quick flashing: System initializing, self-check in progress
  - Green light steady: System Ready / Armed
  - Amber light flashing: Warm-up ramp in progress
  - Amber light steady: Warm-up complete
  - Blue light flashing: Full-temp ramp in progress
  - Blue light steady: Full target temperature reached
  - Red light flashes to indicate error condition
  - Description of light relay connections:
    - Green light is connected to relay NO2
    - Amber light is connected to relay NO3
    - Blue light is connected to relay NO4
    - Red light is connected to relay NO5

## Operational States

### 1\. IDLE

- Initial powered state
- System is inactive but ready for initialization
- No heating elements are active and the PLC is not receiving commands
- Transition: Press INITIALIZE button to begin self-check

### 2\. SELF CHECK

- PLC runs diagnostic routines & initiates the Serial Console and Data Acquisition
- Initially during the PLC self check, all lights will flash 3 times quickly, sequentially.
- Green light continues flashing rapidly during the self check phase
- Checks all modules and connections for proper operation
- Transitions:
  - If successful: System becomes ARMED (Green light solid)
  - If unsuccessful: Transitions to ERROR state

### 3\. WARM-UP

- **Warm-up Ramp (Amber Light Flashing)**

  - Heating elements begin warming up to initial temperature
  - Temperature gradually increases to warm-up setpoint
  - PID controller manages the ramp rate
  - Pressing START during this phase initiates a graceful shutdown

- **Warm-up Complete (Amber Light Steady)**
  - System maintains warm-up temperature
  - Ready for full-power operation
  - Pressing START transitions to full-power ramp

### 4\. FULL-TEMP

- **Full-Temp Ramp (Blue Light Flashing)**

  - Heating elements increase to target temperature
  - PID controller manages the ramp rate and stability
  - Pressing START returns to warm-up state

- **Target Temp Reached (Blue Light Steady)**
  - System maintains target temperature
  - PID controller actively stabilizes temperature
  - Pressing START initiates graceful shutdown sequence

### 5\. ERROR

- Activates when a system fault is detected
- Red light flashes to indicate error condition
- All heating elements are immediately deactivated
- Transitions back to IDLE after acknowledgment / reset

### 6\. SHUTDOWN

- Graceful ramp-down of heating elements
- Prevents thermal shock to system components
- Returns to IDLE state when complete

## PID Control System

The system implements a standard Proportional-Integral-Derivative (PID) control algorithm to maintain precise temperature regulation:

- **Proportional Term (P)**: Responds directly to the current error (difference between setpoint and actual temperature)
- **Integral Term (I)**: Addresses accumulated error over time
- **Derivative Term (D)**: Responds to the rate of change of the process variable

### PID Default Parameters

- **KP** (Proportional Gain): 2.0
- **KI** (Integral Gain): 0.1
- **KD** (Derivative Gain): 0.5
- **Sample Time**: 0.5 seconds

### Control Output

- SCR control via 4-20mA analog output signal
- A single analog signal channel controls 3 SCR units, one per phase of the 480VAC input  
  The SCR units are in this configuration as delivered from the manufacture
- Output scaling from _\`MIN_COUNT\`_ (819) to _\`MAX_COUNT_\` (4095)

## Safety Features

1. **Emergency Stop**: E-STOP button immediately halts all heating operations
2. **Self-Check**: System diagnostics run before operation is permitted
3. **Invalid Temperature Detection**: System transitions to ERROR state if temperature readings are invalid
4. **Over-Current Detection:** System transitions to ERROR state if current readings are over the allowed thresholds on the outputs from any of the SCR units.
5. **Graceful Shutdown**: Controlled ramp-down prevents thermal shock
6. **Relay Safety**: Secondary relay control provides additional safety circuit
7. **Error Handling**: serial console logs error detection and reporting

## System Flow Diagram

The system follows a state-based operational flow as illustrated in the accompanying flowchart [**THOR PLC Operation Flowchart**](https://sites.google.com/terraformindustries.com/thor-plc-operational-flowchart/home). This diagram shows all possible state transitions, button interactions, and decision points in the control logic.

## Implementation Notes

The control system is implemented in Python using the P1AM library for PLC interaction.

- PID controller
- Anti-windup protection
- Hardware initialization and error checking
- Main control loop with safety monitoring
- Indicator relays control based on temperature thresholds
- SCR control via 4-20mA analog output

## Operational Procedure

1. Power on the system (IDLE state)  
   _120VAC is supplied to the PLC from a buck transformer in the main power enclosure_
2. Press Green INITIALIZE button to begin self-check
3. Once armed (Green light solid), press Amber START button to begin warm-up
4. When warm-up completes (Amber light steady), press Amber START to begin full-power operation
5. System will maintain target temperature (Hard-coded temperature points)
6. To return to warm-up mode, press START during full-power
7. To shut down gracefully, press START during warm-up mode

In case of emergency, press the E-STOP button to immediately halt all operations.
