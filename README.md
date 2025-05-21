# THOR SiC Heater Control System

## Overview

This project implements a sophisticated temperature control system for Terraform Industries' THOR Silicon Carbide (SiC) Heater arrays. The system uses a P1AM-200 PLC with multiple I/O modules to precisely control 12 silicon carbide heating elements through SCR (Silicon-Controlled Rectifier) units using 4-20mA control signals.

The control system employs a state machine architecture to manage the heating process through well-defined operational states from warm-up to full temperature operation, with comprehensive safety features and visual status indicators.

For a detailed visual representation of the control system operation, see the [flowchart](flowchart.md) and [state machine diagram](plc_operation_flowchart.mmd).

## Hardware Configuration

- **P1AM-200 PLC**: Main control unit
- **P1AM-ETH**: Ethernet shield for TCP/IP communications
- **P1AM-SERIAL**: Serial interface shield for RS-485 communications
- **P1-04THM module** (Slot 1): K-type thermocouple temperature sensing
- **P1-04AD module** (Slot 2): Current monitoring via 4-20mA signal
- **P1-08TRS relay module** (Slot 3): Status indicators (green, amber, blue, red lights)
- **P1-04DAL-1 module** (Slot 4): SCR control via 4-20mA output
- **P1-15CDD1 digital I/O module** (Slot 5): Button inputs

## Operational Flow

1. System starts in `IDLE` state
2. `INITIALIZE` button initiates `SELF_CHECK` sequence
3. After successful check, system enters `SYSTEM_ARMED` state
4. `START` button begins `WARM_UP` phase to set temperature (100°F in test)
5. When warm-up complete, another `START` button press ramps to `FULL_TEMP` (150°F in test)
6. Pressing `START` during full temperature returns to warm-up or from warm-up initiates graceful shutdown
7. `E-STOP` button immediately halts all operations

## Key Features

- PID temperature control with [anti-windup](https://ocw.mit.edu/courses/16-30-feedback-control-systems-fall-2010/8c33eb306938cac6cd73e701a86a5b32_MIT16_30F10_lec23.pdf) protection
- State machine architecture with proper entry/exit actions
- Comprehensive safety monitoring and error handling
- Debounced physical button interface to avoid erroneous button interactions
- Visual status indication via LED indicator patterns
- Emergency stop functionality
- RS-485 serial control interface for remote operation
- TCP/IP network interface for data logging and monitoring
- Manual control mode for direct SCR output manipulation

## Implementation Details

- Written in CircuitPython for the P1AM-200 PLC platform
- Comprehensive error handling with specific error codes
- Debug logging capabilities
- Command processor architecture for handling multiple control interfaces
- Support for both automatic (PID-based) and manual control modes

## Technical Challenges and Solutions

### Serial Control and Manual Mode Implementation

**Challenge**: Adding remote control capabilities while maintaining safety and operational integrity

**Solution**:
- Implemented modular command processor architecture
- Created graceful degradation when hardware is unavailable
- Added safe state transitions between automatic and manual modes
- Maintained safety checks even during manual control
- Resolved circular import issues with local imports

For detailed information, see [serial-control.md](serial-control.md).

### Blower Monitoring and Lockout

**Challenge**: Ensuring proper airflow before allowing heating elements to operate

**Solution**:
- Added blower monitor module with lockout functionality
- Implemented current sensing-based blower verification
- Integrated blower status into system state machine
- Added blower status to data logging
- Provided detailed warning messages for blower issues

For detailed information, see [blower-lockout-circuit.md](blower-lockout-circuit.md).

### Current Monitoring Hardware Refactor

**Challenge**: Transitioning from multiple separate current transformers to a [single 4-20mA output module](https://cdn.automationdirect.com/static/manuals/acuampinserts/3act_3actr_installation.pdf)

**Solution**:
- Updated `read_current()` function to use Channel 2 of P1-04AD module
- Implemented proper scaling from 4-20mA signal to 0-100A values
- Added signal integrity diagnostic checks

For detailed information about this refactor, see [current_monitoring_changes.md](current_monitoring_changes.md) and [ct_hardware_refactor.md](ct_hardware_refactor.md).

### State Machine Implementation

**Challenge**: System auto-transitioning through states without expected button triggers  
**Solution**:

- Improved Button class with state history and debouncing
- Added startup guard time to delay button event processing
- Implemented state transition validation with parent-child relationships

For detailed information about state machine problems and solutions, see [state_machine_issues.md](state_machine_issues.md).

### Architecture Transition

**Challenge**: Moving from simple linear control flow to state-based architecture  
**Solution**:

- Created SystemState enumeration with eight distinct states
- Implemented state-specific processing functions
- Added proper state transition logic

### Safety Feature Implementation

**Challenge**: Required enhanced safety mechanisms beyond basic error handling  
**Solution**:

- Implemented over-current detection using P1-04AD readings
- Added specific error codes and messages
- Developed graceful shutdown procedures

## Changelog

### v1.4.0 (Current)

- Added RS-485 serial control interface
- Implemented TCP/IP network interface for data logging
- Added manual control mode for direct SCR output manipulation
- Enhanced blower monitoring with lockout functionality

### v1.3.0

- Refactored current transformer implementation
- Updated to use Channel 2 of P1-04AD module for current monitoring
- Improved error handling for current sensing

### v1.2.0

- Improved documentation and debugging capabilities
- Code cleanup and optimization
- Enhanced error reporting

### v1.1.0

- Second major refactoring of control system
- Implemented proper state machine with entry/exit actions
- Added debouncing logic for physical buttons

### v1.0.0

- Initial refactoring and state machine implementation
- Added comprehensive flowchart of system operation
- Implemented PID controller with multiple setpoints

## Requirements

- P1AM-200 PLC with CircuitPython support
- Required I/O modules (see Hardware Configuration)
- Silicon carbide heating elements with SCR controllers

## Usage

1. Load the code onto the P1AM-200 PLC
2. Connect all required hardware components
3. Follow the operational flow outlined above
4. Monitor system status via LED indicators

### Serial Control Interface (RS-485)

The system can be controlled remotely using the RS-485 interface. Here's how to set up and use it:

#### Hardware Setup

1. **Required Equipment**:
   - USB to RS-485 converter or RS-485 terminal device
   - Twisted pair cable (preferably shielded) for RS-485 communication
   - Terminal software on your computer (e.g., PuTTY, TeraTerm, or Serial Tool)

2. **Physical Connection**:
   - Connect the RS-485 A(+) wire to the A(+) terminal on the P1AM-SERIAL module
   - Connect the RS-485 B(-) wire to the B(-) terminal on the P1AM-SERIAL module
   - If available, connect the ground/shield wire to the GND terminal
   - For longer distances, ensure proper RS-485 termination (120Ω resistor across A and B on both ends)

3. **Terminal Software Configuration**:
   - Port: Select the COM port assigned to your USB-RS485 converter
   - Baud Rate: 9600
   - Data Bits: 8
   - Parity: None
   - Stop Bits: 1
   - Flow Control: None
   - Local Echo: On (recommended)
   - Line Ending: CR+LF (for sending commands)

#### Using the Serial Interface

1. **Connection Test**:
   - After connecting, you should see "THOR SiC Heater Control System" and "RS-485 Control Interface Ready" messages
   - If no message appears, press Enter to see if the system responds

2. **Command Format**:
   All commands use this format: `TYPE:COMMAND[:VALUE]` followed by Enter key
   
   - **Control Commands (C:)**:
     - `C:INIT` - Initialize the system
     - `C:START` - Start/advance the heating cycle
     - `C:MANUAL_MODE` - Enter manual control mode
     - `C:AUTO_MODE` - Return to automatic control mode
     - `C:STOP` - Stop heating and begin shutdown
   
   - **Get Commands (G:)**:
     - `G:TEMP` - Read current temperature
     - `G:STATE` - Get current system state
     - `G:CURRENT` - Read heater current
     - `G:OUTPUT` - Read SCR output (4-20mA)
     - `G:PID` - Get PID controller parameters
   
   - **Set Commands (S:)** (only in manual mode):
     - `S:OUTPUT=12.5` - Set SCR output directly (4.0-20.0 mA)
     - `S:OUTPUT_INCREMENT=0.5` - Increase output by specified amount

3. **Response Format**:
   - Success: `OK:message` or value-specific response like `TEMP:145.2`
   - Error: `ERROR:message` with specific error information

### TCP/IP Data Logging Interface

The system provides data logging and read-only monitoring via Ethernet. Here's how to set up and use it:

#### Hardware Setup

1. **Required Equipment**:
   - Ethernet cable (CAT5e or better)
   - Network switch or router with DHCP enabled
   - Computer on the same network
   - Terminal software with telnet capability (e.g., PuTTY, TeraTerm, or NetCat)

2. **Physical Connection**:
   - Connect an Ethernet cable from the P1AM-ETH module to your network switch/router
   - Ensure the P1AM-ETH module's status LEDs show proper link status
   - The system will automatically acquire an IP address via DHCP

3. **Finding the System IP Address**:
   - The IP address is displayed on the serial console during startup
   - If you can't access the console, check your router's DHCP client list
   - Alternatively, use an IP scanner tool to locate the device on your network

#### Connecting to the Data Logging Interface

1. **Terminal Software Configuration**:
   - Connection type: Telnet (raw TCP)
   - Host: The IP address acquired by the system (e.g., 192.168.1.100)
   - Port: 23 (standard telnet port)
   - Local Echo: On (recommended)

2. **Connection Test**:
   - After connecting, you should see "THOR SiC Heater Control System - Data Logging Interface"
   - The system will then send a CSV header line
   - Data will begin streaming automatically in CSV format

3. **Data Format**:
   - CSV format with header: `timestamp,state,temperature,current,output,blower_status`
   - Example: `1234.5,WARM_UP,125.3,45.67,12.50,RUNNING`
   - Data updated at approximately 1-second intervals

4. **Available Commands**:
   - The network interface accepts read-only commands (G: prefix only)
   - Example: `G:TEMP` will return the current temperature
   - Write operations and control commands are not accepted for safety reasons

### Manual Control Mode

The system supports a manual control mode for direct SCR output manipulation without PID control:

#### Entering and Exiting Manual Mode

1. **Enter Manual Mode**:
   - Send `C:MANUAL_MODE` command via RS-485
   - System will respond with `OK:Manual control mode enabled`
   - SCR output will be set to minimum (4.0 mA)
   - LED indicators will show amber and blue alternating pattern
   - System state will report as `MANUAL_CONTROL`

2. **Exit Manual Mode**:
   - Send `C:AUTO_MODE` command via RS-485
   - System will respond with `OK:Automatic control mode enabled`
   - Control will return to the automatic PID-based state machine
   - System will transition to IDLE state for safety

#### Controlling the SCR Output Manually

1. **Setting Absolute Output Value**:
   - Command: `S:OUTPUT=value`
   - Value must be between 4.0 and 20.0 mA
   - Example: `S:OUTPUT=12.5` sets the SCR to 12.5 mA output
   - System will respond with `OK:Output set to 12.50mA`

2. **Incrementing Output Value**:
   - Command: `S:OUTPUT_INCREMENT=value`
   - Value can be positive or negative
   - Example: `S:OUTPUT_INCREMENT=0.5` increases output by 0.5 mA
   - Example: `S:OUTPUT_INCREMENT=-1.0` decreases output by 1.0 mA
   - System will respond with `OK:Output incremented to 13.00mA`

3. **Monitoring During Manual Mode**:
   - Use `G:` commands to monitor system values
   - Example: `G:TEMP` returns current temperature
   - Example: `G:OUTPUT` returns current SCR output
   - Data logging via TCP/IP continues during manual mode

#### Safety Considerations for Manual Mode

- E-STOP button remains active during manual mode
- Blower monitoring remains active during manual mode
- SCR output is constrained to valid 4-20mA range
- System will log all manual actions via the TCP/IP interface
- Upon exiting manual mode, SCR output is automatically set to minimum

## Safety Considerations

- The system includes multiple safety features including:
  - Over-current protection
  - Over-temperature protection
  - Emergency stop functionality
  - Graceful shutdown procedures
  - Blower monitoring and lockout
  - Safety-constrained manual mode
  - Read-only network monitoring
  - Automatic fallback modes when hardware is unavailable

## License

Proprietary - All rights reserved - © Terraform Industries 2025
