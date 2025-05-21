# THOR Serial Control and Data Logging Implementation Plan

_Engineer: Johanness Nilsson Terraform Industries_  
_Date: May 20, 2025_

## Overview

This document outlines a rapid implementation strategy for an agnostic serial console to provide control capabilities and enhanced data logging for the THOR SiC Heater Control System. The implementation will leverage the existing P1AM-SERIAL and P1AM-ETH shields to create a flexible interface for system control and monitoring.

## Implementation Approach

### Hybrid Approach

Leveraging both serial and network capabilities, with a focus on quick deployment:

1. **Serial Interface (RS-485)**: Primary control interface for issuing commands and starting/stopping the unit
2. **Network Interface (TCP/IP)**: Monitoring and verbose data logging interface in CSV format

## Manual Control Mode

When under serial control, the system will operate in a simplified manual control mode:
- PID heating profiles will be disabled
- Direct manipulation of the 4-20mA SCR control signal
- Physical E-STOP button remains functional for emergency shutdown
- Verbose logging to TCP/IP interface in CSV format

## Core Components

### 1. Command Processor and Manual Control Mode

Create a command handler with manual mode support:

```python
# command_processor.py
class CommandProcessor:
    def __init__(self, state_machine, safety_manager, pid_controller, scr_output):
        self.state_machine = state_machine
        self.safety_manager = safety_manager
        self.pid_controller = pid_controller
        self.scr_output = scr_output
        self.manual_mode = False
        self.network_interface = None  # Will be set after initialization
        
    def set_network_interface(self, network_interface):
        """Set reference to network interface for logging"""
        self.network_interface = network_interface
        
    def process_command(self, cmd_str):
        """Process incoming command string and return response"""
        parts = cmd_str.strip().split(":")
        if len(parts) < 2:
            return "ERROR:Invalid command format"
            
        cmd_type = parts[0].upper()
        cmd = parts[1].upper()
        
        # System control commands
        if cmd_type == "C":  # Control commands
            if cmd == "INIT":
                if not self.manual_mode:
                    self.state_machine.process_event(Event(EventType.BUTTON_PRESSED, "INITIALIZE"))
                    return "OK:System initializing"
                else:
                    return "ERROR:Not available in manual mode"
                    
            elif cmd == "START":
                if not self.manual_mode:
                    self.state_machine.process_event(Event(EventType.BUTTON_PRESSED, "START"))
                    return "OK:Start command processed"
                else:
                    return "ERROR:Not available in manual mode"
                    
            elif cmd == "MANUAL_MODE":
                # Switch to manual control mode
                self._enter_manual_mode()
                return "OK:Manual control mode enabled"
                
            elif cmd == "AUTO_MODE":
                # Switch back to automatic PID control mode
                self._exit_manual_mode()
                return "OK:Automatic control mode enabled"
                
            elif cmd == "STOP":
                # Stop heating in either mode
                if self.manual_mode:
                    self.scr_output.real = 4.0  # Minimum output
                    return "OK:Manual heating stopped"
                else:
                    self.state_machine.transition_to(SystemState.SHUTDOWN)
                    return "OK:System shutdown initiated"
                
        # Get commands
        elif cmd_type == "G":  # Get commands
            if cmd == "TEMP":
                temp = read_temperature(self.safety_manager)
                return f"TEMP:{temp:.1f}" if temp is not None else "ERROR:Temp read failed"
                
            elif cmd == "STATE":
                if self.manual_mode:
                    return "STATE:MANUAL_CONTROL"
                else:
                    return f"STATE:{SystemState.NAMES[self.state_machine.current_state]}"
                    
            elif cmd == "CURRENT":
                current = read_current(self.safety_manager)
                return f"CURRENT:{current:.2f}" if current is not None else "ERROR:Current read failed"
                
            elif cmd == "OUTPUT":
                return f"OUTPUT:{self.scr_output.real:.2f}"
                
        # Set commands
        elif cmd_type == "S":  # Set commands
            if cmd.startswith("OUTPUT="):
                if self.manual_mode:
                    try:
                        output = float(cmd.split("=")[1])
                        # Constrain to valid 4-20mA range
                        output = max(4.0, min(20.0, output))
                        self.scr_output.real = output
                        self._log_manual_action(f"Output set to {output:.2f}mA")
                        return f"OK:Output set to {output:.2f}mA"
                    except (ValueError, IndexError):
                        return "ERROR:Invalid output value"
                else:
                    return "ERROR:Manual mode required for direct output control"
                    
            elif cmd.startswith("OUTPUT_INCREMENT="):
                if self.manual_mode:
                    try:
                        increment = float(cmd.split("=")[1])
                        new_output = self.scr_output.real + increment
                        # Constrain to valid 4-20mA range
                        new_output = max(4.0, min(20.0, new_output))
                        self.scr_output.real = new_output
                        self._log_manual_action(f"Output incremented to {new_output:.2f}mA")
                        return f"OK:Output incremented to {new_output:.2f}mA"
                    except (ValueError, IndexError):
                        return "ERROR:Invalid increment value"
                else:
                    return "ERROR:Manual mode required for direct output control"
                
        return "ERROR:Unknown command"
        
    def _enter_manual_mode(self):
        """Enter manual control mode"""
        self.manual_mode = True
        # Save the current state to return to later
        self.previous_state = self.state_machine.current_state
        # Set minimum output for safety
        self.scr_output.real = 4.0
        self._log_manual_action("Manual mode enabled")
        
    def _exit_manual_mode(self):
        """Exit manual control mode"""
        if self.manual_mode:
            self.manual_mode = False
            # Set minimum output before returning to automatic control
            self.scr_output.real = 4.0
            self._log_manual_action("Manual mode disabled")
            # Transition to IDLE state for safety
            self.state_machine.transition_to(SystemState.IDLE)
            
    def _log_manual_action(self, message):
        """Log manual control actions"""
        if self.network_interface:
            temp = read_temperature(self.safety_manager)
            current = read_current(self.safety_manager)
            temp_str = f"{temp:.1f}" if temp is not None else "ERROR"
            curr_str = f"{current:.2f}" if current is not None else "ERROR"
            
            log_message = f"MANUAL,{time.monotonic():.1f},{message},{temp_str},{curr_str},{self.scr_output.real:.2f}"
            self.network_interface.log_message(log_message)
            
    def update(self):
        """Periodic update for logging in manual mode"""
        if self.manual_mode and self.network_interface:
            temp = read_temperature(self.safety_manager)
            current = read_current(self.safety_manager)
            blower_status = "RUNNING" if blower_monitor.blower_status else "OFF"
            
            # Create CSV formatted log entry
            timestamp = time.monotonic()
            temp_str = f"{temp:.1f}" if temp is not None else "ERROR"
            curr_str = f"{current:.2f}" if current is not None else "ERROR"
            
            log_entry = f"{timestamp:.1f},MANUAL_CONTROL,{temp_str},{curr_str},{self.scr_output.real:.2f},{blower_status}"
            self.network_interface.log_message(log_entry)
```

### 2. RS-485 Serial Interface

Implement a serial interface focused on control commands:

```python
# serial_interface.py
import busio
import board
from rs485_wrapper import RS485

class SerialInterface:
    def __init__(self, command_processor, tx_pin, rx_pin, de_pin, baudrate=9600):
        uart = busio.UART(tx_pin, rx_pin, baudrate=baudrate)
        self.rs485 = RS485(uart, de_pin)
        self.command_processor = command_processor
        self.buffer = ""
        
    def update(self):
        """Check for commands and process them"""
        if self.rs485.in_waiting:
            data = self.rs485.read(self.rs485.in_waiting)
            if data:
                try:
                    text = data.decode('utf-8')
                    self.buffer += text
                    if '\r' in self.buffer or '\n' in self.buffer:
                        lines = self.buffer.splitlines()
                        self.buffer = lines[-1]  # Keep incomplete line
                        
                        for line in lines[:-1]:  # Process complete lines
                            if line.strip():
                                response = self.command_processor.process_command(line)
                                self.rs485.write((response + '\r\n').encode('utf-8'))
                except UnicodeError:
                    self.buffer = ""  # Clear buffer on error
```

### 3. TCP/IP Network Interface for Logging

Enhanced network interface focused on data logging:

```python
# network_interface.py
import board
import busio
import digitalio
import adafruit_wiznet5k as wiznet
from adafruit_wiznet5k.adafruit_wiznet5k_socket import socket

class NetworkInterface:
    def __init__(self, command_processor, cs_pin, reset_pin, port=23):
        # Initialize Ethernet
        spi = busio.SPI(board.SCK, MOSI=board.MOSI, MISO=board.MISO)
        cs = digitalio.DigitalInOut(cs_pin)
        reset = digitalio.DigitalInOut(reset_pin)
        
        # Initialize Ethernet interface
        self.eth = wiznet.WIZNET5K(spi, cs, reset)
        # Use DHCP for automatic IP configuration
        self.eth.dhcp = True
        
        # Create socket server
        self.server_socket = socket(self.eth)
        self.server_socket.bind((0, port))
        self.server_socket.listen(1)
        
        self.command_processor = command_processor
        self.client = None
        self.client_buffer = ""
        
        # Set reference in command processor for logging
        self.command_processor.set_network_interface(self)
        
        # CSV header
        self.csv_header = "timestamp,state,temperature,current,output,blower_status"
        
    def update(self):
        """Handle network connections and logging"""
        # Accept new connections
        if self.client is None:
            try:
                self.client, addr = self.server_socket.accept()
                print(f"Network client connected from {addr}")
                self.client.send(b"THOR SiC Heater Control System - Data Logging Interface\r\n")
                self.client.send(f"{self.csv_header}\r\n".encode('utf-8'))
            except OSError:
                pass  # No connection available
                
        # Process read-only monitoring commands if needed
        if self.client:
            try:
                if self.client.available():
                    # Only handle basic monitoring commands
                    data = self.client.recv(256)
                    if data:
                        text = data.decode('utf-8')
                        self.client_buffer += text
                        if '\r' in self.client_buffer or '\n' in self.client_buffer:
                            lines = self.client_buffer.splitlines()
                            self.client_buffer = lines[-1]  # Keep incomplete line
                            
                            for line in lines[:-1]:  # Process complete lines
                                if line.strip():
                                    # Only allow read-only commands on network interface
                                    if line.upper().startswith("G:"):
                                        response = self.command_processor.process_command(line)
                                        self.client.send((response + '\r\n').encode('utf-8'))
                                    else:
                                        self.client.send(b"ERROR:Network interface is read-only\r\n")
            except OSError:
                print("Client disconnected")
                self.client = None
                self.client_buffer = ""
                
    def log_message(self, message):
        """Send a log message to the connected client"""
        if self.client:
            try:
                self.client.send((message + '\r\n').encode('utf-8'))
            except OSError:
                # Client disconnected
                self.client = None
```

### 4. Integration into Main Loop

Modify the main loop to handle the manual control mode:

```python
# Add imports
from command_processor import CommandProcessor
from serial_interface import SerialInterface
from network_interface import NetworkInterface

# Initialize interfaces after other components are set up
command_processor = CommandProcessor(state_machine, safety_manager, pid, scr_output)
serial_interface = SerialInterface(command_processor, board.TX, board.RX, board.D13)
network_interface = NetworkInterface(command_processor, board.D4, board.D5)

# In the main loop, add:
while True:
    try:
        # Update button states (keep E-STOP functionality)
        initialize_state = initialize_button.update()
        start_state = start_button.update()

        # Apply startup guard time - don't process button events during startup
        current_time = time.monotonic()
        if current_time - startup_time > STARTUP_GUARD_TIME:
            # Check for and process button events - only when not in manual mode
            if not command_processor.manual_mode:
                if initialize_button.get_event_and_clear():
                    print("INITIALIZE button pressed")
                    state_machine.process_event(Event(EventType.BUTTON_PRESSED, "INITIALIZE"))

                if start_button.get_event_and_clear():
                    print("START button pressed")
                    state_machine.process_event(Event(EventType.BUTTON_PRESSED, "START"))

        # Check blower status - keep safety features operational
        is_blower_safe, blower_event = blower_monitor.check_blower(state_machine.current_state)
        if not is_blower_safe and blower_event:
            state_machine.process_event(blower_event)

        # Update interfaces
        serial_interface.update()
        network_interface.update()
        
        # Only update state machine if not in manual mode
        if not command_processor.manual_mode:
            state_machine.update()
            led_manager.update()
        else:
            # In manual mode, update command processor for logging
            command_processor.update()

        # Read sensors for status reporting
        current_temp = read_temperature(safety_manager)
        current_reading = read_current(safety_manager)

        # Print status periodically - in both modes
        if current_time - last_print_time >= print_interval:
            # Format temperature and current readings
            temp_str = f"{current_temp:.1f}°F" if current_temp is not None else "ERROR"
            curr_str = f"{current_reading:.2f}A" if current_reading is not None else "ERROR"

            # Status strings
            if command_processor.manual_mode:
                state_str = "MANUAL_CONTROL"
            else:
                state_str = SystemState.NAMES[state_machine.current_state]
                
            output_str = f"{scr_output.real:.2f}mA"

            # E-STOP status
            estop_status = "ACTIVATED" if safety_manager.check_estop() else "NORMAL"

            # Blower status
            blower_status = "RUNNING" if blower_monitor.blower_status else "OFF"

            print(f"State: {state_str} | E-STOP: {estop_status} | Blower: {blower_status} | Temp: {temp_str} | Current: {curr_str} | Output: {output_str}")

            last_print_time = current_time

    except Exception as e:
        # Unexpected error - ensure safety
        safety_manager.set_error(999, f"Unhandled exception: {e}")
        # In manual mode, reset to minimal output
        if command_processor.manual_mode:
            scr_output.real = 4.0
            command_processor.manual_mode = False
        # Otherwise transition to error state
        else:
            state_machine.transition_to(SystemState.ERROR)
        # Reset outputs to safe state
        scr_output.real = 4.0  # Minimum control signal

    # Small delay to prevent CPU hogging
    time.sleep(0.01)
```

## Manual Control Command Set

| Command | Description | Example |
|---------|-------------|---------|
| C:MANUAL_MODE | Enter manual control mode | `C:MANUAL_MODE` |
| C:AUTO_MODE | Return to automatic mode | `C:AUTO_MODE` |
| C:STOP | Stop heating (in either mode) | `C:STOP` |
| S:OUTPUT=x | Set SCR output to x mA (4-20) | `S:OUTPUT=10.5` |
| S:OUTPUT_INCREMENT=x | Change output by x mA | `S:OUTPUT_INCREMENT=0.5` |
| G:TEMP | Get current temperature | `G:TEMP` |
| G:CURRENT | Get current reading | `G:CURRENT` |
| G:OUTPUT | Get current SCR output level | `G:OUTPUT` |
| G:STATE | Get current control mode | `G:STATE` |

## TCP/IP Logging Format

The TCP/IP interface will output CSV-formatted data in real-time with the following columns:

```
timestamp,state,temperature,current,output,blower_status
1621512345.1,MANUAL_CONTROL,105.2,32.5,12.6,RUNNING
1621512346.1,MANUAL_CONTROL,105.8,32.7,12.6,RUNNING
```

## Testing Procedure

### RS-485 Control Testing:
1. Connect to RS-485 interface using a serial terminal at 9600 baud
2. Test manual mode entry with `C:MANUAL_MODE`
3. Test SCR output control with `S:OUTPUT=10.0`
4. Verify manual output control by monitoring temperature
5. Test E-STOP functionality during manual operation

### TCP/IP Logging Testing:
1. Connect to TCP/IP interface using telnet on port 23
2. Verify CSV header and data streaming
3. Test both automatic and manual mode logging
4. Monitor log data during output changes

## Implementation Sequence

1. Implement the command processor with manual mode support
2. Add RS-485 interface for control
3. Add TCP/IP interface for logging
4. Modify main loop to support manual control mode
5. Test manual control functionality
6. Test data logging