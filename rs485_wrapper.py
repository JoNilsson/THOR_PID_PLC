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
        
        # Store baudrate for timing calculations
        self.baudrate = getattr(uart, 'baudrate', 9600)  # Default to 9600 if not available
        print(f"RS-485 wrapper initialized with baudrate: {self.baudrate}")
        
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
        data = self.uart.read(size)
        
        # Log received data
        if data and len(data) > 0:
            print(f"RS-485 RX: {data} ({len(data)} bytes)")
            
        return data
        
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
        
        # Longer delay to ensure DE pin has time to switch
        time.sleep(0.005)  # Increased from 0.001 to 0.005
        
        # Write data
        bytes_written = self.uart.write(data)
        print(f"RS-485 TX: {data} ({bytes_written} bytes)")
        
        # Allow more time for transmission to complete based on data length and baud rate
        # Calculate delay based on bytes and baud rate (assuming 10 bits per byte with start/stop)
        bits_to_send = len(data) * 10  # 8 data bits + 1 start bit + 1 stop bit
        seconds_per_bit = 1.0 / self.uart.baudrate
        transmission_time = bits_to_send * seconds_per_bit
        
        # Add a safety margin (at least 5ms, or double the calculated time)
        delay = max(0.005, transmission_time * 2)
        time.sleep(delay)
        
        # Clear input buffer
        self.uart.reset_input_buffer()
        
        # Set DE pin back to low (receive mode)
        self.de_pin.value = False
        
        return bytes_written
        
    def flush(self):
        """Flush the UART buffers"""
        self.uart.reset_input_buffer()
        self.uart.reset_output_buffer()