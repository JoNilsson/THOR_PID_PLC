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
                        
                        # Check for complete commands (terminated by CR or LF)
                        if '\r' in self.buffer or '\n' in self.buffer:
                            # Split buffer by line endings
                            lines = self.buffer.splitlines()
                            
                            # Print all lines for debugging
                            print(f"RS-485 buffer split into {len(lines)} lines")
                            
                            # Last line might be incomplete, keep it in buffer
                            self.buffer = lines[-1] if lines else ""
                            
                            # Process complete lines
                            for line in lines[:-1] if lines else []:
                                line = line.strip()
                                if line:
                                    # Process command and send response
                                    print(f"RS-485 received command: '{line}'")
                                    try:
                                        response = self.command_processor.process_command(line)
                                        print(f"RS-485 sending response: '{response}'")
                                        self.send_message(response)
                                    except Exception as e:
                                        print(f"Error processing command: {e}")
                                        self.send_message(f"ERROR:Internal error processing command")
                                        # Clear buffer to recover from error state
                                        self.buffer = ""
                    except UnicodeError as e:
                        # Clear buffer on decode error
                        print(f"RS-485 decode error: {e}, clearing buffer")
                        print(f"Raw data was: {data}")
                        self.buffer = ""
            
            # Check if buffer has been sitting too long without a terminator
            # This helps recover from partial commands
            if self.buffer and len(self.buffer) > 0:
                # If buffer contains a command without CR/LF for too long, try to process it
                if ':' in self.buffer and len(self.buffer) >= 3:
                    # After 1 second, force processing of partial command
                    print(f"Processing potential unterminated command: '{self.buffer}'")
                    line = self.buffer.strip()
                    self.buffer = ""
                    
                    try:
                        response = self.command_processor.process_command(line)
                        print(f"RS-485 sending response: '{response}'")
                        self.send_message(response)
                    except Exception as e:
                        print(f"Error processing unterminated command: {e}")
                        self.send_message(f"ERROR:Invalid command format")
        
        except Exception as e:
            # Catch-all error handler to prevent serial processing from crashing the system
            print(f"Unexpected error in RS-485 update: {e}")
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