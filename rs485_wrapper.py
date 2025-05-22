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
        print(f"RS-485 DE pin initial state: {'HIGH' if self.de_pin.value else 'LOW'} (should be LOW for RX)")
        
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
        print(f"RS-485: Setting DE pin HIGH for TX")
        self.de_pin.value = True
        
        # Longer delay to ensure DE pin has time to switch
        time.sleep(0.010)  # Increased to 10ms for debugging
        
        # Verify DE pin is actually high
        de_state = self.de_pin.value
        print(f"RS-485: DE pin is {'HIGH' if de_state else 'LOW'} (should be HIGH)")
        
        # Write data
        bytes_written = self.uart.write(data)
        print(f"RS-485 TX: {data} ({bytes_written} bytes)")
        
        # Check if bytes were actually written
        if bytes_written != len(data):
            print(f"RS-485 WARNING: Only wrote {bytes_written} of {len(data)} bytes!")
        
        # Force UART to transmit by waiting for TX to complete
        # CircuitPython UART doesn't have a flush method, but we can check in_waiting
        # Some versions have a 'out_waiting' property that shows bytes in TX buffer
        if hasattr(self.uart, 'out_waiting'):
            while self.uart.out_waiting > 0:
                time.sleep(0.001)
                
        # Wait for UART to actually transmit
        # CircuitPython's UART might buffer, so we need to ensure it's sent
        time.sleep(0.020)  # Wait 20ms to ensure transmission
        
        # Allow more time for transmission to complete based on data length and baud rate
        # Calculate delay based on bytes and baud rate (assuming 10 bits per byte with start/stop)
        bits_to_send = len(data) * 10  # 8 data bits + 1 start bit + 1 stop bit
        seconds_per_bit = 1.0 / self.uart.baudrate
        transmission_time = bits_to_send * seconds_per_bit
        
        # Add a safety margin (at least 10ms, or double the calculated time)
        delay = max(0.010, transmission_time * 2)
        time.sleep(delay)
        
        # Clear input buffer
        self.uart.reset_input_buffer()
        
        # Set DE pin back to low (receive mode)
        print(f"RS-485: Setting DE pin LOW for RX")
        self.de_pin.value = False
        
        return bytes_written
        
    def flush(self):
        """Flush the UART buffers"""
        self.uart.reset_input_buffer()
        self.uart.reset_output_buffer()