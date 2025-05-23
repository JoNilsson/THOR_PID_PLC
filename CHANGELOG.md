# THOR SiC Heater Control System Changelog

## May 22, 2025 - Network Interface Improvements and Documentation Updates

### Major Changes

1. **Zero-Configuration Peer-to-Peer Networking**
   
   - Implemented link-local addressing (169.254.100.100) for simple peer-to-peer connections
   - No router or DHCP server required - works with direct cable or unmanaged switch
   - Most operating systems automatically configure compatible addresses
   - Added fallback to static IP configuration for maximum compatibility

2. **Fixed Network Interface Issues**
   
   - Resolved "Wrong length for IPv4 address" error when accepting connections
   - Fixed "Operation timed out" errors by properly managing socket timeouts
   - Added validation to reject invalid connections (0.0.0.0:0)
   - Improved socket handling with proper blocking/non-blocking mode switching

3. **Added Real-Time Data Logging**
   
   - Implemented automatic CSV data streaming over telnet connection
   - Data updates every second with system telemetry
   - Enhanced timestamps with both elapsed seconds and human-readable HH:MM:SS format
   - Fixed blower status reporting to show actual running state

4. **Documentation Reorganization**
   
   - Created Docs directory for all technical documentation
   - Moved all markdown files (except README and CHANGELOG) to Docs/
   - Updated all links in README to point to new Docs/ locations
   - Simplified network setup instructions with focus on zero-configuration

5. **Serial Command Processing Fixes**
   
   - Fixed fragmented command handling (e.g., "S:OUTPUT" + "=5" arriving separately)
   - Added timeout protection for incomplete commands (2-second timeout)
   - Improved command parsing to wait for complete SET commands before processing
   - Fixed "invalid syntax for number" errors when commands arrive in chunks

### Technical Details

#### Network Configuration

- **Static IP**: 169.254.100.100 (link-local, zero-configuration)
- **Subnet**: 255.255.0.0 (standard link-local subnet)
- **Port**: 23 (telnet)
- **Fallback**: Can switch to DHCP by setting `USE_DHCP = True` in config.py

#### CSV Data Format

```csv
elapsed_time,hours:min:sec,state,temperature_F,blower_temp_F,current_A,output_mA,blower_status
120.5,00:02:00,WARM_UP,125.3,105.2,45.67,12.50,RUNNING
```

#### Code Changes

1. **network_interface.py**
   
   - Added link-local IP configuration (169.254.x.x)
   - Implemented periodic CSV data sending with 1-second interval
   - Added `_get_csv_data()` method to collect system telemetry
   - Fixed socket timeout handling for reliable data transmission
   - Added connection validation to reject invalid clients
   - Enhanced error handling with proper socket mode management

2. **config.py**
   
   - Added network configuration settings (USE_DHCP, STATIC_IP, etc.)
   - Set default to link-local addressing for peer-to-peer simplicity

3. **serial_interface.py**
   
   - Enhanced command completion detection for SET commands
   - Added timeout mechanism for stale partial commands
   - Improved buffer management to handle fragmented messages
   - Fixed parsing logic to ensure values are present before processing

4. **command_processor.py**
   
   - Fixed SET command parsing to use original command string
   - Added proper handling for OUTPUT= and OUTPUT_INCREMENT= commands

5. **Documentation Updates**
   
   - Created Docs/NETWORK_SETUP.md with simplified setup instructions
   - Updated README.md with concise network setup synopsis
   - Moved all technical docs to Docs/ directory for better organization

### Testing Results

- Peer-to-peer connection works without router using link-local addressing
- Data streams reliably at 1 Hz with proper CSV formatting
- Fragmented serial commands now process correctly
- Blower status accurately reflects actual hardware state
- Network timeouts resolved with improved socket management

## May 22, 2025 - RS-485 Communication Fixes and Memory Optimization

### Major Changes

1. **Fixed RS-485 Transmission Issues**

   - Resolved issue where RS-485 TX was not working despite RX functioning correctly
   - Added P1AM-SERIAL mode pin configuration (D3 set to LOW for RS-485 mode)
   - Improved DE pin timing for reliable transmit/receive switching
   - Added UART transmission delays to ensure data is fully sent before switching back to receive mode

2. **Hardware Configuration for RS-485**

   - Installed 120Ω termination resistors at both ends of the twisted pair
   - Properly grounded the cable shielding for noise immunity
   - These hardware changes were critical for reliable bidirectional communication

3. **Memory Allocation Fixes**

   - Fixed "memory allocation failed" errors when processing commands
   - Moved module imports out of function bodies to prevent repeated allocations
   - Replaced `isprintable()` with CircuitPython-compatible character checking
   - Optimized command processing to reduce memory fragmentation

4. **Command Processing Improvements**
   - Fixed command routing for G: (Get) commands like RS485 and MEM
   - Added memory diagnostic command (G:MEM) to monitor free memory
   - Simplified RS485 diagnostic command to avoid circular references

### Technical Details

#### RS-485 Configuration

- **TX Pin**: board.TX1 (hardware UART)
- **RX Pin**: board.RX1 (hardware UART)
- **DE Pin**: A6 (Data Enable for transmit/receive switching)
- **Mode Pin**: D3 (LOW = RS-485, HIGH = RS-232)
- **Termination**: 120Ω resistors at both ends of twisted pair
- **Shielding**: Cable shield connected to ground

#### Memory Optimization

- Removed repeated imports inside `process_command()` method
- Created `set_code_references()` static method to avoid circular imports
- Replaced string method `isprintable()` with `ord()` range checking
- Reduced debug output to minimize string allocations

#### Code Changes

1. **command_processor.py**

   - Added module-level placeholders for imported functions
   - Implemented `set_code_references()` to initialize imports after module load
   - Fixed command routing logic for G: commands
   - Replaced `isprintable()` with CircuitPython-compatible implementation

2. **serial_interface.py**

   - Added mode pin configuration for P1AM-SERIAL shield
   - Code clean-up and removal of debug outputs
   - Improved error handling for command processing

3. **rs485_wrapper.py**

   - Increased DE pin switching delays for reliability
   - Added transmission completion delays
   - Removed verbose debug output while keeping essential TX/RX logging

4. **code.py**
   - Added call to `set_code_references()` after CommandProcessor initialization
   - Reduced memory check frequency from 30 seconds to 5 minutes

### Testing Results

- RS-485 bidirectional communication verified working
- Commands properly processed without memory allocation errors
- System maintains ~88KB free memory during normal operation
- TX LED on P1AM-SERIAL shield properly indicates transmission
- Stable communication achieved with proper termination and shielding

## May 22, 2025 - Blower Monitor Hardware Migration and Safety Enhancements

### Major Changes

1. **Blower Monitor Hardware Migration**

   - Moved blower monitor input from GPIO pin D0 to P1-15CDD1 module input C1-4
   - Eliminates conflict with P1AM-SERIAL Port 2 TX- (D0) reservation
   - Ensures both serial ports remain available for future use

2. **Enhanced Safety for Blower Failures**

   - Blower failures now treated as critical errors (code 101) requiring manual reset
   - Cannot be cleared via software - requires physical intervention
   - Protects expensive heating elements from damage due to lack of cooling airflow

3. **Improved Error Broadcasting**
   - Critical errors now broadcast to all connected interfaces (RS-485 and TCP/IP)
   - Added `broadcast_critical_error()` method to CommandProcessor
   - Ensures all monitoring systems are immediately notified of critical failures

### Technical Details

#### Hardware Changes

- **Previous**: Blower monitor used GPIO pin D0 with digitalio
- **Current**: Uses P1-15CDD1 module input C1-4 (button_module.inputs[4])
- **Rationale**: D0 is reserved by P1AM-SERIAL for Port 2 TX-, creating a conflict

#### Code Changes

1. **config.py**

   - Removed `BLOWER_SENSOR_PIN` definition (no longer using GPIO pins)

2. **blower_monitor.py**

   - Updated to accept module input directly via `blower_monitor_input` parameter
   - Changed from GPIO pin reading to module input reading
   - Enhanced error messages to emphasize critical nature of blower failures

3. **code.py**

   - Added blower_monitor_input assignment from P1-15CDD1 module
   - Updated BlowerMonitor initialization with module input
   - Added critical error broadcasting on blower failure detection
   - Updated hardware configuration logging

4. **command_processor.py**
   - Added `serial_interface` reference
   - Added `broadcast_critical_error()` method for multi-interface alerts

#### Safety Response to Blower Failure

1. **Immediate Actions**:

   - SCR output drops to minimum (4.0 mA)
   - Red LED activates with ERROR_BLINK pattern (1 Hz)
   - System transitions to ERROR state

2. **Notifications**:

   - Console: "CRITICAL: Blower failure - airflow required for safe operation"
   - RS-485: "ERROR:CRITICAL ERROR [101]: Blower failure..."
   - TCP/IP: Critical error logged to connected clients

3. **Recovery**:
   - Requires manual system reset after physical resolution
   - INITIALIZE button will not clear blower errors
   - Prevents automatic recovery that could damage equipment

### Testing Results

- Blower monitor correctly detects circuit closure/opening
- LED indication on P1-15CDD1 module confirms signal reception
- Critical error handling prevents system operation without airflow
- All interfaces receive critical error notifications
- Manual reset requirement enforced as designed

## May 21, 2025 - RS-485 and Config System Improvements

### Major Changes

1. Unified Hardware Configuration

   - Removed `pin_manager.py` and consolidated all pin management into `config.py`
   - Made `config.py` the single source of truth for all hardware pins and feature flags
   - Added pin reservation system directly in `config.py` to prevent conflicts

2. Fixed RS-485 Communication Issues

   - Improved transmission timing in RS-485 wrapper
   - Enhanced error handling for more reliable communication
   - Added detailed debug logging to identify communication issues
   - Fixed buffer handling to prevent memory allocation failures
   - Added support for unterminated commands (missing CR/LF)

3. Memory Optimization

   - Reduced UART buffer size to prevent memory allocation failures
   - Added buffer size limits to prevent memory exhaustion
   - Implemented better error recovery mechanisms

4. Removed Unused Files
   - Cleaned up repository by removing unused diagnostic tools:
     - `pin_diagnostic.py`
     - `pin_diagnostics.py`
     - `pin_test.py`
     - `test_wiznet.py`
     - `pin_manager.py` (functionality moved to `config.py`)

### Technical Details

#### Pin Management Improvements

- Moved pin reservation system from `pin_manager.py` to `config.py` to create a single source of truth
- Updated all hardware interfaces to use pin definitions from `config.py`
- Ensured hardware enable/disable flags in `config.py` properly control interface initialization

#### RS-485 Communication Fixes

- Added dynamic timing calculations in `rs485_wrapper.py` based on message length and baud rate
- Increased delays before and after transmission to ensure reliable operation
- Implemented proper handling of the DE (Data Enable) pin for transmit/receive switching
- Added detailed logging of transmitted and received data for debugging
- Enhanced error handling to prevent crashes from malformed commands

#### Memory Optimization

- Reduced UART receiver buffer size from 256 to 128 bytes
- Added buffer overflow protection to prevent memory exhaustion
- Improved error handling around command processing to prevent crashes from malformed data
- Limited the number of bytes read at once to prevent buffer overflows

#### Command Processing Improvements

- Enhanced error handling in command processor to handle duplicate/concatenated commands
- Added guards against empty or very long commands
- Improved recovery from malformed commands to maintain system stability

### Implementation Rationale

These changes were implemented to address several issues observed in the system:

1. **Pin Conflicts**: Different components were attempting to use the same pins, leading to initialization failures. By centralizing pin definitions in `config.py`, we ensure consistent pin assignments across the system.

2. **RS-485 Communication Reliability**: The system was experiencing intermittent communication issues with the RS-485 interface. The timing improvements and enhanced error handling ensure more reliable data transmission and reception.

3. **Memory Allocation Failures**: The system was crashing with "memory allocation failed" errors when handling large buffers. By optimizing buffer sizes and adding overflow protection, we prevent these crashes.

4. **Code Organization**: Having multiple files with overlapping functionality created confusion and potential conflicts. By consolidating pin management into `config.py` and removing unused files, we've simplified the codebase and made it easier to maintain.

These improvements should result in a more stable and reliable system with better error handling and debugging capabilities.

