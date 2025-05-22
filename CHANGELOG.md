# THOR SiC Heater Control System Changelog

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