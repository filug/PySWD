Pirate-SWD
----------

This is a basic implementation of the SWD protocol using the Bus Pirate.

The 'PirateSWD', 'DebugPort' and 'MEM_AP' classes should be portable to
all ARM chips supporting the SWD protocol.

Also included is a 'STM32' class, which encapsulates some basic operations
on the STM32 microcontroller, allowing it to be halted and reset, and the
flash memory programmed with a sequence of words.

There are some example firmware files for the STM32VLDISCOVERY board, as
I mainly developed this code so I could program mine from Linux without
bothering with the embedded bootloader.

UPDATES:
* Added 6/7/2011 by hugovincent: Energy Micro EFM32 support.
* Added 16/3/2015 by filug: Extended feature set for EFM32
