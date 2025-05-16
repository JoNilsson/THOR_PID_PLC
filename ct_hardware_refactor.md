# Current Transformer Hardware Refactor Action Plan

## Overview

This document outlines the action plan for implementing changes to the current monitoring system. The hardware has been upgraded from multiple current transformers to a module that outputs a standard 4-20mA signal representing the average current across the three phases of the THOR heater elements.

## Hardware Changes Summary

1. **Previous configuration**: Multiple independent current transformers monitoring each phase
2. **New configuration**: Single module providing averaged 4-20mA output signal
   - Positive connection: Channel 2 input on P1-04AD
   - Negative connection: Channel 10 com input on P1-04AD
3. **Datasheet**: <https://cdn.automationdirect.com/static/specs/acuamp3act3actr.pdf>

## Technical Implications

- **Signal type change**: Moving from CT output to standardized 4-20mA industrial signal
- **Averaging**: New module provides a pre-averaged value across all three phases
- **Signal range**: Standard 4-20mA range where:
  - 4mA typically represents 0 or minimum value
  - 20mA typically represents maximum scale value

## Code Refactoring Requirements

1. **Input handling**: Update code to read from Channel 2 on the P1-04AD module
2. **Scaling**: Implement proper scaling for 4-20mA signal to actual current values
   - Current range is presently set to low (100A) that corresponds to 4-20mA
3. **Simplification**: Remove any code related to individual phase monitoring and averaging
4. **Diagnostics**: Add diagnostic checks (signal < 4mA or > 20mA indicates fault condition)

## Implementation Steps

1. Create backup of existing code.py
2. Identify all current transformer related code sections
3. Modify input reading functions to use Channel 2 on P1-04AD
4. Implement 4-20mA scaling to actual current values
5. Remove obsolete multi-phase monitoring code
6. Add diagnostic checks for signal integrity
7. Document changes in code comments and change-log documentation

## Next Steps

Proceed with code.py modifications following this action plan.

