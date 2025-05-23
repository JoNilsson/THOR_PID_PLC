# Simple Peer-to-Peer Network Setup

## Quick Start

The P1AM is configured for **zero-configuration** peer-to-peer networking:

**P1AM Address: `169.254.100.100` (port 23)**

## Connecting Your Computer

### Easiest Method (Automatic):
1. Connect P1AM and PC to the switch (or directly with a cable)
2. Wait ~30 seconds for your PC to auto-assign a 169.254.x.x address
3. Connect: `telnet 169.254.100.100 23`

### If Automatic Doesn't Work:

**Windows (Command Prompt as Admin):**
```cmd
netsh interface ip set address "Ethernet" static 169.254.100.101 255.255.0.0
```

**Linux:**
```bash
sudo ip addr add 169.254.100.101/16 dev eth0
```

**macOS:**
```bash
sudo ifconfig en0 inet 169.254.100.101 netmask 255.255.0.0
```

## Testing
```bash
ping 169.254.100.100
telnet 169.254.100.100 23
```

## Why This Works

- **169.254.x.x** addresses are specifically for device-to-device connections
- No router, DHCP server, or configuration needed
- Most operating systems handle this automatically
- Works with any switch or direct cable connection

## Reverting Changes

To restore automatic DHCP on your PC:

**Windows:** 
```cmd
netsh interface ip set address "Ethernet" dhcp
```

**Linux:** 
```bash
sudo ip addr del 169.254.100.101/16 dev eth0
```

**macOS:** System Preferences → Network → Configure IPv4 → Using DHCP