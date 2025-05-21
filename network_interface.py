"""
Network Interface for THOR SiC Heater Control System
Author: Johanness A. Nilsson for TERRAFORM INDUSTRIES 2025
Provides TCP/IP socket server for data logging and monitoring
"""

import board
import busio
import digitalio
import time
import adafruit_wiznet5k as wiznet
from adafruit_wiznet5k.adafruit_wiznet5k_socket import socket

class NetworkInterface:
    def __init__(self, command_processor, cs_pin, reset_pin, port=23):
        """
        Initialize the TCP/IP network interface
        
        Args:
            command_processor: Reference to command processor object
            cs_pin: Chip select pin for Ethernet module
            reset_pin: Reset pin for Ethernet module
            port: TCP port to listen on (default 23 - telnet)
        """
        # Initialize SPI for Ethernet module
        spi = busio.SPI(board.SCK, MOSI=board.MOSI, MISO=board.MISO)
        cs = digitalio.DigitalInOut(cs_pin)
        reset = digitalio.DigitalInOut(reset_pin)
        
        # Initialize Ethernet interface
        print("Initializing Ethernet interface...")
        self.eth = wiznet.WIZNET5K(spi, cs, reset)
        
        # Use DHCP for automatic IP configuration
        print("Requesting IP address via DHCP...")
        self.eth.dhcp = True
        
        # Wait for IP address
        timeout = time.monotonic() + 10  # 10 second timeout
        while not self.eth.dhcp and time.monotonic() < timeout:
            time.sleep(0.1)
            
        if self.eth.dhcp:
            print(f"IP Address: {self.eth.pretty_ip(self.eth.ip_address)}")
            print(f"Subnet Mask: {self.eth.pretty_ip(self.eth.subnet_mask)}")
            print(f"Gateway: {self.eth.pretty_ip(self.eth.gateway_ip)}")
            print(f"DNS Server: {self.eth.pretty_ip(self.eth.dns_server)}")
        else:
            print("DHCP failed, using default IP address")
            # Set a default IP configuration
            self.eth.ifconfig = (
                (192, 168, 1, 100),  # IP address
                (255, 255, 255, 0),  # Subnet mask
                (192, 168, 1, 1),    # Gateway
                (8, 8, 8, 8)         # DNS server
            )
            
        # Create socket server
        print(f"Starting TCP server on port {port}...")
        self.server_socket = socket(self.eth)
        self.server_socket.bind((0, port))
        self.server_socket.listen(1)
        
        self.command_processor = command_processor
        self.client = None
        self.client_buffer = ""
        
        # Set reference in command processor for logging
        self.command_processor.set_network_interface(self)
        
        # CSV header for data logging
        self.csv_header = "timestamp,state,temperature,current,output,blower_status"
        print(f"Network interface ready on {self.eth.pretty_ip(self.eth.ip_address)}:{port}")
        
    def update(self):
        """
        Handle network connections and incoming commands
        Should be called in the main loop
        """
        # Accept new connections if no client is connected
        if self.client is None:
            try:
                self.client, addr = self.server_socket.accept()
                ip_str = self.eth.pretty_ip(addr[0])
                print(f"Network client connected from {ip_str}:{addr[1]}")
                self.send_message("THOR SiC Heater Control System - Data Logging Interface")
                self.send_message(self.csv_header)
            except OSError:
                pass  # No connection available
                
        # Process read-only monitoring commands if client is connected
        if self.client:
            try:
                if self.client.available():
                    # Handle incoming data
                    data = self.client.recv(256)
                    if data:
                        try:
                            # Decode and add to buffer
                            text = data.decode('utf-8')
                            self.client_buffer += text
                            
                            # Check for complete commands
                            if '\r' in self.client_buffer or '\n' in self.client_buffer:
                                # Split buffer by line endings
                                lines = self.client_buffer.splitlines()
                                
                                # Last line might be incomplete, keep it in buffer
                                self.client_buffer = lines[-1] if lines else ""
                                
                                # Process complete lines
                                for line in lines[:-1] if lines else []:
                                    line = line.strip()
                                    if line:
                                        print(f"Network received: {line}")
                                        # Only allow read-only commands (G:)
                                        if line.upper().startswith("G:"):
                                            response = self.command_processor.process_command(line)
                                            self.send_message(response)
                                        else:
                                            self.send_message("ERROR:Network interface is read-only")
                        except UnicodeError:
                            # Clear buffer on decode error
                            self.client_buffer = ""
            except OSError as e:
                # Handle disconnection
                print(f"Network client disconnected: {e}")
                self.client = None
                self.client_buffer = ""
                
    def log_message(self, message):
        """
        Send a log message to the connected client
        
        Args:
            message: The message string to send
        """
        if self.client:
            try:
                self.send_message(message)
            except OSError:
                # Client disconnected
                print("Network client disconnected during logging")
                self.client = None
                
    def send_message(self, message):
        """
        Send a message to the connected client
        
        Args:
            message: The message string to send
        """
        if self.client:
            try:
                # Add CR+LF and encode
                full_message = message + '\r\n'
                self.client.send(full_message.encode('utf-8'))
            except OSError as e:
                # Handle errors
                print(f"Network send error: {e}")
                self.client = None
                
    def close(self):
        """Close the interface and release resources"""
        if self.client:
            try:
                self.send_message("Connection closing")
                self.client.close()
            except:
                pass
                
        try:
            self.server_socket.close()
        except:
            pass