# Blower Monitor System Documentation

## Overview

The blower monitor system ensures adequate cooling airflow is present before allowing heating operations. This critical safety feature prevents damage to expensive silicon carbide heating elements by enforcing a hardware-verified airflow lockout.

## System Design

### Hardware Configuration

The blower monitor uses a current-sensing solid state relay (SSR) that detects when the blower motor is energized:

- **SSR Type**: Normally Open (NO) current sensor
- **Activation**: Closes circuit when blower current detected
- **Input**: P1-15CDD1 module input C1-4 (slot 5, input 4)
- **Signal Logic**: LOW (closed) = blower running, HIGH (open) = blower stopped

### Software Implementation

The `BlowerMonitor` class (`blower_monitor.py`) provides:

- Continuous monitoring of blower status via module input
- Integration with system state machine
- Critical error generation on blower failure
- Configurable monitoring intervals (default 500ms)

## Operational States

### States Requiring Blower Operation

The following system states require verified airflow:
- `SELF_CHECK` - System verification
- `SYSTEM_ARMED` - Ready for heating
- `WARM_UP` - Initial temperature ramp
- `WARM_UP_COMPLETE` - Maintaining warm-up temperature
- `FULL_TEMP` - Full temperature operation
- `FULL_TEMP_COMPLETE` - Maintaining full temperature

### Blower Failure Response

When blower failure is detected in a required state:

1. **Immediate Actions**:
   - SCR output drops to minimum (4.0 mA)
   - System transitions to ERROR state
   - Red LED activates with 1 Hz blink pattern

2. **Error Broadcasting**:
   - Console: "CRITICAL: Blower failure - airflow required for safe operation"
   - RS-485: Critical error message with code 101
   - TCP/IP: Error logged to all connected clients

3. **Recovery Requirements**:
   - Manual system reset required
   - Physical verification of blower operation
   - Cannot be cleared via software commands

## Integration Points

### State Machine Integration

The blower monitor is checked in the main control loop:
- Runs independently of control mode (auto/manual)
- Generates error events for state machine processing
- Maintains status flag for data logging

### Data Logging

Blower status is included in all data outputs:
- CSV logging shows "RUNNING" or "OFF"
- Status available via `G:STATE` command
- Included in periodic console status updates

## Configuration

### Module Initialization

```python
blower_monitor = BlowerMonitor(
    blower_monitor_input=button_module.inputs[4],  # P1-15CDD1 C1-4
    required_states=[...],                         # States requiring blower
    error_callback=safety_manager.set_error        # Error handler
)
```

### Enable/Disable

Controlled via `config.py`:
```python
ENABLE_BLOWER_MONITOR = True  # Set to False to disable
```

## Safety Considerations

- Blower monitoring cannot be bypassed in software
- Remains active during manual control mode
- Error code 101 is classified as critical (non-clearable)
- Designed for fail-safe operation (loss of signal = error)