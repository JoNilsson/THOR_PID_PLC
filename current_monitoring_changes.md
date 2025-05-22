# Current Monitoring System Documentation

## Overview

The THOR SiC Heater Control System monitors electrical current draw to ensure safe operation and detect fault conditions. The system uses an industrial 4-20mA current transducer module to provide real-time current measurements across all heating elements.

## Hardware Configuration

### Current Transducer Module
- **Type**: 4-20mA output current transformer module
- **Range**: 0-100A (low range setting)
- **Output**: 4mA = 0A, 20mA = 100A (linear)
- **Connection**: 
  - Positive: P1-04AD Channel 2 input
  - Negative: P1-04AD Channel 10 com input

### Signal Characteristics
- **Standard**: Industrial 4-20mA current loop
- **Resolution**: 0.00391A per bit (16-bit ADC)
- **Update Rate**: Continuous monitoring in main loop

## Software Implementation

### Current Reading Function

The `read_current()` function in `code.py`:
1. Reads raw value from P1-04AD Channel 2
2. Converts to 4-20mA signal value
3. Applies linear scaling to get actual current
4. Performs signal integrity checks

### Scaling Formula
```python
current = (mA_signal - 4.0) * (100.0 / 16.0)
```
Where:
- `mA_signal` is the measured 4-20mA value
- Result is current in amperes (0-100A range)

### Signal Integrity Monitoring

The system checks for:
- **Open Circuit**: Signal < 3.8mA (warning only)
- **Valid Range**: 3.8mA to 20.2mA
- **Fault Condition**: Signal > 20.2mA (returns None)

## Safety Features

### Overcurrent Protection
- **Threshold**: 70.0A (configurable in code)
- **Response**: Immediate transition to ERROR state
- **Error Code**: 102
- **Recovery**: Requires system reset

### Current Warnings
- **Range**: 60-70A generates console warnings
- **Purpose**: Alert operator before reaching trip point
- **Logging**: Warnings logged but don't trigger errors

## Data Access

### Console Display
- Shown in periodic status updates
- Format: "Current: XX.XXA"

### Remote Access
- **Command**: `G:CURRENT`
- **Response**: `CURRENT:XX.XX` or `ERROR:Current read failed`

### Data Logging
- Included in CSV stream via TCP/IP interface
- Updated every logging cycle
- Field name: `current`

## Calibration Notes

- Module must be configured for correct current range
- Scaling assumes 100A = 20mA (low range)
- Verify scaling accuracy during commissioning
- Consider load characteristics when setting thresholds

## Error Handling

Current monitoring errors are handled gracefully:
- Read failures return None (logged as "ERROR" in data)
- System continues operation unless overcurrent detected
- Signal integrity issues generate appropriate warnings
- All errors logged to console with timestamps