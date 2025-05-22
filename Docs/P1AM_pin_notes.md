# P1AM MKR PIN Descriptions

The following is from the manufacture data-sheets for the various P1AM shields utilized in the THOR
SiC heater control system.

## MKR Expansion Bus Pins

| Pin Type           | Pins                   |
| ------------------ | ---------------------- |
| GPIO               | A0–A6, 0–14            |
| Analog Input Pins  | A0–A6                  |
| Analog Output Pins | A0                     |
| PWM Pins           | 0–8, 10, A3, A4        |
| Interrupt Pins     | 0, 1, 4–8, A1, A2      |
| SV                 | 5V supply output       |
| Vin                | 5V regulated supply    |
| VCC                | 3.3V supply output     |
| GND                | Ground                 |
| RST                | Reset                  |
| AREF               | Analog Input Reference |

**Critical Integration Notes:**

- Pins A3, A4, and 8–10 are used for the base controller!

### Header Pins Used for Serial Shield

| Pin | Function | Description                            |
| --- | -------- | -------------------------------------- |
| 3   | P1 Mode  | Port 1 Mode (Low=RS485 High=RS232)     |
| 14  | P1 TX-   | Port 1 Data –                          |
| 13  | P1 RX+   | Port 1 Data +                          |
| A6  | P1 DE/RE | Port 1 Driver Enable / Receiver Enable |
| 2   | P2 Mode  | Port 2 Mode (Low=RS485, High=RS232)    |
| 0   | P2 TX-   | Port 2 Data –                          |
| 1   | P2 RX+   | Port 2 Data +                          |
| 6   | P2 DE/RE | Port 2 Driver Enable / Receiver Enable |

**Note: The P1AM-GPIO module is installed alongside a P1AM-SERIAL module,  
as a result the above pins are unavailable to the P1AM-GPIO!**

### Header Pins Used for Ethernet Shield

| Pins | Function | Description                                       |
| ---- | -------- | ------------------------------------------------- |
| 5    | ETH SS   |                                                   |
| 8    | MOSI     |                                                   |
| 9    | SCK      | SPI pins are shared with other devices on SPI bus |
| 10   | MISO     |                                                   |

**Implementation Notes: GPIO PIN 0 was previously used for the Blower Monitor signal,
this has been moved to the P1-15CDD1 module, on pin C1-4 (physical pin 5 of the module),
The functional principal is the same however, when the blower is energized,the
current sensing NO-SSR will close, and deliver a path to ground on pin C1-4.  
We need to update code to implement this schematic change. This will free up
GPIO pins which are in short supply. Use this table as a source of truth for pin
assignments, and refactor the codebase to use these pin assignments, to remove any
existing conflicts, and avoid them in the future. -Johanness Nilsson 5/22/2025**
