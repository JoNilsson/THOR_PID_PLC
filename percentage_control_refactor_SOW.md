# Statement of Work: Percentage-Based Control Refactor

## THOR SiC Heater Control System

**Date:** May 23, 2025  
**Author:** Johanness A. Nilsson for TERRAFORM INDUSTRIES  
**Project:** Implement a conversion of 4-20mA control values to percentage-based control (0-100%)

---

## Executive Summary

This SOW outlines the required changes to convert the THOR SiC Heater Control System from using raw 4-20mA values to a more intuitive percentage-based control system (0-100%). This change will affect the SCR output control, command interfaces, data logging, and user display throughout the system.

## Current Implementation Analysis

### 1. SCR Output Control

- **Location:** `code.py`
- **Current Range:** 4.0 to 20.0 mA
- **Module:** P1-04DAL-1 analog output module (Slot 4, Channel 1)
- **Variable:** `scr_output.real`
- **Scaling Constants:**
  - `MIN_COUNT = 819` (4mA)
  - `MAX_COUNT = 4095` (20mA)
  - `HEATING_THRESHOLD = 6.0` mA

### 2. PID Controller

- **Location:** `code.py` (lines 129-185)
- **Output Range:** `output_min=4`, `output_max=20`
- **Direct mapping:** PID output directly controls mA value

### 3. Command Interfaces

- **Serial Commands:** `S:OUTPUT=<value>`, `S:OUTPUT_INCREMENT=<value>`
- **Get Commands:** `G:OUTPUT` returns mA value
- **Manual Mode:** Direct manipulation of 4-20mA values

### 4. Data Logging

- **CSV Header:** `"elapsed_time,hours:min:sec,state,temperature_F,blower_temp_F,current_A,output_mA,blower_status"`
- **Network Interface:** Reports output as mA
- **Serial Interface:** Reports output as mA

### 5. Display and Reporting

- **Console Output:** Shows `<value>mA`
- **Status Messages:** Reference mA values
- **Error Thresholds:** Based on mA values

---

## Proposed Changes

### Phase 1: Core Infrastructure

#### 1.1 Create Conversion Utilities

**New File:** `output_utils.py`

```python
def mA_to_percent(mA_value):
    """Convert 4-20mA to 0-100%"""
    return ((mA_value - 4.0) / 16.0) * 100.0

def percent_to_mA(percent_value):
    """Convert 0-100% to 4-20mA"""
    return (percent_value / 100.0) * 16.0 + 4.0

def constrain_percent(percent):
    """Constrain percentage to 0-100 range"""
    return max(0.0, min(100.0, percent))
```

#### 1.2 Update Configuration Constants

**File:** `config.py`

- Add percentage-based constants
- Define conversion thresholds
- Maintain backward compatibility flags

### Phase 2: Control System Updates

#### 2.1 PID Controller Modification

**File:** `code.py`

- Change PID output range to 0-100
- Add conversion layer before writing to hardware
- Update internal calculations

#### 2.2 SCR Output Wrapper

Create abstraction layer for SCR output:

- Internal storage in percentage
- Automatic conversion to mA for hardware writes
- Property accessors for both percentage and mA values

### Phase 3: Command Interface Updates

#### 3.1 Command Processor Updates

**File:** `command_processor.py`

- Add new commands: `S:OUTPUT_PCT=<value>`, `S:OUTPUT_INCREMENT_PCT=<value>`
- Update `G:OUTPUT` to return percentage (with backward compatibility option)
- Add `G:OUTPUT_MA` for legacy mA value access
- Update command validation for percentage ranges

#### 3.2 Manual Mode Updates

- Accept percentage inputs
- Display percentage values
- Maintain safety constraints in percentage terms

### Phase 4: Logging and Display Updates

#### 4.1 Network Interface

**File:** `network_interface.py`

- Update CSV header: `output_pct` instead of `output_mA`
- Add configuration option for legacy format
- Update `_get_csv_data()` method

#### 4.2 Console Display

**File:** `code.py`

- Update status displays to show percentage
- Format: eg: `70.5%` instead of `15.3mA`
- Update all print statements and log messages

### Phase 5: Documentation and Testing

#### 5.1 Update Documentation

- Updates to Command reference guide
- new API documentation
- Documentation Updates

#### 5.2 Testing Requirements

- Unit tests for conversion functions
- Integration tests for command processing
- Hardware validation tests
- Backward compatibility tests

---

## Implementation Considerations

### Safety Considerations

1. **Minimum Output:** 0% = 4mA (maintains safe minimum)
2. **Maximum Output:** 100% = 20mA (prevents over-driving)
3. **Emergency Stop:** Sets to 0% (4mA)
4. **Heating Threshold:** Convert 6mA to percentage (12.5%)

### Backward Compatibility

1. **Legacy Commands:** Support both mA and percentage commands
2. **Configuration Flag:** `USE_PERCENTAGE_CONTROL = True`
3. **Dual Reporting:** Option to report both values

### Memory Constraints

- CircuitPython has limited memory
- Minimize new code additions
- Optimize conversion functions

---

## Affected Files Summary

### Core Files to Modify

1. `code.py` - Main control logic
2. `command_processor.py` - Command handling
3. `network_interface.py` - Network logging
4. `serial_interface.py` - Serial communication
5. `config.py` - Configuration constants

### New Files to Create

1. `output_utils.py` - Conversion utilities

### Documentation to Update

1. `README.md`
2. `Docs/serial-control.md`
3. `Docs/state_machine.md`
4. `CHANGELOG.md`

---

## Risk Assessment

### Low Risk

- Conversion calculations are straightforward
- Can be implemented incrementally
- Easy to test and validate

### Medium Risk

- Need clear documentation
- Potential for input errors if formats mixed

### Mitigation Strategies

1. Implement comprehensive input validation
2. Clear error messages distinguishing mA vs percentage

---

## Timeline Estimate

### Phase 1: Core Infrastructure (1 hour)

- Create conversion utilities
- Update configuration

### Phase 2: Control System (1-2 hours)

- PID controller updates
- SCR output wrapper

### Phase 3: Command Interface (1-2 hours)

- Command processor updates
- Backward compatibility

### Phase 4: Logging and Display (1-2 hours)

- Network interface updates
- Console display updates

### Phase 5: Documentation and Testing (1-2 hours)

- Documentation updates
- Testing and validation

**Total Estimated Time:** 6-9 hours

---

## Success Criteria

1. All percentage inputs correctly convert to 4-20mA hardware signals
2. All displays show percentage values clearly
3. Legacy commands continue to function
4. No loss of precision in control
5. Safety systems remain fully functional
6. Clear migration path for users

---

## Approval

This SOW requires DAC system lead approval before implementation begins. The phased approach allows for incremental development and testing while maintaining system stability.

