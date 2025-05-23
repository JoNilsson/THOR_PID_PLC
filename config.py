"""
Configuration file for THOR SiC Heater Control System
Central source of truth for hardware configuration and pin assignments
"""

# Feature Enable/Disable Flags
ENABLE_BLOWER_MONITOR = True    # Monitor for blower operation
ENABLE_RS485_SERIAL = True      # RS-485 serial interface 
ENABLE_NETWORK = True           # TCP/IP network interface

# Pin Reservation System
# Dictionary to track pin reservations
RESERVED_PINS = {}

def reserve_pin(pin_name, component_name):
    """
    Attempt to reserve a pin for a specific component
    
    Args:
        pin_name: Pin name (e.g., 'D5', 'A0', etc.)
        component_name: Name of component reserving the pin
        
    Returns:
        The actual pin object if successful
        
    Raises:
        ValueError: If pin is already reserved
    """
    import board
    
    if pin_name in RESERVED_PINS:
        owner = RESERVED_PINS[pin_name]
        raise ValueError(f"Pin {pin_name} already reserved by {owner}")
    
    # Get the actual pin object
    try:
        pin_obj = getattr(board, pin_name)
        RESERVED_PINS[pin_name] = component_name
        print(f"Pin {pin_name} reserved for {component_name}")
        return pin_obj
    except AttributeError:
        raise ValueError(f"Pin {pin_name} does not exist on this board")

def release_pin(pin_name):
    """
    Release a reserved pin
    
    Args:
        pin_name: Pin name to release
    """
    if pin_name in RESERVED_PINS:
        del RESERVED_PINS[pin_name]
        print(f"Pin {pin_name} released")
    else:
        print(f"Warning: Pin {pin_name} was not reserved")

def list_reserved_pins():
    """List all currently reserved pins"""
    print("\nReserved Pins:")
    if not RESERVED_PINS:
        print("  None")
        return
        
    for pin_name, component in RESERVED_PINS.items():
        print(f"  {pin_name}: reserved by {component}")

# ----- System Pin Assignments -----
# These are the central definitions for all pins in the system

# RS-485 Serial Interface
# P1AM-SERIAL Port 1 configuration
SERIAL_TX_PIN = "TX1"         # Port 1 UART TX (board.TX1)
SERIAL_RX_PIN = "RX1"         # Port 1 UART RX (board.RX1)
SERIAL_DE_PIN = "A6"          # Port 1 DE/RE pin
SERIAL_MODE_PIN = "D3"        # Port 1 Mode pin (LOW=RS485)

# Ethernet Interface
ETH_CS_PIN = "D5"             # Ethernet module Chip Select (using D5 as recommended)
ETH_RESET_PIN = "D11"         # Ethernet module Reset
