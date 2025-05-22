"""
Serial Interface for THOR SiC Heater Control System
Author: Johanness A. Nilsson for TERRAFORM INDUSTRIES 2025
Provides RS-485 serial interface for system control
"""

import busio
import board
import digitalio
import time
import config  # Import the central config file
from rs485_wrapper import RS485

class SerialInterface:
    def __init__(self, command_processor, tx_pin, rx_pin, de_pin, baudrate=9600):
        """
        Initialize the RS-485 serial interface
        
        Args:
            command_processor: Reference to command processor object
            tx_pin: TX pin for UART
            rx_pin: RX pin for UART
            de_pin: Data Enable pin for RS-485
            baudrate: Communication baudrate (default 9600)
        """
        # Check if RS485 is enabled in config
        if not config.ENABLE_RS485_SERIAL:
            print("RS-485 interface disabled in config.py")
            self.rs485 = None
            self.command_processor = command_processor
            self.buffer = ""
            return
            
        # Create UART object
        try:
            # Get the DE pin from config
            print(f"Requesting RS-485 DE pin {config.SERIAL_DE_PIN}...")
            de_pin_obj = config.reserve_pin(config.SERIAL_DE_PIN, "RS-485 DE")
            
            # Create the UART
            try:
                print(f"Creating UART on TX={tx_pin}, RX={rx_pin}, baudrate={baudrate}...")
                
                # Print pin details for debugging
                print(f"TX pin: {tx_pin}")
                print(f"RX pin: {rx_pin}")
                
                # Make sure TX and RX are valid pins
                if not hasattr(board, str(tx_pin).replace('board.', '')):
                    raise ValueError(f"Invalid TX pin: {tx_pin}")
                if not hasattr(board, str(rx_pin).replace('board.', '')):
                    raise ValueError(f"Invalid RX pin: {rx_pin}")
                
                # Create UART with explicit parameters
                uart = busio.UART(tx_pin, rx_pin, baudrate=baudrate, 
                                 bits=8, parity=None, stop=1, 
                                 timeout=0.1, receiver_buffer_size=128)
                                 
                print(f"UART created successfully: baudrate={baudrate}, bits=8, parity=None, stop=1")
            except Exception as e:
                raise Exception(f"Failed to create UART: {e}")
            
            # Create and configure the DE pin
            try:
                print(f"Creating DigitalInOut for DE pin...")
                de_pin_dio = digitalio.DigitalInOut(de_pin_obj)
                de_pin_dio.switch_to_output(value=False)  # Start in receive mode
                print("DE pin configured successfully")
            except Exception as e:
                raise Exception(f"Failed to initialize DE pin: {e}")
            
            # Initialize RS-485 wrapper
            print("Initializing RS485 wrapper...")
            self.rs485 = RS485(uart, de_pin_dio)
            print("RS485 wrapper initialized")
            
            # Store reference to command processor
            self.command_processor = command_processor
            
            # Initialize command buffer
            self.buffer = ""
            
            # Debug timing
            self.last_debug_time = time.monotonic()
            self.debug_interval = 10.0  # Print debug info every 10 seconds
            
            # Send welcome message
            self.send_message("THOR SiC Heater Control System")
            self.send_message("RS-485 Control Interface Ready")
            print(f"RS-485 serial interface initialized at {baudrate} baud")
        except Exception as e:
            print(f"Error initializing serial interface: {e}")
            print("Serial interface in fallback mode (no hardware)")
            # Create dummy objects for graceful failure
            self.rs485 = None
            self.command_processor = command_processor
            self.buffer = ""
        
    def update(self):
        """
        Check for incoming commands and process them
        Should be called in the main loop
        """
        # Skip if serial interface failed to initialize
        if self.rs485 is None:
            return
        
        try:
            # Periodic debug output
            current_time = time.monotonic()
            if current_time - self.last_debug_time >= self.debug_interval:
                self.last_debug_time = current_time
                de_state = "HIGH" if self.rs485.de_pin.value else "LOW"
                print(f"RS-485 Debug: DE pin={de_state}, in_waiting={self.rs485.in_waiting}")
            
            # Check if data is available
            if self.rs485.in_waiting:
                # Read available data - limit to a reasonable amount
                bytes_to_read = min(self.rs485.in_waiting, 64)  # Read up to 64 bytes at a time
                data = self.rs485.read(bytes_to_read)
                
                if data:
                    try:
                        # Decode and add to buffer
                        text = data.decode('utf-8')
                        print(f"RS-485 decoded: '{text}'")
                        
                        # Limit buffer size to prevent memory issues
                        if len(self.buffer) + len(text) > 128:  # Reduced from 256 to 128
                            print("WARNING: Buffer overflow, truncating")
                            self.buffer = text  # Discard old data
                        else:
                            self.buffer += text
                        
                        # Check for command completion by presence of command type and terminator
                        command_complete = False
                        
                        # Look for command termination (CR or LF)
                        if '\r' in self.buffer or '\n' in self.buffer:
                            command_complete = True
                            
                            # Use a more robust command extraction method
                            buffer_copy = self.buffer
                            # Normalize line endings
                            buffer_copy = buffer_copy.replace('\r\n', '\n').replace('\r', '\n')
                            
                            # Split into lines, preserving empty lines
                            lines = buffer_copy.split('\n')
                            
                            # Print diagnostic info
                            print(f"RS-485 buffer split into {len(lines)} lines")
                            
                            # Process all complete lines (all except the last one if it's not terminated)
                            complete_lines = lines[:-1]
                            
                            # Keep the last line in buffer only if it's not empty
                            if lines and lines[-1]:
                                self.buffer = lines[-1]
                            else:
                                self.buffer = ""
                            
                            # Process each complete line
                            for line in complete_lines:
                                self._process_command_line(line)
                            
                        # Check for a complete command in the buffer without terminator
                        # This could happen with slow serial transmission or packet splitting
                        elif ':' in self.buffer:
                            # Check if we have a complete command by looking for command type patterns
                            parts = self.buffer.split(':')
                            cmd_type = parts[0].upper() if parts else ""
                            
                            # Check if command type is valid and we have a command
                            if cmd_type in ['C', 'G', 'S'] and len(parts) >= 2:
                                # Check if command appears complete based on format
                                if cmd_type == 'S' and 'OUTPUT=' in self.buffer:
                                    command_complete = True
                                elif cmd_type == 'G' and any(cmd in parts[1].upper() for cmd in ['TEMP', 'STATE', 'CURRENT', 'OUTPUT', 'PID']):
                                    command_complete = True
                                elif cmd_type == 'C' and any(cmd in parts[1].upper() for cmd in ['INIT', 'START', 'MANUAL_MODE', 'AUTO_MODE', 'STOP']):
                                    command_complete = True
                            
                            if command_complete:
                                print(f"Processing complete unterminated command: '{self.buffer}'")
                                self._process_command_line(self.buffer)
                                self.buffer = ""
                                
                    except UnicodeError as e:
                        # Clear buffer on decode error
                        print(f"RS-485 decode error: {e}, clearing buffer")
                        print(f"Raw data was: {data}")
                        self.buffer = ""
            
            # Check for partial commands that have been sitting in buffer
            if self.buffer and len(self.buffer) > 0 and ':' in self.buffer:
                # Check if we have what looks like a valid command start
                parts = self.buffer.split(':')
                cmd_type = parts[0].upper() if parts else ""
                
                if cmd_type in ['C', 'G', 'S']:
                    # If we have a command type, check if we can process it
                    if cmd_type == 'S' and 'OUTPUT=' in self.buffer:
                        print(f"Processing delayed unterminated command: '{self.buffer}'")
                        self._process_command_line(self.buffer)
                        self.buffer = ""
                    elif cmd_type == 'G' and len(parts) >= 2:
                        print(f"Processing delayed unterminated command: '{self.buffer}'")
                        self._process_command_line(self.buffer)
                        self.buffer = ""
                    elif cmd_type == 'C' and len(parts) >= 2:
                        print(f"Processing delayed unterminated command: '{self.buffer}'")
                        self._process_command_line(self.buffer)
                        self.buffer = ""
                        
        except Exception as e:
            # Catch-all error handler to prevent serial processing from crashing the system
            print(f"Unexpected error in RS-485 update: {e}")
            self.buffer = ""  # Clear buffer to recover
                        
    def _process_command_line(self, line):
        """Process a single command line and send response"""
        # Clean up the line
        line = line.strip()
        if not line:
            return
            
        # Debug output
        print(f"RS-485 received command: '{line}'")
        
        try:
            # Process the command
            response = self.command_processor.process_command(line)
            # Simplified debug to save memory
            print("RS-485 response ready")
            self.send_message(response)
        except Exception as e:
            # Handle errors
            print(f"Error processing command: {e}")
            self.send_message(f"ERROR:Internal error processing command")
            self.buffer = ""  # Clear buffer to recover
    
    def send_message(self, message):
        """
        Send a message over the RS-485 interface
        
        Args:
            message: The message string to send
        """
        # Skip if serial interface failed to initialize
        if self.rs485 is None:
            return
            
        try:
            # Add CR+LF and encode
            full_message = message + '\r\n'
            self.rs485.write(full_message.encode('utf-8'))
        except Exception as e:
            print(f"RS-485 send error: {e}")
            
    def close(self):
        """Close the interface and release resources"""
        # Skip if serial interface failed to initialize
        if self.rs485 is None:
            return
            
        try:
            # Send goodbye message
            self.send_message("RS-485 interface closing")
            # No explicit close method for RS485 wrapper
            # but we can reset the UART if needed
        except:
            pass

# Make the class directly available at module level
SerialInterface = SerialInterface