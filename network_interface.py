"""
Network Interface for THOR SiC Heater Control System
Author: Johanness A. Nilsson for TERRAFORM INDUSTRIES 2025
Provides TCP/IP socket server for data logging and monitoring
"""

import board
import busio
import digitalio
import time
import config  # Import the central config file

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
        self.csv_header = "timestamp,state,temperature,blower_temp,current,output,blower_status"
        
        # Variable for connected client
        self.client = None
        self.client_buffer = ""
        self.server_socket = None  # Initialize to None for fallback mode
        self.eth = None
        self.pool = None
        
        # Check if network interface is enabled in config
        if not config.ENABLE_NETWORK:
            print("Network interface disabled in config.py")
            return
        
        # Skip Ethernet initialization if libraries not available
        if not ETHERNET_AVAILABLE:
            print("Network interface in simulation mode (no hardware)")
            return
        
        try:
            # Initialize SPI for Ethernet module
            spi = busio.SPI(board.SCK, MOSI=board.MOSI, MISO=board.MISO)
            
            # Setup pins using direct access (standard Adafruit method)
            print(f"Setting up Ethernet pins {config.ETH_CS_PIN} and {config.ETH_RESET_PIN}...")
            
            try:
                # Create the digitalio objects directly without using pin reservation
                # This is the standard approach recommended by Adafruit
                print(f"Creating DigitalInOut for CS pin...")
                cs = digitalio.DigitalInOut(getattr(board, config.ETH_CS_PIN))
                print("CS pin created successfully")
                
                print(f"Creating DigitalInOut for Reset pin...")
                reset = digitalio.DigitalInOut(getattr(board, config.ETH_RESET_PIN))
                print("Reset pin created successfully")
            except Exception as e:
                raise Exception(f"Failed to access Ethernet pins: {e}")
            
            # Initialize Ethernet interface
            print("Initializing Ethernet interface...")
            
            # Configure pins properly
            cs.switch_to_output(value=True)  # CS high by default
            reset.switch_to_output(value=True)  # Reset high by default
            
            # Hardware reset of the WIZnet chip
            reset.value = False  # Assert reset (active low)
            time.sleep(0.1)
            reset.value = True   # Release reset
            time.sleep(0.2)  # Give chip time to stabilize
            
            # Initialize with retry logic
            retry_count = 3
            while retry_count > 0:
                try:
                    self.eth = WIZNET5K(spi, cs, reset, is_dhcp=config.USE_DHCP)
                    
                    if config.USE_DHCP:
                        # Use DHCP for automatic IP configuration
                        print("Requesting IP address via DHCP...")
                        time.sleep(2.0)
                        
                        # Verify we got a valid IP
                        if self.eth.ip_address[0] == 0:
                            print("No IP address assigned, retrying DHCP...")
                            time.sleep(1.0)
                            self.eth.ifconfig = (None, None, None, None)  # Reset config
                            continue
                    else:
                        # Use static IP configuration
                        print("Configuring static IP address...")
                        print(f"  IP: {'.'.join(str(x) for x in config.STATIC_IP)}")
                        print(f"  Subnet: {'.'.join(str(x) for x in config.STATIC_SUBNET)}")
                        
                        self.eth.ifconfig = (config.STATIC_IP, config.STATIC_SUBNET, 
                                           config.STATIC_GATEWAY, config.STATIC_DNS)
                        time.sleep(0.5)  # Give it time to configure
                        
                        # Verify configuration took
                        if self.eth.ip_address[0] == 0:
                            print("Static IP configuration failed, retrying...")
                            time.sleep(1.0)
                            continue
                        
                    # Successfully initialized
                    break
                    
                except Exception as e:
                    print(f"Ethernet init attempt failed: {e}")
                    retry_count -= 1
                    if retry_count > 0:
                        print(f"Retrying... ({retry_count} attempts left)")
                        time.sleep(1.0)
                    else:
                        raise  # Re-raise the exception after all retries fail
            
            # Get IP address information
            # The WIZnet5k library uses different attribute names depending on DHCP vs static
            if config.USE_DHCP:
                self.ip_address = self.eth.pretty_ip(self.eth.ip_address)
                self.subnet_mask = self.eth.pretty_ip(self.eth.subnet_mask)
                self.gateway_ip = self.eth.pretty_ip(self.eth.gateway_ip)
                self.dns_server = self.eth.pretty_ip(self.eth.dns_server)
            else:
                # For static IP, use the configured values
                self.ip_address = self.eth.pretty_ip(config.STATIC_IP)
                self.subnet_mask = self.eth.pretty_ip(config.STATIC_SUBNET)
                self.gateway_ip = self.eth.pretty_ip(config.STATIC_GATEWAY)
                self.dns_server = self.eth.pretty_ip(config.STATIC_DNS)
            
            # Display network information
            print("="*50)
            print(f"NETWORK INTERFACE ONLINE")
            print(f"IP Address: {self.ip_address}")
            print(f"Subnet Mask: {self.subnet_mask}")
            
            # Check if using link-local
            if self.ip_address.startswith("169.254"):
                print("\nPEER-TO-PEER MODE (Link-Local)")
                print("No router needed - connect directly or through switch")
            else:
                print(f"Gateway: {self.gateway_ip}")
                print(f"DNS Server: {self.dns_server}")
                
            # Create socket server
            print(f"\nStarting TCP server on port {port}...")
            # Create a socket pool
            self.pool = socketpool.SocketPool(self.eth)
            self.server_socket = self.pool.socket()
            self.server_socket.settimeout(0.5)  # Half-second timeout
            self.server_socket.bind((0, port))
            self.server_socket.listen(1)
            
            # Display connection information prominently
            print("="*50)
            print(f"CONNECT TO: telnet {self.ip_address} {port}")
            print("="*50)
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
                    # Handle different address formats from socket.accept()
                    try:
                        if isinstance(addr[0], str):
                            ip_str = addr[0]  # Already a string
                        elif isinstance(addr[0], tuple) and len(addr[0]) == 4:
                            ip_str = self.eth.pretty_ip(addr[0])  # IPv4 tuple
                        else:
                            ip_str = str(addr[0])  # Fallback to string conversion
                    except Exception:
                        ip_str = "unknown"  # Fallback if all else fails
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