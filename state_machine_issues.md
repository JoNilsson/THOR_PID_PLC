# State Machine Implementation Issues Analysis

## Observed Behavior

According to the console log, after a reboot and without any button interactions, the system:

1. Started in IDLE state
2. Immediately transitioned to SYSTEM_ARMED (without button press)
3. Immediately transitioned to WARM_UP (without button press)
4. Immediately transitioned to SHUTDOWN
5. Finally transitioned back to IDLE
6. Remained in IDLE with blinking green light

This behavior indicates the state machine is not correctly handling button inputs and is auto-transitioning through states without the expected triggers.

## Root Causes of Issues

### 1. Button Event Processing Issues

The primary issue appears to be in the button event processing in the main loop:

```python
# Update button states and generate events
initialize_state = initialize_button.update()
start_state = start_button.update()

# Create button events when needed
if initialize_state == ButtonState.PRESSED:
    state_machine.process_event(Event(EventType.BUTTON_PRESSED, "INITIALIZE"))

if start_state == ButtonState.PRESSED:
    state_machine.process_event(Event(EventType.BUTTON_PRESSED, "START"))
```

#### Problem

- In the original Button class, the debouncing logic was designed to return `ButtonState.PRESSED` on the first read after a press, then immediately reset to `ButtonState.NOT_PRESSED` on subsequent reads
- In the refactored code, this means a button press is detected as PRESSED only for a single loop iteration
- However, we're creating a fully event-driven system now, which means the event is processed in the same iteration it's created

### 2. Unexpected Event Handling in State Handlers

```python
def _handle_system_armed(self, event):
    """Handle SYSTEM_ARMED state events"""
    if event is None:
        # No event, just regular update
        return

    if event.type == EventType.BUTTON_PRESSED:
        if event.data == "START":
            self.transition_to(SystemState.WARM_UP)
```

#### Problem

- In this new design, the START button in SYSTEM_ARMED state should transition to WARM_UP
- If the INITIALIZE button triggered a transition to SYSTEM_ARMED, and then immediately a START button is detected (erroneously), it would explain the immediate transition to WARM_UP

### 3. Initial Button State Reading Issues

- When the system starts up, the button inputs may not be in a known stable state
- The Button class could be misinterpreting the initial reading as a button press

### 4. Missing Self-Check State

The log shows the system going directly from IDLE to SYSTEM_ARMED, skipping the SELF_CHECK state:

```
Entering SYSTEM_ARMED state
```

#### Problem

- The self-check process seems to be bypassed, which is a critical safety feature

## Specific Code Issues

### 1. Button State Handling

```python
def update(self):
    # ... button logic ...
    # Reset to not pressed after processing the edge
    if self.current_state == ButtonState.PRESSED or self.current_state == ButtonState.RELEASED:
        self.current_state = ButtonState.NOT_PRESSED

    return self.current_state
```

The button implementation resets too quickly. For an event-driven system, we should track button state changes differently.

### 2. Event Processing Without Proper Guards

```python
# In the main loop
# Create button events when needed
if initialize_state == ButtonState.PRESSED:
    state_machine.process_event(Event(EventType.BUTTON_PRESSED, "INITIALIZE"))
```

There's no protection against falsely detected button presses during startup.

### 3. Missing State Handler Return Values

```python
def _handle_idle(self, event):
    """Handle IDLE state events"""
    if event is None:
        # No event, just regular update
        return

    if event.type == EventType.BUTTON_PRESSED:
        if event.data == "INITIALIZE":
            self.transition_to(SystemState.SYSTEM_ARMED)
```

State handlers don't return a value to indicate if they handled the event, so multiple handlers might try to process the same event.

## Recommendations for Fixes

### 1. Improve Button Debouncing

Modify the Button class to maintain state history and require multiple consistent readings:

```python
class Button:
    def __init__(self, digital_in, debounce_time=0.05, consistent_readings=3, is_normally_closed=True):
        self.digital_in = digital_in
        self.debounce_time = debounce_time
        self.consistent_readings = consistent_readings
        self.reading_history = [False] * consistent_readings
        self.last_change_time = time.monotonic()
        self.current_state = ButtonState.NOT_PRESSED
        self.previous_state = ButtonState.NOT_PRESSED
        self.is_normally_closed = is_normally_closed
```

### 2. Add Startup Guard Time

Add a startup delay before processing any button events:

```python
# At the start of the program
startup_time = time.monotonic()
startup_guard_time = 1.0  # 1 second startup guard

# In the main loop
if time.monotonic() - startup_time < startup_guard_time:
    # Skip button processing during startup
    pass
else:
    # Process buttons normally
```

### 3. Fix State Transitions

Ensure the state machine follows the correct transitions:

```python
def transition_to(self, new_state, record_history=True):
    # Add logging
    print(f"Attempting to transition from {SystemState.NAMES[self.current_state]} to {SystemState.NAMES[new_state]}")

    # Add validation logic
    if not self._is_valid_transition(self.current_state, new_state):
        print(f"Invalid state transition: {SystemState.NAMES[self.current_state]} -> {SystemState.NAMES[new_state]}")
        return False

    # Rest of transition logic
    # ...
```

### 4. Implement Proper Hierarchical State Machine

Define clear parent-child relationships for states and only allow specific transitions:

```python
# Define valid state transitions
VALID_TRANSITIONS = {
    SystemState.IDLE: [SystemState.SELF_CHECK],
    SystemState.SELF_CHECK: [SystemState.IDLE, SystemState.SYSTEM_ARMED, SystemState.ERROR],
    SystemState.SYSTEM_ARMED: [SystemState.WARM_UP, SystemState.IDLE, SystemState.ERROR],
    # ... other states ...
}

# All states can transition to ERROR
for state in VALID_TRANSITIONS:
    if SystemState.ERROR not in VALID_TRANSITIONS[state]:
        VALID_TRANSITIONS[state].append(SystemState.ERROR)
```

### 5. Adding More Debug Logging

Add comprehensive logging around state transitions and event processing:

```python
def process_event(self, event):
    """Process an event based on the current state"""
    print(f"Processing event: {event.type} - {event.data if event.data else 'No data'} in state {SystemState.NAMES[self.current_state]}")

    # Event handling logic
    # ...
```
