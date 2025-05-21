"""
Serial Interface for THOR SiC Heater Control System
Author: Johanness A. Nilsson for TERRAFORM INDUSTRIES 2025
Provides RS-485 serial interface for system control
"""

import busio
import board
import time
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
        # Create UART object
        uart = busio.UART(tx_pin, rx_pin, baudrate=baudrate, 
                          bits=8, parity=None, stop=1, 
                          timeout=0.1, receiver_buffer_size=256)
        
        # Initialize RS-485 wrapper
        self.rs485 = RS485(uart, de_pin)
        
        # Store reference to command processor
        self.command_processor = command_processor
        
        # Initialize command buffer
        self.buffer = ""
        
        # Send welcome message
        self.send_message("THOR SiC Heater Control System")
        self.send_message("RS-485 Control Interface Ready")
        print(f"RS-485 serial interface initialized at {baudrate} baud")
        
    def update(self):
        """
        Check for incoming commands and process them
        Should be called in the main loop
        """
        # Check if data is available
        if self.rs485.in_waiting:
            # Read available data
            data = self.rs485.read(self.rs485.in_waiting)
            if data:
                try:
                    # Decode and add to buffer
                    text = data.decode('utf-8')
                    self.buffer += text
                    
                    # Check for complete commands (terminated by CR or LF)
                    if '\r' in self.buffer or '\n' in self.buffer:
                        # Split buffer by line endings
                        lines = self.buffer.splitlines()
                        
                        # Last line might be incomplete, keep it in buffer
                        self.buffer = lines[-1] if lines else ""
                        
                        # Process complete lines
                        for line in lines[:-1] if lines else []:
                            line = line.strip()
                            if line:
                                # Process command and send response
                                print(f"RS-485 received: {line}")
                                response = self.command_processor.process_command(line)
                                self.send_message(response)
                except UnicodeError:
                    # Clear buffer on decode error
                    print("RS-485 decode error, clearing buffer")
                    self.buffer = ""
    
    def send_message(self, message):
        """
        Send a message over the RS-485 interface
        
        Args:
            message: The message string to send
        """
        try:
            # Add CR+LF and encode
            full_message = message + '\r\n'
            self.rs485.write(full_message.encode('utf-8'))
        except Exception as e:
            print(f"RS-485 send error: {e}")
            
    def close(self):
        """Close the interface and release resources"""
        try:
            # Send goodbye message
            self.send_message("RS-485 interface closing")
            # No explicit close method for RS485 wrapper
            # but we can reset the UART if needed
        except:
            pass