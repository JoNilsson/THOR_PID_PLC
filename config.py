"""
Configuration file for THOR SiC Heater Control System
Controls which hardware interfaces are enabled
"""

# Feature Enable/Disable Flags
ENABLE_BLOWER_MONITOR = True    # Monitor for blower operation
ENABLE_RS485_SERIAL = False     # RS-485 serial interface 
ENABLE_NETWORK = False          # TCP/IP network interface

# Default Pins - centralized for easier management
# RS-485 Serial Interface
SERIAL_DE_PIN = "D7"            # RS-485 Data Enable pin

# Ethernet Interface
ETH_CS_PIN = "D10"              # Ethernet module Chip Select
ETH_RESET_PIN = "D11"           # Ethernet module Reset

# Blower Monitor 
BLOWER_SENSOR_PIN = "D14"       # Current sensing for blower