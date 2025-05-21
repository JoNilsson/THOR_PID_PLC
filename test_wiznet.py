"""
Simple test script to verify WIZnet5k imports work correctly
"""

print("Starting WIZnet5k test")

# Try to import libraries
try:
    print("Importing WIZnet5k libraries...")
    from adafruit_wiznet5k.adafruit_wiznet5k import WIZNET5K
    import adafruit_wiznet5k.adafruit_wiznet5k_socketpool as socketpool
    print("✓ WIZnet5k libraries imported successfully!")
    print(f"  WIZNET5K module: {WIZNET5K}")
    print(f"  socketpool module: {socketpool}")
    print(f"  socketpool.SocketPool class: {socketpool.SocketPool}")
except ImportError as e:
    print(f"✗ Import error: {e}")
    
print("Test complete")