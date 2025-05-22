# State Machine Architecture Documentation

## Overview

The THOR SiC Heater Control System implements a finite state machine architecture to manage the heating process through well-defined operational states. This design ensures predictable behavior, safe transitions, and comprehensive error handling.

## State Definitions

### System States

1. **IDLE** - System powered but inactive

   - Green LED: Slow blink
   - SCR Output: 4.0 mA (minimum)
   - Waiting for INITIALIZE button

2. **SELF_CHECK** - System verification in progress

   - Green LED: Fast blink
   - Verifies all hardware components
   - Checks blower operation

3. **SYSTEM_ARMED** - Ready to begin heating

   - Green LED: Solid on
   - All checks passed
   - Waiting for START button

4. **WARM_UP** - Initial temperature ramp

   - Green LED: On, Amber LED: Slow blink
   - PID Setpoint: (configurable)
   - Active temperature control

5. **WARM_UP_COMPLETE** - Warm-up temperature achieved

   - Green LED: On, Amber LED: On
   - Maintaining warm-up setpoint
   - Waiting for START to advance

6. **FULL_TEMP** - Full temperature operation

   - Green LED: On, Blue LED: Slow blink
   - PID Setpoint: (configurable)
   - Maximum heating mode

7. **FULL_TEMP_COMPLETE** - Full temperature achieved

   - Green LED: On, Blue LED: On
   - Maintaining full temperature
   - Production ready state

8. **ERROR** - Fault condition active

   - Red LED: Error blink (1 Hz)
   - SCR Output: 4.0 mA (safe)
   - Requires intervention

9. **SHUTDOWN** - Controlled shutdown sequence
   - Previous LEDs: Fast blink
   - SCR Output: Gradual reduction
   - Cooling down safely

## State Transitions

### Valid Transition Map

```
IDLE → SELF_CHECK → SYSTEM_ARMED → WARM_UP → WARM_UP_COMPLETE → FULL_TEMP → FULL_TEMP_COMPLETE → SHUTDOWN → IDLE
```

Additional transitions:

- Any state → ERROR (on fault condition)
- ERROR → IDLE (after error cleared)
- WARM_UP/FULL_TEMP → SHUTDOWN (via START button)

### Transition Triggers

1. **Button Events**:

   - INITIALIZE: IDLE → SELF_CHECK
   - START: Advances through heating states or initiates shutdown

2. **Temperature Events**:

   - TEMP_REACHED: Automatically advances when setpoint achieved

3. **Error Events**:
   - ERROR_OCCURRED: Any state → ERROR
   - ESTOP_ACTIVATED: Any state → ERROR
   - ESTOP_CLEARED: Clears E-STOP error only

## Implementation Details

### State Machine Class

The `StateMachine` class manages:

- Current state tracking
- Transition validation
- State-specific handlers
- Entry/exit actions
- Event processing

### Event System

Events carry:

- **Type**: EventType enumeration
- **Data**: Optional payload (e.g., error codes)

### State Handlers

Each state has a dedicated handler method:

```python
def _handle_<state_name>(self, event):
    # Process state-specific events
    # Return True if event was handled
```

## Button Interface

### Button Class Features

- Hardware debouncing (50ms default)
- State tracking (pressed/not pressed/released)
- Event generation on state changes
- Support for normally-closed (NC) and normally-open (NO) buttons

### Button Configuration

- **Initialize**: NC button on P1-15CDD1 input 1
- **Start**: NC button on P1-15CDD1 input 2
- **E-STOP**: NO button on P1-15CDD1 input 3

### Startup Protection

- 2-second guard time after boot
- Prevents spurious events during initialization
- Ensures clean state machine startup

## Safety Features

### Error Handling

- Immediate SCR shutdown on any error
- State history tracking for diagnostics
- Error codes for specific fault types

### Critical Errors

- Code 100: E-STOP activated
- Code 101: Blower failure
- Code 102: Overcurrent condition

### State Validation

- Only valid transitions allowed
- Invalid requests logged but ignored
- System remains in safe state

## Integration Points

### PID Controller

- Setpoint updates on state entry
- Active only in heating states
- Output constrained to 4-20mA range

### LED Manager

- Automatic pattern updates per state
- Visual system status indication
- Error state override capability

### Safety Manager

- Continuous monitoring in all states
- Error event generation
- E-STOP handling priority

