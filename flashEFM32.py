#!/usr/bin/env python

# EFM32 controller
# modified by Piotr L. Figlarek (piotr.figlarek@gmail.com)

import time
import sys
import array
from optparse import OptionParser

from PirateSWD import *
from SWDCommon import *
from EFM32 import *

def loadFile(path):
    arr = array.array('I')
    try:
        arr.fromfile(open(path, 'rb'), 1024*1024)
    except EOFError:
        pass
    return arr.tolist()

def main():
        
    parser = OptionParser(version="1.0", add_help_option=False)
    parser.add_option("-p", "--port",
                      action="store", type="string", dest="port", default=None,
                      help="Bus Pirate serial port (if not defined Bus Pirate will be detected automatically)")
    parser.add_option("-f", "--file",
                      action="store", type="string", dest="file", default=None,
                      help="name of binary image file")
    parser.add_option("-u", "--unlock",
                      action="store_true", dest="unlock", 
                      help="unlock debug mode")
    parser.add_option("-o", "--offset",
                      action="store", type="int", dest="offset", default=0,
                      help="program FLASH memory with provided offset")
    parser.add_option("", "--eraseall",
                      action="store_true", dest="eraseall", 
                      help="erase all FLASH memory")
    parser.add_option("", "--pagesize",
                      action="store", type="int", dest="flashpagesize", default=0, 
                      help="use following value for flash page size (ignore value read from EFM32)")
    parser.add_option("", "--noreset",
                      action="store_false", dest="reset", default=True,
                      help="don't reset EFM32 on exit")
    parser.add_option("-h", "--help",
                      action="store_true", dest="help", 
                      help="show this help")
    
    (options, args) = parser.parse_args()
    
    # show help 
    if options.help:
        parser.print_help()
        print("")
        print("Please connect your Bus Pirate to the EFM32 in this way:\n\n" \
              " +------------+        +-------------+ \n" \
              " | Bus Pirate |        |   EFM32*    | \n" \
              " +------------+        +-------------+ \n" \
              " |       MOSI |<------>| SWDIO (PF1) | \n" \
              " |        CLK |------->| SWCLK (PF0) | \n" \
              " +------------+        +-------------+ \n\n" \
              "This script is executing following scenario:\n" \
              " 1. unlocking debug mode (if selected),\n" \
              " 2. detecting type of EFM32 microcontroller,\n" \
              " 3. erasing FLASH memory (if file with firmware is provided),\n" \
              " 4. programming FLASH memory (if file with firmware is provided).\n")
        exit(0)
    
    try:
        # connect with EFM32 through Bus Pirate    
        busPirate = PirateSWD(options.port, vreg = True)
        debugPort = DebugPort(busPirate)
        efm32 = EFM32(debugPort)

        # unclocking EFM32 debug
        if options.unlock:
            print("--== Step 1: Unlocking debug mode ==--")
            efm32.unlockDebug()
            time.sleep(1)
        else:
            print("--== Step 1: Unlocking debug mode (SKIPPED) ==--")
        print("")
        
        
        # detect type of EFM32
        print("--== Step 2: Detecting microcontroller ==--")
        efm32.detectType()
        print("")
        
        # erase all memory if requested
        if options.eraseall:
            print("--== Step 3: Erasing FLASH memory (all) ==--")
            efm32.halt()
            efm32.flashUnlock()
            efm32.flashEraseAll(options.flashpagesize)
        elif options.file:
            print("--== Step 3: Erasing FLASH memory (needed by firmware) ==--")
            firmware = loadFile(options.file)
            length = len(firmware) * 4
            
            efm32.halt()
            efm32.flashUnlock()            
            efm32.flashErase(options.offset, length, options.flashpagesize)
        else:
            print("--== Step 3: Erasing FLASH memory (SKIPPED) ==--")
        print("")
            
        # otherwise erase only this what is needed
        if options.file:
            print("--== Step 4: Programming FLASH memory ==--")
            firmware = loadFile(options.file)
            efm32.flashProgram(options.offset, firmware)
        else:
            print("--== Step 4: Programming FLASH memory (SKIPPED) ==--")
        print("")
        
        # reset if possible
        if options.reset:
            efm32.sysReset()

    except Exception as e:
        sys.stderr.write("Terminated!\n")
        sys.stderr.write("Exception: {}\n".format(e))
        exit(1)
    finally:
        try:
            busPirate.tristatePins()    
        except: pass
        exit()



if __name__ == "__main__":
    main()
