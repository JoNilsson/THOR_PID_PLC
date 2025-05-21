"""
Network Interface for THOR SiC Heater Control System
Author: Johanness A. Nilsson for TERRAFORM INDUSTRIES 2025
Provides TCP/IP socket server for data logging and monitoring
"""

import board
import busio
import digitalio
import time

# Try to import Ethernet libraries, but make them optional
try:
    from adafruit_wiznet5k.adafruit_wiznet5k import WIZNET5K
    import adafruit_wiznet5k.adafruit_wiznet5k_socketpool as socketpool
    ETHERNET_AVAILABLE = True
except ImportError as e:
    print(f"WARNING: WIZnet5k library not available: {e}. Network logging disabled.")
    ETHERNET_AVAILABLE = False

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
        # Store command processor reference
        self.command_processor = command_processor
        
        # Set reference in command processor for logging
        self.command_processor.set_network_interface(self)
        
        # CSV header for data logging
        self.csv_header = "timestamp,state,temperature,current,output,blower_status"
        
        # Variable for connected client
        self.client = None
        self.client_buffer = ""
        self.server_socket = None  # Initialize to None for fallback mode
        self.eth = None
        self.pool = None
        
        # Skip Ethernet initialization if libraries not available
        if not ETHERNET_AVAILABLE:
            print("Network interface in simulation mode (no hardware)")
            return
        
        try:
            # Initialize SPI for Ethernet module
            spi = busio.SPI(board.SCK, MOSI=board.MOSI, MISO=board.MISO)
            cs = digitalio.DigitalInOut(cs_pin)
            reset = digitalio.DigitalInOut(reset_pin)
            
            # Initialize Ethernet interface
            print("Initializing Ethernet interface...")
            self.eth = WIZNET5K(spi, cs, reset, is_dhcp=True)
            
            # Use DHCP for automatic IP configuration
            print("Requesting IP address via DHCP...")
            
            # Wait a moment for DHCP to complete
            time.sleep(0.5)
            
            # Display network information
            print(f"IP Address: {self.eth.pretty_ip(self.eth.ip_address)}")
            print(f"Subnet Mask: {self.eth.pretty_ip(self.eth.subnet_mask)}")
            print(f"Gateway: {self.eth.pretty_ip(self.eth.gateway_ip)}")
            print(f"DNS Server: {self.eth.pretty_ip(self.eth.dns_server)}")
                
            # Create socket server
            print(f"Starting TCP server on port {port}...")
            # Create a socket pool
            self.pool = socketpool.SocketPool(self.eth)
            self.server_socket = self.pool.socket()
            self.server_socket.settimeout(0.5)  # Half-second timeout
            self.server_socket.bind((0, port))
            self.server_socket.listen(1)
            
            print(f"Network interface ready on {self.eth.pretty_ip(self.eth.ip_address)}:{port}")
        except Exception as e:
            print(f"Error initializing network interface: {e}")
            print("Network interface in fallback mode (no hardware)")
            # Reset attributes for fallback mode
            self.eth = None
            self.pool = None
            self.server_socket = None
        
    def update(self):
        """
        Handle network connections and incoming commands
        Should be called in the main loop
        """
        # Skip if Ethernet not available or socket not initialized
        if not ETHERNET_AVAILABLE or self.server_socket is None:
            return
            
        try:
            # Accept new connections if no client is connected
            if self.client is None:
                try:
                    self.client, addr = self.server_socket.accept()
                    ip_str = self.eth.pretty_ip(addr[0])
                    print(f"Network client connected from {ip_str}:{addr[1]}")
                    self.send_message("THOR SiC Heater Control System - Data Logging Interface")
                    self.send_message(self.csv_header)
                except (OSError, TimeoutError):
                    pass  # No connection available or timeout
                    
            # Process read-only monitoring commands if client is connected
            if self.client:
                try:
                    # Check for data to read
                    try:
                        # Handle incoming data (with timeout)
                        self.client.settimeout(0.01)  # Very short timeout
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
                    except (OSError, TimeoutError):
                        # No data available or timeout
                        pass
                except Exception as e:
                    # Handle disconnection
                    print(f"Network client disconnected: {e}")
                    self.client = None
                    self.client_buffer = ""
        except Exception as e:
            print(f"Network interface error: {e}")
                
    def log_message(self, message):
        """
        Send a log message to the connected client
        
        Args:
            message: The message string to send
        """
        # Skip if Ethernet not available or if eth object is None
        if not ETHERNET_AVAILABLE or self.eth is None:
            # Print to serial console instead
            print(f"LOG: {message}")
            return
            
        if self.client:
            try:
                self.send_message(message)
            except OSError:
                # Client disconnected
                print("Network client disconnected during logging")
                self.client = None
        else:
            # No client connected, log to serial console instead
            print(f"LOG: {message}")
                
    def send_message(self, message):
        """
        Send a message to the connected client
        
        Args:
            message: The message string to send
        """
        # Skip if Ethernet not available or if eth object is None
        if not ETHERNET_AVAILABLE or self.eth is None:
            return
            
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
        # Skip if Ethernet not available or if eth object is None
        if not ETHERNET_AVAILABLE or self.eth is None:
            return
            
        if self.client:
            try:
                self.send_message("Connection closing")
                self.client.close()
            except:
                pass
                
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass