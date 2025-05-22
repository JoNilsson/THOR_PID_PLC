"""
Command Processor for THOR SiC Heater Control System
Author: Johanness A. Nilsson for TERRAFORM INDUSTRIES 2025
Handles processing of commands from serial and network interfaces
Supports both automatic PID control and manual control modes
"""

import time
import gc

# Note: We'll store references to these functions/classes after initialization
# to avoid circular imports and repeated import allocations
SystemState = None
Event = None
EventType = None
read_temperature = None
read_current = None
read_blower_temperature = None
blower_monitor = None

# This class will be imported by code.py
class CommandProcessor:
    def __init__(self, state_machine, safety_manager, pid_controller, scr_output):
        """
        Initialize the command processor
        
        Args:
            state_machine: The system state machine
            safety_manager: The system safety manager
            pid_controller: The PID controller
            scr_output: The SCR output control
        """
        self.state_machine = state_machine
        self.safety_manager = safety_manager
        self.pid_controller = pid_controller
        self.scr_output = scr_output
        self.manual_mode = False
        self.network_interface = None  # Will be set after initialization
        self.serial_interface = None   # Will be set after initialization
        self.previous_state = None
        self.last_log_time = 0
        self.log_interval = 1.0  # Log interval in seconds
    
    @staticmethod
    def set_code_references(sys_state, event, event_type, read_temp, read_curr, read_blower_temp, blower_mon):
        """Set references to code.py objects to avoid circular imports"""
        global SystemState, Event, EventType, read_temperature, read_current, read_blower_temperature, blower_monitor
        SystemState = sys_state
        Event = event
        EventType = event_type
        read_temperature = read_temp
        read_current = read_curr
        read_blower_temperature = read_blower_temp
        blower_monitor = blower_mon
        
    def set_network_interface(self, network_interface):
        """Set reference to network interface for logging"""
        self.network_interface = network_interface
    
    def set_serial_interface(self, serial_interface):
        """Set reference to serial interface for logging"""
        self.serial_interface = serial_interface
    
    def broadcast_critical_error(self, error_code, error_message):
        """Broadcast critical error to all connected interfaces"""
        critical_msg = f"CRITICAL ERROR [{error_code}]: {error_message}"
        
        # Send to serial interface
        if self.serial_interface and hasattr(self.serial_interface, 'send_message'):
            try:
                self.serial_interface.send_message(f"ERROR:{critical_msg}")
            except:
                pass  # Don't let interface errors prevent error handling
                
        # Send to network interface
        if self.network_interface and hasattr(self.network_interface, 'log_message'):
            try:
                self.network_interface.log_message(critical_msg)
            except:
                pass  # Don't let interface errors prevent error handling
        print(f"Command processor linked to network interface: {'Yes' if network_interface else 'No'}")
        
    def process_command(self, cmd_str):
        """
        Process incoming command string and return response
        
        Args:
            cmd_str: The command string to process
            
        Returns:
            Response string with format TYPE:VALUE or ERROR:MESSAGE
        """
        # Guard against very long commands
        if len(cmd_str) > 50:
            return "ERROR:Command too long"
            
        # Guard against empty commands
        cmd_str = cmd_str.strip()
        if not cmd_str:
            return "ERROR:Empty command"
            
        # Sanitize command string - remove any unwanted control characters
        # CircuitPython doesn't have isprintable(), so use ord() to check ASCII range
        cmd_str = "".join(c for c in cmd_str if (ord(c) >= 32 and ord(c) <= 126) or c in ['\t'])
        
        # Split the command - handle both cases with/without trailing data
        parts = cmd_str.split(":")
        if len(parts) < 2:
            return "ERROR:Invalid command format"
            
        # Get command type and command
        cmd_type = parts[0].upper()
        
        # Special handling for commands with parameters (like S:OUTPUT=5)
        if len(parts) >= 2:
            # For S:OUTPUT commands specifically
            if cmd_type == 'S' and 'OUTPUT=' in cmd_str:
                # Extract everything after S:
                cmd_data = cmd_str[2:].strip()
                
                # Check if this is OUTPUT or OUTPUT_INCREMENT
                if cmd_data.startswith('OUTPUT='):
                    cmd = 'OUTPUT='
                    # The value is processed later
                elif cmd_data.startswith('OUTPUT_INCREMENT='):
                    cmd = 'OUTPUT_INCREMENT='
                    # The value is processed later
                else:
                    cmd = parts[1].upper()
            else:
                # For other commands - use standard processing
                cmd = parts[1].upper()
                
                # Clean up cmd by removing any trailing command markers
                if ':' in cmd:
                    cmd = cmd.split(':')[0]
        else:
            # This shouldn't happen due to the earlier check, but just in case
            return "ERROR:Invalid command format"
            
        # Debug info
        print(f"Command parsed - Type: {cmd_type}, Command: {cmd}")
        
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
                    
            elif cmd == "MANUAL_MODE" or cmd.strip() == "MANUAL_MODE":
                # Switch to manual control mode - added more robust handling for different line ending formats
                try:
                    self._enter_manual_mode()
                    return "OK:Manual control mode enabled"
                except Exception as e:
                    print(f"Error entering manual mode: {e}")
                    return "ERROR:Failed to enter manual mode"
                
            elif cmd == "AUTO_MODE":
                # Switch back to automatic PID control mode
                self._exit_manual_mode()
                return "OK:Automatic control mode enabled"
                
            elif cmd == "STOP":
                # Stop heating in either mode
                if self.manual_mode:
                    self.scr_output.real = 4.0  # Minimum output
                    self._log_manual_action("Manual heating stopped")
                    return "OK:Manual heating stopped"
                else:
                    self.state_machine.transition_to(SystemState.SHUTDOWN)
                    return "OK:System shutdown initiated"
                
        # Get commands
        elif cmd_type == "G":  # Get commands
            if cmd == "TEMP":
                temp = read_temperature(self.safety_manager)
                return f"TEMP:{temp:.1f}" if temp is not None else "ERROR:Temp read failed"
                
            elif cmd == "BLOWER_TEMP":
                blower_temp = read_blower_temperature()
                return f"BLOWER_TEMP:{blower_temp:.1f}" if blower_temp is not None else "INFO:Blower temp not available"
                
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
                
            elif cmd == "PID":
                if not self.manual_mode:
                    return f"PID:{self.pid_controller.kp:.2f},{self.pid_controller.ki:.2f},{self.pid_controller.kd:.2f}"
                else:
                    return "ERROR:PID not active in manual mode"
            
            elif cmd == "RS485":
                # RS485 diagnostic - simplified due to memory constraints
                return "RS485:OK"
            
            elif cmd == "MEM":
                # Memory diagnostic
                import gc
                gc.collect()
                free = gc.mem_free()
                return "MEM:" + str(free)
                
        # Set commands
        elif cmd_type == "S":  # Set commands
            # Handle OUTPUT command with different formats
            if "OUTPUT=" in cmd:  # Check for substring to be more forgiving with format
                if self.manual_mode:
                    try:
                        # Extract the value part after the equals sign
                        output_part = cmd.split("OUTPUT=")[1].strip()
                        output = float(output_part)
                        # Constrain to valid 4-20mA range
                        output = max(4.0, min(20.0, output))
                        self.scr_output.real = output
                        self._log_manual_action(f"Output set to {output:.2f}mA")
                        return f"OK:Output set to {output:.2f}mA"
                    except (ValueError, IndexError) as e:
                        print(f"Error parsing OUTPUT command: {e}")
                        return "ERROR:Invalid output value"
                else:
                    return "ERROR:Manual mode required for direct output control"
                    
            elif "OUTPUT_INCREMENT=" in cmd:  # Check for substring to be more forgiving
                if self.manual_mode:
                    try:
                        # Extract the value part after the equals sign
                        increment_part = cmd.split("OUTPUT_INCREMENT=")[1].strip()
                        increment = float(increment_part)
                        new_output = self.scr_output.real + increment
                        # Constrain to valid 4-20mA range
                        new_output = max(4.0, min(20.0, new_output))
                        self.scr_output.real = new_output
                        self._log_manual_action(f"Output incremented to {new_output:.2f}mA")
                        return f"OK:Output incremented to {new_output:.2f}mA"
                    except (ValueError, IndexError) as e:
                        print(f"Error parsing OUTPUT_INCREMENT command: {e}")
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
        print("MANUAL CONTROL MODE ENABLED")
        
    def _exit_manual_mode(self):
        """Exit manual control mode"""
        if self.manual_mode:
            self.manual_mode = False
            # Set minimum output before returning to automatic control
            self.scr_output.real = 4.0
            self._log_manual_action("Manual mode disabled")
            # Transition to IDLE state for safety
            self.state_machine.transition_to(SystemState.IDLE)
            print("MANUAL CONTROL MODE DISABLED - Returning to automatic control")
            
    def _log_manual_action(self, message):
        """
        Log manual control actions to network interface
        
        Args:
            message: The action message to log
        """
        if self.network_interface:
            temp = read_temperature(self.safety_manager)
            blower_temp = read_blower_temperature()
            current = read_current(self.safety_manager)
            temp_str = f"{temp:.1f}" if temp is not None else "ERROR"
            blower_temp_str = f"{blower_temp:.1f}" if blower_temp is not None else "UNKNOWN"
            curr_str = f"{current:.2f}" if current is not None else "ERROR"
            
            # Create CSV formatted log entry
            timestamp = time.monotonic()
            log_message = f"{timestamp:.1f},MANUAL_CONTROL,{message},{temp_str},{blower_temp_str},{curr_str},{self.scr_output.real:.2f}"
            self.network_interface.log_message(log_message)
            
    def update(self):
        """
        Periodic update for logging in manual mode
        Should be called in the main loop
        """
        if self.manual_mode and self.network_interface:
            current_time = time.monotonic()
            
            # Only log at specified interval
            if current_time - self.last_log_time >= self.log_interval:
                self.last_log_time = current_time
                
                # Get sensor readings
                temp = read_temperature(self.safety_manager)
                blower_temp = read_blower_temperature()
                current = read_current(self.safety_manager)
                blower_status = "RUNNING" if blower_monitor.blower_status else "OFF"
                
                # Format values for logging
                temp_str = f"{temp:.1f}" if temp is not None else "ERROR"
                blower_temp_str = f"{blower_temp:.1f}" if blower_temp is not None else "UNKNOWN"
                curr_str = f"{current:.2f}" if current is not None else "ERROR"
                
                # Create CSV formatted log entry
                log_entry = f"{current_time:.1f},MANUAL_CONTROL,{temp_str},{blower_temp_str},{curr_str},{self.scr_output.real:.2f},{blower_status}"
                self.network_interface.log_message(log_entry)

# Make the class directly available at the module level
CommandProcessor = CommandProcessor