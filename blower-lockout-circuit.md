# Blower Lockout Circuit Implementation Strategy

_Author: Johanness Nilsson_  
Date May 20 2025

## Current Situation Analysis

The temperature control system for the THOR SiC Heater Control System currently lacks an explicit blower lockout mechanism that was previously implemented. This safety feature is critical for an automated configuration; as it prevents the system from initializing or starting heating cycles unless adequate airflow is present, detected via a current sensing SSR (Solid State Relay) on the blower load line. However, since the parameters of our tests have changed, and as a result we expect much lower RPM's on the blower, the SSR will need to be recalibrated if being implemented in tests that run the blower at lower RPM.

### Key Requirements

- Monitor GPIO Pin 14 for a sunk (LOW) signal
- The SSR circuit is normally open and closes when current is sensed on the blower load line. **NOTE:** The SSR is presently calibrated to energize, closing the circuit above 1200 RPM.
- Prevent system initialization/heating without confirmed airflow

## Current Error Handling System

The existing code implements robust error handling through. So as long as the operator is concious of the blower state, it should present no safety hazards. The code currently implements the following error systems;

1. **SafetyManager Class**: Centralizes all safety checks and error reporting
2. **Error State Handling**: Dedicated ERROR state in the state machine
3. **Self-Check Process**: Verifies system integrity before operation
4. **Current Monitoring**: Monitors heater current but not blower current

## Blower Lockout Implementation Strategy

There are two options for how this can be implemented as follows;

### Option 1: Direct Integration in code.py (Simpler Approach)

This approach modifies the `SafetyManager` class to directly incorporate blower monitoring:

1. **GPIO Pin Configuration**:

   - Configure GPIO Pin 14 as input, optionally with a 5k .5w pull-up resistor for added safety
   - This ensures HIGH signal when disconnected (no current)

2. **SafetyManager Enhancement**:

   - Add blower status check to the `update()` method
   - Prevent transitions to `SELF_CHECK`, `SYSTEM_ARMED`, or any heating states if blower signal isn't detected

3. **Implementation Details**:

   ```python
   # Add to SafetyManager.__init__
   self.blower_pin = board.GP14  # GPIO Pin 14
   self.blower_pin_io = digitalio.DigitalInOut(self.blower_pin)
   self.blower_pin_io.direction = digitalio.Direction.INPUT
   self.blower_pin_io.pull = digitalio.Pull.UP  # Pull-up, so LOW means current detected
   self.blower_status = False  # Track blower status

   # Add to SafetyManager.update method
   def check_blower(self):
       """
       Checks if blower is operating by reading current sensor SSR on GPIO Pin 14
       LOW signal (False) means current is detected and blower is running
       HIGH signal (True) means no current detected
       """
       # Invert signal since LOW means blower is running (SSR closed)
       return not self.blower_pin_io.value

   # In update method
   blower_status = self.check_blower()
   self.blower_status = blower_status

   # If blower not running but system in or transitioning to heating state
   if not blower_status and state_machine.current_state in [
       SystemState.SELF_CHECK, SystemState.SYSTEM_ARMED,
       SystemState.WARM_UP, SystemState.WARM_UP_COMPLETE,
       SystemState.FULL_TEMP, SystemState.FULL_TEMP_COMPLETE]:
           return False, self.set_error(101, "Blower not running - airflow required for operation")
   ```

4. **State Machine Enhancement**:
   - Modify state validation to prevent entering heating states without blower
   - Add a blower check to the self-check routine

### Option 2: Modular Approach (More Maintainable)

Creating a dedicated module to handle the blower lockout functionality would improve code maintainability and extend reuse of the functionality:

1. **Create a new module file** `blower_monitor.py`:

   ```python
   import board
   import digitalio
   import time

   class BlowerMonitor:
       """Monitors blower operation via current sensing SSR on GPIO Pin 14"""

       def __init__(self, required_states=None, error_callback=None):
           """
           Initialize blower monitoring

           Args:
               required_states: List of system states where blower must be running
               error_callback: Function to call when blower failure detected
           """
           self.blower_pin = board.GP14
           self.blower_input = digitalio.DigitalInOut(self.blower_pin)
           self.blower_input.direction = digitalio.Direction.INPUT
           self.blower_input.pull = digitalio.Pull.UP  # Pull-up, so LOW means current detected

           self.required_states = required_states or []
           self.error_callback = error_callback
           self.blower_status = False
           self.last_check_time = time.monotonic()
           self.check_interval = 0.5  # Check every 500ms by default

       def is_blower_running(self):
           """
           Check if blower is running based on current sensor
           Returns True if running, False if not
           """
           # LOW signal (False) means current detected (blower running)
           return not self.blower_input.value

       def check_blower(self, current_state):
           """
           Check if blower is running and required for current state

           Args:
               current_state: Current system state

           Returns:
               (is_safe, error_event) tuple - error_event will be None if no issues
           """
           current_time = time.monotonic()

           # Only check at specified intervals to avoid excessive polling
           if current_time - self.last_check_time < self.check_interval:
               return True, None

           self.last_check_time = current_time
           self.blower_status = self.is_blower_running()

           # Check if blower needs to be running in this state
           if current_state in self.required_states and not self.blower_status:
               if self.error_callback:
                   return False, self.error_callback(101, "Blower not running - airflow required for operation")
               return False, None

           return True, None
   ```

2. **Integration with code.py**:

   ```python
   from blower_monitor import BlowerMonitor

   # In initialization section
   blower_monitor = BlowerMonitor(
       required_states=[
           SystemState.SELF_CHECK,
           SystemState.SYSTEM_ARMED,
           SystemState.WARM_UP,
           SystemState.WARM_UP_COMPLETE,
           SystemState.FULL_TEMP,
           SystemState.FULL_TEMP_COMPLETE
       ],
       error_callback=safety_manager.set_error
   )

   # In the main loop, before state machine update
   is_blower_safe, blower_event = blower_monitor.check_blower(state_machine.current_state)
   if not is_blower_safe and blower_event:
       state_machine.process_event(blower_event)
   ```

## Implementation Action Items

1. **Hardware Connection**:

   - Confirm GPIO Pin 14 is connected with continuity to the current sensing SSR mounted in the ClearPath motor electrical enclosure
   - Verify SSR properly closes circuit when blower current is detected at specified RPM

2. **Add Required Imports**:

   - If using the modular approach, create the `blower_monitor.py` file
   - Add `import board` and `import digitalio` to access GPIO functionality

3. **Update SafetyManager or Add Module**:

   - Choose either the direct integration or modular approach
   - Implement the chosen approach with appropriate error codes and messaging

4. **Modify Self-Check Routine**:

   - Add blower check to the self-check diagnostic process
   - Update the self-check feedback to include blower status

5. **Update State Machine Logic**:

   - Ensure state transitions respect blower status
   - Add appropriate error recovery for blower-related errors

6. **Add Status Reporting**:
   - Update status reporting to include blower status
   - Include visual indicator for blower operation (perhaps using an existing LED pattern)

## Jo's Recommendations

The modular approach (Option 2) is recommended for the following reasons:

1. **Better Separation of Concerns**: Isolates blower monitoring from the main code
2. **Enhanced Maintainability**: Easier for me to update or modify blower monitoring logic
3. **Testability**: Can be tested independently of the main system
4. **Reusability**: Can be used in other systems that require similar monitoring

However, if simplicity is preferred and the codebase is not expected to grow significantly, the direct integration approach (Option 1) is a valid alternative that requires fewer files, and slightly less complexity.

## Testing Strategy

After implementation, test the blower lockout functionality by:

1. Simulating blower failure (disconnect or bypass the SSR) during each system state
2. Verify system enters ERROR state with appropriate error code
3. Test recovery by simulating blower restoration
4. Verify blower status is correctly reported in system logs
5. Test edge cases such as intermittent blower operation

## Conclusions

The blower lockout mechanism is a critical autonomous safety feature that ensures proper airflow before heating elements are engaged. By monitoring the current-sensing SSR on GPIO Pin 14, the system can verify blower operation and prevent potentially hazardous conditions. The proposed implementation strategies provide robust ways to incorporate this safety feature into the existing control system architecture.

