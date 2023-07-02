## Contents

## - `hotclasps_circuitpy_8_1_0.uf2`
This is the "officially" supported build of CircuitPython that runs on the HotClasps cartridge. It is based off of the `8.1.0` release, and simply adds a board definition with proper pin names and USB ids for this device.

## - `code.py`
The firmware for this device, which runs on the build of CircuitPython above. 
### **Notes:**
* This build expects audio files to be converted into the [`.htclp`](https://www.hotclasps.com/upload) format and loaded into a directory named `sounds`.
* CircuitPython dependencies:
    * [adafruit_pioasm](https://github.com/adafruit/Adafruit_CircuitPython_PIOASM)
    * [adafruit_ticks](https://github.com/adafruit/Adafruit_CircuitPython_Ticks)
    * [asyncio](https://github.com/adafruit/Adafruit_CircuitPython_asyncio)