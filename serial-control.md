# Serial Control Interface Documentation

## Overview

The THOR SiC Heater Control System provides comprehensive remote control and monitoring capabilities through RS-485 serial and TCP/IP network interfaces. This dual-interface architecture enables both direct control operations and continuous data logging.

## System Architecture

### Interface Types

1. **RS-485 Serial Interface** (`serial_interface.py`)
   - Primary control interface for system commands
   - Bidirectional communication at 9600 baud
   - Uses P1AM-SERIAL shield Port 1
   - Supports both automatic and manual control modes

2. **TCP/IP Network Interface** (`network_interface.py`)
   - Read-only monitoring and data logging
   - Provides real-time CSV-formatted data stream
   - Uses P1AM-ETH shield on port 23
   - Continuous logging at 1-second intervals

### Command Processor (`command_processor.py`)

The central command processor handles all incoming commands from both interfaces:

- **Command Format**: `TYPE:COMMAND[:VALUE]`
- **Response Format**: `OK:message` or `ERROR:message`
- **Thread-safe**: Maintains system integrity across interfaces

## Control Modes

### Automatic Mode (Default)
- PID-based temperature control following programmed setpoints
- State machine manages heating profiles
- All safety interlocks active
- Commands limited to state transitions (INIT, START, STOP)

### Manual Mode
- Direct 4-20mA output control
- PID controller bypassed
- Safety systems remain active (E-STOP, blower monitoring)
- Full access to output manipulation commands

## Command Reference

### Control Commands (C:)
- `C:INIT` - Initialize system (automatic mode only)
- `C:START` - Start/advance heating cycle (automatic mode only)
- `C:MANUAL_MODE` - Enter manual control mode
- `C:AUTO_MODE` - Return to automatic mode
- `C:STOP` - Stop heating (works in both modes)

### Get Commands (G:)
- `G:TEMP` - Current heater temperature (°F)
- `G:BLOWER_TEMP` - Blower outlet temperature (°F)
- `G:STATE` - Current system state
- `G:CURRENT` - System current (A)
- `G:OUTPUT` - SCR output value (mA)
- `G:PID` - PID parameters (automatic mode only)
- `G:MEM` - Available memory (bytes)
- `G:RS485` - RS-485 interface status

### Set Commands (S:) - Manual Mode Only
- `S:OUTPUT=value` - Set output directly (4.0-20.0 mA)
- `S:OUTPUT_INCREMENT=value` - Adjust output by increment

## Data Logging Format

The TCP/IP interface streams CSV data with the following fields:
```
timestamp,state,temperature,blower_temp,current,output,blower_status
```

Example:
```
1234.5,WARM_UP,125.3,105.2,45.67,12.50,RUNNING
```

## Hardware Configuration

### RS-485 (P1AM-SERIAL Port 1)
- TX: board.TX1 (hardware UART)
- RX: board.RX1 (hardware UART)
- DE: A6 (Data Enable)
- Mode: D3 (LOW = RS-485)
- Termination: 120Ω resistors required at cable ends

### TCP/IP (P1AM-ETH)
- CS: D5 (Chip Select)
- Reset: D11
- DHCP enabled for automatic IP assignment
- Port: 23 (telnet)

## Safety Features

- Manual mode constrains output to 4-20mA range
- E-STOP remains active in all modes
- Blower monitoring cannot be bypassed
- Automatic fallback to safe state on communication loss
- All commands logged for audit trail