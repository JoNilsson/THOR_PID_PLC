"""
RS-485 Wrapper for THOR SiC Heater Control System
Author: Johanness A. Nilsson for TERRAFORM INDUSTRIES 2025
Provides an interface for RS-485 communication
"""

import time

class RS485:
    """
    RS-485 wrapper class for CircuitPython
    Provides a wrapper around a UART object with DE pin control
    for RS-485 half-duplex communication
    """
    def __init__(self, uart, de_pin):
        """
        Initialize RS-485 interface
        
        Args:
            uart: UART object already configured with desired settings
            de_pin: DigitalInOut object for the DE pin (data enable)
        """
        self.uart = uart
        self.de_pin = de_pin
        self.de_pin.switch_to_output(value=False)  # Start with DE pin low (receive mode)
        self.timeout = 0.1  # Default timeout in seconds
        
    @property
    def in_waiting(self):
        """Get the number of bytes waiting in the receive buffer"""
        return self.uart.in_waiting
        
    def read(self, size=1):
        """
        Read data from the RS-485 bus
        
        Args:
            size: Number of bytes to read
            
        Returns:
            Bytes read or None if no data available
        """
        # Ensure DE pin is low (receive mode)
        self.de_pin.value = False
        
        # Read data from UART
        return self.uart.read(size)
        
    def write(self, data):
        """
        Write data to the RS-485 bus
        
        Args:
            data: Bytes to write
            
        Returns:
            Number of bytes written
        """
        # Set DE pin high (transmit mode)
        self.de_pin.value = True
        
        # Small delay to ensure DE pin has time to switch
        time.sleep(0.001)
        
        # Write data
        bytes_written = self.uart.write(data)
        
        # Wait for transmission to complete
        self.uart.reset_input_buffer()
        
        # Set DE pin back to low (receive mode)
        time.sleep(0.001)  # Wait for last byte to finish transmitting
        self.de_pin.value = False
        
        return bytes_written
        
    def flush(self):
        """Flush the UART buffers"""
        self.uart.reset_input_buffer()
        self.uart.reset_output_buffer()