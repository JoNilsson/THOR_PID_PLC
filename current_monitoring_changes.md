# Current Monitoring System Upgrade

## Overview
This document summarizes the recent hardware and code changes made to the current monitoring system in the THOR SiC Heater Control System.

## Hardware Changes
- Previous configuration: Multiple separate current transformers for each phase
- New configuration: Single module that outputs a 4-20mA standard signal
- New module provides a pre-averaged value across all three phases
- Connections:
  - Positive: Channel 2 input on P1-04AD
  - Negative: Channel 10 com input on P1-04AD

## Code Changes
1. Simplified `read_current()` function:
   - Now reads from a single channel (Channel 2) instead of three separate channels
   - Directly converts 4-20mA signal to current value using proper scaling (4mA = 0A, 20mA = 100A)
   - Removed multi-phase averaging logic as this is now handled by the hardware

2. Added new diagnostics:
   - Signal integrity checks for the 4-20mA range
   - Issues a warning for potential open circuit (signal < 3.8mA) without triggering an error
   - Detects potential fault conditions (signal > 20.2mA)

3. Updated documentation:
   - Added detailed comments explaining the new hardware setup
   - Updated hardware configuration description
   - Updated code_updates.md with changelog

## Benefits
1. **Simplified Code**: Reduced code complexity by eliminating multi-phase monitoring and averaging
2. **Improved Reliability**: Standard 4-20mA industrial signal is more noise-resistant
3. **Better Diagnostics**: Added ability to detect signal integrity problems
4. **Standardization**: Using industry-standard signal protocol (4-20mA)

## Testing Notes
- The current range is set to low (100A) on the module
- System behavior should be monitored during initial deployment to verify scaling accuracy
- The overcurrent threshold (CURRENT_THRESHOLD = 180.0A) may need adjustment based on the new module's range

## Reference Documentation
- Original hardware refactoring plan: `ct_hardware_refactor.md`
- Product datasheet: https://cdn.automationdirect.com/static/specs/acuamp3act3actr.pdf
- Code changelog: `code_updates.md`