from SWDCommon import *
from SWDErrors import *
import sys
import time


class EFM32:
    # AAP registers 
    AAP_CMD = 0x00
    AAP_CMD_DEVICEERASE = 0x01      # when set, all data and program code in the main block is erased
    AAP_CMD_SYSRESETREQ = 0x02      # a system reset request is generated when set to 1
    
    AAP_CMDKEY = 0x04
    AAP_CMDKEY_VALID = 0xCFACC118   # valid key to enable write to AAP_CMD
    
    AAP_STATUS = 0x08
    APP_STATUS_ERASEBUSY = 0x01     # This bit is set when a device erase is executing
    
    IDR = 0xFC
    IDR_EXPECTED = 0x16E60001       # JEDEC Manufacturer ID
    
    EFM32_FAMILY = {71: ["G", "Gecko"],
                    72: ["GG", "Giant Gecko"],
                    73: ["TG", "Tiny Gecko"],
                    74: ["LG", "Leopard Gecko"],
                    75: ["WG", "Wonder Gecko"]}
    
    def __init__ (self, debugPort):
        self.ahb = MEM_AP(debugPort, 0)
        self.debug = debugPort

    #--------------------------------------------------------------------------
    # Cortex M3 stuff

    def halt (self):
        # halt the processor core
        self.ahb.writeWord(0xE000EDF0, 0xA05F0003)

    def unhalt (self):
        # unhalt the processor core
        self.ahb.writeWord(0xE000EDF0, 0xA05F0000)

    def sysReset (self):
        # restart the processor and peripherals
        self.ahb.writeWord(0xE000ED0C, 0x05FA0004)

    #--------------------------------------------------------------------------
    # EFM32-specific stuff

    def flashUnlock (self):
        # unlock main flash
        self.ahb.writeWord(0x400C0000 + 0x008, 0x00000001) # MSC_WRITECTL.WREN <- 1

    #def flashErase (self, flash_size, page_size, offset=0):
    def flashErase(self, offset, length, flashPageSize=0):
        
        start = offset
        end = start + length
        
        # use default flash page size if it's not defined
        if flashPageSize == 0:
            flashPageSize = self.MEM_INFO_PAGE_SIZE
                
        print("Erasing FLASH memory")
        print(" From:      0x{:x}".format(start))
        print(" To:        0x{:x}".format(end))
        print(" Page size: {}B".format(flashPageSize))
        print("")
               
        # erase page by page
        self.ShowProgress(0)
        
        #for i in range(offset, offset+(length * 1024 / flashPageSize)): # page size is 512 or 1024
        for addr in range(start, end, flashPageSize):
            self.ahb.writeWord(0x400C0000 + 0x010, addr)  # MSC_ADDRB <- page address
            self.ahb.writeWord(0x400C0000 + 0x00C, 0x00000001) # MSC_WRITECMD.LADDRIM <- 1
            self.ahb.writeWord(0x400C0000 + 0x00C, 0x00000002) # MSC_WRITECMD.ERASEPAGE <- 1
            while (self.ahb.readWord(0x400C0000 + 0x01C) & 0x1) == 1:
                pass # poll the BUSY bit in MSC_STATUS until it clears
            self.ShowProgress((100.0 * (addr-start)/end))
        
        # erasing complete
        self.ShowProgress(100)


    def flashEraseAll(self, flashPageSize=0):
        '''Erase whole FLASH memory'''
        self.flashErase(0, self.MEM_INFO_FLASH * 1024, flashPageSize)

    def flashProgram(self, offset, firmware):
        # Write each word one by one .... SLOOOW!
        # (don't bother with checking the busy/status bits as this is so slow it's 
        # always ready before we are anyway)
        
        start = offset
        end = start + 4*len(firmware)
        
        print("Programming FLASH memory")
        print(" From:      0x{:x}".format(start))
        print(" To:        0x{:x}".format(end))
        print("")
               
        addr = start
        self.ShowProgress(0)
        
        for i in firmware:
            self.ahb.writeWord(0x400C0000 + 0x010, addr) # MSC_ADDRB <- starting address
            self.ahb.writeWord(0x400C0000 + 0x00C, 0x1)  # MSC_WRITECMD.LADDRIM <- 1
            self.ahb.writeWord(0x400C0000 + 0x018, i)    # MSC_WDATA <- data
            self.ahb.writeWord(0x400C0000 + 0x00C, 0x8)  # MSC_WRITECMD.WRITETRIG <- 1
            self.ShowProgress(100*(addr-start)/end)
            addr += 0x4

        # programming complete
        self.ShowProgress(100)

    def unlockDebug(self, timeout=5):
        '''Unlock EFM32 debug mode
        WARNING: this operation will erase all FLASH memory'''

        sys.stdout.write("Erasing ... ")
        # Write 0xCFACC118 to AAP_CMDKEY to enable writes to AAP_CMD
        self.debug.writeAP(0, self.AAP_CMDKEY, self.AAP_CMDKEY_VALID)
        # Write 1 to the DEVICEERASE bit of AAP_CMD
        self.debug.writeAP(0, self.AAP_CMD, self.AAP_CMD_DEVICEERASE)
        # according to EFM32G Reference Manual APP_CMDKEY must be invalidated to execute the command
        self.debug.writeAP(0, self.AAP_CMDKEY, 0)
        # Check the ERASEBUSY flag in AAP_STATUS to see when the Device Erase operation is complete
        while timeout > 0:
            self.debug.readAP(0, self.AAP_STATUS)
            if self.debug.readRB() != self.APP_STATUS_ERASEBUSY:    # done
                # unlock
                self.debug.writeAP(0, self.AAP_CMDKEY, self.AAP_CMDKEY_VALID)
                # trigger reset
                self.debug.writeAP(0, self.AAP_CMD, self.AAP_CMD_SYSRESETREQ)
                # invalidate
                self.debug.writeAP(0, self.AAP_CMDKEY, 0)
                sys.stdout.write("Done\n")
                return
            else:   # still erasing
                sys.stdout.write(". ")
                time.sleep(0.1)
                timeout -= 0.1
        sys.stdout.write("FAILED!\n")
        raise SWDTimeout("Erase operation timeouted")
    
    def detectType(self):
        '''Detect type of EFM32 microcontroller'''
        
        # read info about uC from Device Information (DI) Page
        value = self.ahb.readWord(0x0FE081E4)
        self.MEM_INFO_PAGE_SIZE = 2**(((value >> 24 & 0xFF) + 10) & 0xFF) 
        
        self.UNIQUE_0 = self.ahb.readWord(0x0FE081F0)
        self.UNIQUE_1 = self.ahb.readWord(0x0FE081F4)
        
        value = self.ahb.readWord(0x0FE081F8)
        self.MEM_INFO_FLASH = value & 0xFFFF
        self.MEM_INFO_RAM = value >> 16 & 0xFFFF
        
        value = self.ahb.readWord(0x0FE081FC)
        self.PART_NUMBER = value & 0xFFFF
        self.PART_FAMILY = value >> 16 & 0xFF
        self.PROD_REV = value >> 24 & 0xFF
        
        # could be that EFM32 is locked
        if self.PART_FAMILY == 0:
            raise SWDInitError("Can't read information about connected EFM32. Please check if debug is not locked.")
        
        # print info about recognized uC
        if self.PART_FAMILY in self.EFM32_FAMILY.keys():
            print("{0:<20} EFM32{1:}{2:}F{3:} ({4:})".format("Part Number:", self.EFM32_FAMILY[self.PART_FAMILY][0], 
                                                                             self.PART_NUMBER, 
                                                                             self.MEM_INFO_FLASH,
                                                                             self.EFM32_FAMILY[self.PART_FAMILY][1]))
        else:
            print("{0:<20} {1:}".format("Part Family:", self.PART_FAMILY))
            print("{0:<20} {1:}".format("Part Number:", self.PART_NUMBER))

        print("{0:<20} {1} kB".format("FLASH memory size:", self.MEM_INFO_FLASH))
        print("{0:<20} {1} B".format("FLASH page size:", self.MEM_INFO_PAGE_SIZE))
                        
        print("{0:<20} {1} kB".format("RAM size:", self.MEM_INFO_RAM))
        print("{0:<20} {1}".format("Production ID:", self.PROD_REV))
        print("{0:<20} {1:x}{2:x}".format("Unique number:", self.UNIQUE_1, self.UNIQUE_0))


    def ShowProgress(self, progress):
        sys.stdout.write("\b" * 17)
        sys.stdout.write("Progress: %5.1f %%" % progress)
        if progress == 100.0:
            sys.stdout.write("\n")
        sys.stdout.flush()
