"""
Console Output Manager for THOR SiC Heater Control System
Provides centralized, event-based console logging with reduced noise
"""

import time

# ANSI color codes for console output
ANSI_RED = "\033[31m"
ANSI_GREEN = "\033[32m"
ANSI_YELLOW = "\033[33m"
ANSI_BLUE = "\033[34m"
ANSI_CYAN = "\033[36m"
ANSI_MAGENTA = "\033[35m"
ANSI_RESET = "\033[0m"

class ConsoleManager:
    """Manages console output with event-based messaging and reduced noise"""
    
    def __init__(self, timestamp_format="%H:%M:%S"):
        """Initialize the console manager"""
        self.timestamp_format = timestamp_format
        self.last_state = None
        self.last_messages = {}  # Store last message by type to avoid duplicates
        self.message_throttle = {}  # Track message timing for throttling
        self.message_counts = {}  # Track message counts for summary
        
    def _timestamp(self):
        """Get current timestamp string - simplified for CircuitPython"""
        t = time.monotonic()
        # Just show seconds since startup, formatted to 2 decimal places
        return f"{t:.2f}s"
        
    def _should_print(self, message_type, message, throttle_seconds=0):
        """Determine if message should be printed based on throttling"""
        # Generate a key for this message
        key = f"{message_type}:{message}"
        
        # Always print if not seen before
        if key not in self.message_throttle:
            self.message_throttle[key] = time.monotonic()
            self.message_counts[key] = 1
            return True
            
        # Check throttling
        current_time = time.monotonic()
        elapsed = current_time - self.message_throttle[key]
        
        if elapsed >= throttle_seconds:
            self.message_throttle[key] = current_time
            self.message_counts[key] += 1
            return True
            
        # Update count but don't print
        self.message_counts[key] += 1
        return False
        
    def log_event(self, message, message_type="EVENT"):
        """Log a general event (always printed)"""
        ts = self._timestamp()
        print(f"{ANSI_CYAN}[{ts}] {message_type}: {message}{ANSI_RESET}")
        
    def log_state_change(self, old_state, new_state, context=None):
        """Log a state change event"""
        ts = self._timestamp()
        context_str = f" ({context})" if context else ""
        print(f"{ANSI_BLUE}[{ts}] STATE: {old_state} → {new_state}{context_str}{ANSI_RESET}")
        self.last_state = new_state
        
    def log_info(self, message, throttle_seconds=0):
        """Log informational message (throttled if repeated)"""
        if throttle_seconds == 0 or self._should_print("INFO", message, throttle_seconds):
            ts = self._timestamp()
            print(f"{ANSI_GREEN}[{ts}] INFO: {message}{ANSI_RESET}")
            
    def log_warning(self, message, throttle_seconds=60):
        """Log warning message (throttled if repeated)"""
        if self._should_print("WARNING", message, throttle_seconds):
            ts = self._timestamp()
            print(f"{ANSI_YELLOW}[{ts}] WARNING: {message}{ANSI_RESET}")
            
    def log_error(self, message, error_code=None, throttle_seconds=0):
        """Log error message (not throttled by default)"""
        if throttle_seconds == 0 or self._should_print("ERROR", message, throttle_seconds):
            ts = self._timestamp()
            code_str = f"[{error_code}] " if error_code else ""
            print(f"{ANSI_RED}[{ts}] ERROR: {code_str}{message}{ANSI_RESET}")
            
    def log_success(self, message):
        """Log success message (always printed)"""
        ts = self._timestamp()
        print(f"{ANSI_GREEN}[{ts}] SUCCESS: {message}{ANSI_RESET}")
        
    def log_hardware(self, component, status, details=None):
        """Log hardware status message"""
        ts = self._timestamp()
        details_str = f" - {details}" if details else ""
        
        if status == "ONLINE" or status == "ENABLED" or status == "SUCCESS":
            color = ANSI_GREEN
        elif status == "OFFLINE" or status == "DISABLED" or status == "ERROR":
            color = ANSI_RED
        elif status == "FALLBACK":
            color = ANSI_YELLOW
        else:
            color = ANSI_BLUE
            
        print(f"{color}[{ts}] HARDWARE: {component} {status}{details_str}{ANSI_RESET}")
        
    def log_network(self, status, ip_address=None, port=None):
        """Log network status"""
        ts = self._timestamp()
        
        if status == "ONLINE":
            if ip_address:
                addr_str = f"@ {ip_address}"
                if port:
                    addr_str += f":{port}"
                status_str = f"ONLINE {addr_str}"
                
                # For ONLINE status with IP, add a more prominent display
                print(f"{ANSI_GREEN}[{ts}] NETWORK: {status_str}{ANSI_RESET}")
                print(f"{ANSI_GREEN}{'='*50}")
                print(f"DATA LOGGING CONNECTION: {ip_address}:{port}")
                print(f"{'='*50}{ANSI_RESET}")
                return
            else:
                status_str = "ONLINE"
            color = ANSI_GREEN
        else:
            status_str = status
            color = ANSI_RED if status == "ERROR" else ANSI_YELLOW
            
        print(f"{color}[{ts}] NETWORK: {status_str}{ANSI_RESET}")
        
    def log_init(self, component, success, message=None):
        """Log initialization message"""
        ts = self._timestamp()
        
        if success:
            print(f"{ANSI_GREEN}[{ts}] INIT: {component} initialized successfully{ANSI_RESET}")
        else:
            msg = f" - {message}" if message else ""
            print(f"{ANSI_RED}[{ts}] INIT: Failed to initialize {component}{msg}{ANSI_RESET}")
            
    def log_command(self, source, command, response=None):
        """Log command processing"""
        ts = self._timestamp()
        
        # Color code based on command type
        if command.startswith("C:"):
            color = ANSI_MAGENTA  # Control commands
        elif command.startswith("G:"):
            color = ANSI_CYAN     # Get commands
        elif command.startswith("S:"):
            color = ANSI_YELLOW   # Set commands
        else:
            color = ANSI_BLUE     # Other
            
        print(f"{color}[{ts}] CMD: {source} > {command}{ANSI_RESET}")
        
        if response:
            # Color code based on response type
            if response.startswith("ERROR:"):
                resp_color = ANSI_RED
            elif response.startswith("OK:"):
                resp_color = ANSI_GREEN
            else:
                resp_color = ANSI_BLUE
                
            print(f"{resp_color}[{ts}] RESPONSE: {response}{ANSI_RESET}")

# Create global instance
console = ConsoleManager()