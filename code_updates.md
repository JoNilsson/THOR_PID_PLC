# Code Updates Changelog

## Current Transformer Hardware Refactor (2025-05-15) [UPDATED]

The hardware for current monitoring has been upgraded from multiple current transformers to a single module that outputs a 4-20mA standard signal.

**Update (2025-05-15):** Modified error handling to treat low current signal (open circuit) as a warning rather than an error. This prevents false error states when the system is not actively heating.

### Changes Made:
1. Updated the `read_current()` function to use the new 4-20mA current transformer module
   - Changed to read from Channel 2 of the P1-04AD module
   - Implemented proper scaling from 4-20mA signal to 0-100A current values
   - Added signal integrity diagnostic checks (< 3.8mA or > 20.2mA indicates fault)
   - Removed obsolete multi-phase monitoring code (as new module provides averaged output)

2. Updated code comments and documentation
   - Added detailed comment about the new hardware connection (P1-04AD Channel 2)
   - Updated hardware configuration description

### Technical Details:
- The new current monitoring hardware outputs a standard 4-20mA signal
- Signal corresponds to 0-100A (low range setting on the module)
- Positive connection: Channel 2 input on P1-04AD
- Negative connection: Channel 10 com input on P1-04AD

### References:
- See datasheet: https://cdn.automationdirect.com/static/specs/acuamp3act3actr.pdf
- See ct_hardware_refactor.md for full implementation plan

---

# Previous Action Plan: Aligning code.py with flowchart.md

This document outlines the necessary changes to align the current `code.py` implementation with the system described in the `flowchart.md` document.

## Core Differences

1. **State-Based Architecture**

   - Current implementation: Simple linear control flow with basic error handling
   - Required: Implementation of state machine with six distinct states (IDLE, SELF_CHECK, WARM_UP, FULL_TEMP, ERROR, SHUTDOWN)

2. **User Interface**

   - Current implementation: No button interfaces, purely programmatic
   - Required: Three physical button inputs (E-STOP, INITIALIZE, START/SHUTDOWN)

3. **Visual Indicators**

   - Current implementation: Four relay outputs for basic status indication
   - Required: More complex status indication with multiple patterns for different states

4. **Temperature Control**

   - Current implementation: Single setpoint temperature control
   - Required: Multiple temperature setpoints (warm-up, full-temp) with transitions

5. **Safety Features**
   - Current implementation: Basic error handling
   - Required: Enhanced safety with E-STOP functionality, over-current detection, and more robust error handling

## Detailed Action Plan

### 1. Define State Machine Framework

- Create an enumeration for system states:

  ```python
  from enum import Enum

  class SystemState(Enum):
      IDLE = 0
      SELF_CHECK = 1
      WARM_UP = 2
      WARM_UP_COMPLETE = 3
      FULL_TEMP = 4
      FULL_TEMP_COMPLETE = 5
      ERROR = 6
      SHUTDOWN = 7
  ```

- Add state transition logic in main loop

### 2. Update Module Configuration

- Verify P1-04THM configuration for 4 K-type thermocouples
- Configure P1-04AD for reading current transformer signals
- Update P1-08TRS configuration for visual indicators
- Configure P1-15CDD1 module for button inputs

### 3. Implement Button Interface

- Add button input detection for:
  - E-STOP button (P1-15CDD1, input 3)
  - INITIALIZE momentary button (P1-15CDD1, input 1)
  - START/SHUTDOWN momentary button (P1-15CDD1, input 2)
- Add debouncing logic for button inputs
- Implement state transition logic based on button presses

### 4. Update Visual Indicator Logic

- Modify relay assignments:
  - Green light: relay NO2
  - Amber light: relay NO3
  - Blue light: relay NO4
  - Red light: relay NO5
- Implement blinking patterns, reference the flowchart.md for pattern details:
  - Sequential blinking for self-check
  - Rapid flashing for initialization
  - Slow flashing for warm-up ramp
  - Steady lights for stable states
  - Error indication patterns

### 5. Enhance PID Controller

- Update PID parameters (KP=2.0, KI=0.1, KD=0.5, sample_time=0.5)
- Implement multiple setpoint handling for warm-up and full-temp modes
- Add controlled ramp rates for temperature transitions

### 6. Implement Safety Features

- Add over-current detection using P1-04AD readings
- Enhance error handling with specific error codes and messages
- Implement graceful shutdown procedures
- Add E-STOP handling logic that immediately disables outputs

### 7. Update Main Control Loop

- Restructure main loop around state machine
- Add state-specific processing functions
- Implement proper transitions between states based on conditions and inputs
- Add timing logic for state transitions and indicator patterns

### 8. Implement Self-Check Functionality

- Create diagnostics routine for checking modules
- Add sequential light pattern during initialization
- Implement validation of sensor readings
- Add error detection for missing or misconfigured components

### Implementation Strategy

1. Start by defining the state machine and core control flow
2. Update configuration code for all modules
3. Implement button detection and debouncing
4. Add visual indicator control logic
5. Enhance PID controller with multi-setpoint capability
6. Add safety features and error handling
7. Refactor main loop to use state machine
8. Test each state transition and condition

## Required Code Sections to Add or Modify

1. State machine enumeration and tracking variables
2. Button input handling functions
3. Visual indicator pattern functions
4. Enhanced PID controller with multiple setpoints
5. Current transformer reading and over-current detection
6. Self-check diagnostics routine
7. State-specific processing functions
8. Main loop restructuring for state machine

## Conclusion

The transition from the current implementation to the system described in the flowchart will require significant restructuring. The most fundamental change is moving from a simple linear control flow to a state-based architecture with multiple operational modes. Additionally, adding user interface elements (buttons) and enhancing the visual indicator system will require careful integration with the state machine logic.

