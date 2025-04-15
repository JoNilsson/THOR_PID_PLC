{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  name = "circuitpython-p1am-dev";

  buildInputs = with pkgs; [
    circup
    cmake
    gcc
    gcc-arm-embedded-13
    git
    gnumake
    lsof
    python313
    python313Packages.adafruit-board-toolkit
    python313Packages.adafruit-platformdetect
    python313Packages.pip
    python313Packages.pyserial
    python313Packages.setuptools
    python313Packages.virtualenv
    screen
    usbutils
  ];

  shellHook = ''
    export CIRCUITPY_BOARD=p1am_200
    export PATH=$PATH:$HOME/.local/bin

    if [ -d "$PWD/modules/" ]; then
      export PYTHONPATH="$PYTHONPATH:$PWD/modules"
      echo "Added existing CIRCUITPY/modules to PYTHONPATH"
    fi
    
    if [ -d "$PWD/lib" ]; then
      export PYTHONPATH="$PYTHONPATH:$PWD/lib"
      echo "Added existing CIRCUITPY/lib to PYTHONPATH"
    fi

    # Function to find P1AM-200 serial connection
    find_p1am_serial() {
      echo "Searching for P1AM-200 serial connection..."
      
      # Look for P1AM-200 in USB devices
      echo "USB devices:"
      lsusb | grep -i "P1AM\|Productivity"
      
      # Check if device is mounted as CIRCUITPY
      if [ -d "/run/media/$USER/CIRCUITPY" ]; then
        echo "P1AM-200 mounted as CIRCUITPY at /run/media/$USER/CIRCUITPY"
      fi
      
      # Look for serial ports
      echo "Serial ports:"
      ls -l /dev/ttyACM* /dev/ttyUSB* 2>/dev/null || echo "No serial ports found"
      
      # Check which process is using the serial port
      echo "Processes using serial ports:"
      lsof /dev/ttyACM* /dev/ttyUSB* 2>/dev/null || echo "No processes using serial ports"
      
      # Use Python to get more details about serial ports
      python3 -c '
import serial.tools.list_ports
ports = serial.tools.list_ports.comports()
if ports:
    print("Available serial ports:")
    for port in ports:
        if "P1AM" in port.description or "Productivity" in port.description:
            print(f"P1AM-200 found at {port.device} - {port.description} [VID:PID={port.vid:04x}:{port.pid:04x}]")
        else:
            print(f"{port.device} - {port.description}")
else:
    print("No serial ports detected")
'
    }
    
    # Run the function to find P1AM-200
    find_p1am_serial
    
    # Create a helper function to connect to the serial console
    p1am_console() {
      if [ -z "$1" ]; then
        echo "Usage: p1am_console /dev/ttyXXX"
        echo "Available serial ports:"
        ls /dev/ttyACM* /dev/ttyUSB* 2>/dev/null || echo "No serial ports found"
        return 1
      fi
      
      echo "Connecting to P1AM-200 on $1..."
      echo "Press Ctrl+A followed by \ to exit"
      sleep 1
      screen $1 115200
    }

    echo "Activated CircuitPython P1AM-200 development environment."
    echo ""
    echo "Target board: $CIRCUITPY_BOARD /n"
    echo "Use 'p1am_console /dev/ttyXXX' to connect to the serial console /n"
    echo "Use 'find_p1am_serial' to search for the P1AM-200 again"

    
  '';
}
