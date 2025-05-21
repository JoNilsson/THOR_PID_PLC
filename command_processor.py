"""
Command Processor for THOR SiC Heater Control System
Author: Johanness A. Nilsson for TERRAFORM INDUSTRIES 2025
Handles processing of commands from serial and network interfaces
Supports both automatic PID control and manual control modes
"""

import time

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
        self.previous_state = None
        self.last_log_time = 0
        self.log_interval = 1.0  # Log interval in seconds
        
    def set_network_interface(self, network_interface):
        """Set reference to network interface for logging"""
        self.network_interface = network_interface
        
    def process_command(self, cmd_str):
        """
        Process incoming command string and return response
        
        Args:
            cmd_str: The command string to process
            
        Returns:
            Response string with format TYPE:VALUE or ERROR:MESSAGE
        """
        parts = cmd_str.strip().split(":")
        if len(parts) < 2:
            return "ERROR:Invalid command format"
            
        cmd_type = parts[0].upper()
        cmd = parts[1].upper()
        
        # Import these locally to avoid circular imports
        from code import SystemState, Event, EventType, read_temperature, read_current
        
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
        from code import SystemState
        self.manual_mode = True
        # Save the current state to return to later
        self.previous_state = self.state_machine.current_state
        # Set minimum output for safety
        self.scr_output.real = 4.0
        self._log_manual_action("Manual mode enabled")
        print("MANUAL CONTROL MODE ENABLED")
        
    def _exit_manual_mode(self):
        """Exit manual control mode"""
        from code import SystemState
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
        # Import these locally to avoid circular imports
        from code import read_temperature, read_current
        
        if self.network_interface:
            temp = read_temperature(self.safety_manager)
            current = read_current(self.safety_manager)
            temp_str = f"{temp:.1f}" if temp is not None else "ERROR"
            curr_str = f"{current:.2f}" if current is not None else "ERROR"
            
            # Create CSV formatted log entry
            timestamp = time.monotonic()
            log_message = f"{timestamp:.1f},MANUAL_CONTROL,{message},{temp_str},{curr_str},{self.scr_output.real:.2f}"
            self.network_interface.log_message(log_message)
            
    def update(self):
        """
        Periodic update for logging in manual mode
        Should be called in the main loop
        """
        # Import these locally to avoid circular imports
        from code import read_temperature, read_current, blower_monitor
        
        if self.manual_mode and self.network_interface:
            current_time = time.monotonic()
            
            # Only log at specified interval
            if current_time - self.last_log_time >= self.log_interval:
                self.last_log_time = current_time
                
                # Get sensor readings
                temp = read_temperature(self.safety_manager)
                current = read_current(self.safety_manager)
                blower_status = "RUNNING" if blower_monitor.blower_status else "OFF"
                
                # Format values for logging
                temp_str = f"{temp:.1f}" if temp is not None else "ERROR"
                curr_str = f"{current:.2f}" if current is not None else "ERROR"
                
                # Create CSV formatted log entry
                log_entry = f"{current_time:.1f},MANUAL_CONTROL,{temp_str},{curr_str},{self.scr_output.real:.2f},{blower_status}"
                self.network_interface.log_message(log_entry)

# Make the class directly available at the module level
CommandProcessor = CommandProcessor