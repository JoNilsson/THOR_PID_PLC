# THOR SiC Heater Control System

## Overview

This project implements a sophisticated temperature control system for Terraform Industries' THOR Silicon Carbide (SiC) Heater arrays. The system uses a P1AM-200 PLC with multiple I/O modules to precisely control 12 silicon carbide heating elements through SCR (Silicon-Controlled Rectifier) units using 4-20mA control signals.

The control system employs a state machine architecture to manage the heating process through well-defined operational states from warm-up to full temperature operation, with comprehensive safety features and visual status indicators.

For a detailed visual representation of the control system operation, see the [flowchart](flowchart.md) and [state machine diagram](plc_operation_flowchart.mmd).

## Hardware Configuration

- **P1AM-200 PLC**: Main control unit
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

## Implementation Details

- Written in CircuitPython for the P1AM-200 PLC platform
- Comprehensive error handling with specific error codes
- Debug logging capabilities

## Technical Challenges and Solutions

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

### v1.3.0 (Current)

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

## Safety Considerations

- The system includes multiple safety features including:
  - Over-current protection
  - Over-temperature protection
  - Emergency stop functionality
  - Graceful shutdown procedures

## License

Proprietary - All rights reserved - © Terraform Industries 2025
