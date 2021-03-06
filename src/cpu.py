import numpy as np

class CPU:
    def __init__(self, mmu):
        self.regs = {
            'A': 0x00,
            'B': 0x00,
            'C': 0x00,
            'D': 0x00,
            'E': 0x00,
            'F': 0x00,
            'H': 0x00,
            'L': 0x00
        }

        self.sp = 0xFFFE
        self.pc = 0x0100
        self.interrupt_master_enable = False

        self.mmu = mmu

    def get_reg_8(self, reg):
        return self.regs[reg]

    def set_reg_8(self, reg, val):
        self.regs[reg] = val

    def get_reg_16(self, reg):
        if (reg == 'AF'):
            return (self.regs['A'] << 8) | self.regs['F']
        elif (reg == 'BC'):
            return (self.regs['B'] << 8) | self.regs['C']
        elif (reg == 'DE'):
            return (self.regs['D'] << 8) | self.regs['E']
        elif (reg == 'HL'):
            return (self.regs['H'] << 8) | self.regs['L']
        elif (reg == 'SP'):
            return self.sp
        elif (reg == 'PC'):
            return self.pc

    def set_reg_16(self, reg, val):
        if (reg == 'AF'):
            self.regs['A'] = (val & 0xFF00) >> 8
            self.regs['F'] = val & 0x00FF
        elif (reg == 'BC'):
            self.regs['B'] = (val & 0xFF00) >> 8
            self.regs['C'] = val & 0x00FF
        elif (reg == 'DE'):
            self.regs['D'] = (val & 0xFF00) >> 8
            self.regs['E'] = val & 0x00FF
        elif (reg == 'HL'):
            self.regs['H'] = (val & 0xFF00) >> 8
            self.regs['L'] = val & 0x00FF
        elif (reg == 'SP'):
            self.sp = val
        elif (reg == 'PC'):
            self.pc = val

    def fetch_8(self):
        val = self.mmu.get(self.pc)
        self.pc = self.pc + 1
        return val

    def fetch_16(self):
        val1 = self.mmu.get(self.pc)
        val2 = self.mmu.get(self.pc + 1)
        self.pc = self.pc + 2
        val = (val2 << 8) | val1 # Least sig byte popped first, might be wrong
        return val

    def get_flag(self, flag):
        if (flag == 'Z'):
            return (self.get_reg_8('F') & 0b10000000) >> 7
        elif (flag == 'N'):
            return (self.get_reg_8('F') & 0b01000000) >> 6
        elif (flag == 'H'):
            return (self.get_reg_8('F') & 0b00100000) >> 5
        elif (flag == 'C'):
            return (self.get_reg_8('F') & 0b00010000) >> 4
        else:
            raise NotImplementedError('Unknown flag get: ' + flag)

    def set_flag(self, flag, val):
        if (flag == 'Z'):
            self.set_reg_8('F', self.get_reg_8('F') & 0b01111111 | (val << 7))
        elif (flag == 'N'):
            self.set_reg_8('F', self.get_reg_8('F') & 0b10111111 | (val << 6))
        elif (flag == 'H'):
            self.set_reg_8('F', self.get_reg_8('F') & 0b11011111 | (val << 5))
        elif (flag == 'C'):
            self.set_reg_8('F', self.get_reg_8('F') & 0b11101111 | (val << 4))
        else:
            raise NotImplementedError('Unknown flag set: ' + flag)

    def push_stack(self, addr):
        SP = self.get_reg_16('SP')
        self.mmu.set(SP - 1, (addr & 0xFF00) >> 8)
        self.mmu.set(SP - 2, (addr & 0xFF))
        self.set_reg_16('SP', SP - 2)

    def pop_stack(self):
        SP = self.get_reg_16('SP')
        lo = self.mmu.get(SP)
        hi = self.mmu.get(SP + 1)
        self.set_reg_16('SP', SP + 2)
        return (hi << 8) | lo

    def add_8(self, val1, val2, use_carry = False):
        total = (int(val1) + int(val2) + int(use_carry))
        wrappedTotal = total % 0x100
        self.set_flag('Z', int(wrappedTotal == 0))
        self.set_flag('N', 0)
        self.set_flag('H', int((val1 & 0x0F) + (val2 & 0x0F) + (int(use_carry) & 0x0F) > 0x0F))
        self.set_flag('C', int(total > 0xFF))
        return wrappedTotal

    def add_16(self, val1, val2, use_carry = False):
        total = (int(val1) + int(val2) + int(use_carry))
        wrappedTotal = total % 0x10000
        self.set_flag('Z', int(wrappedTotal == 0))
        self.set_flag('N', 0)
        self.set_flag('H', int((val1 & 0xFFF) + (val2 & 0xFFF) + (int(use_carry) & 0x0FFF) > 0x0FFF))
        self.set_flag('C', int(total > 0xFFFF))
        return wrappedTotal

    def sub_8(self, val1, val2, use_carry = False):
        total = (int(val1) - int(val2) - int(use_carry))
        wrappedTotal = total % 0x100
        self.set_flag('Z', int(wrappedTotal == 0))
        self.set_flag('N', 1)
        self.set_flag('H', int((val1 & 0xF) < ((val2 & 0xF) + int(use_carry))))
        self.set_flag('C', int(total < 0x00))
        return wrappedTotal

    def sub_16(self, val1, val2, use_carry = False):
        total = (int(val1) - int(val2) - int(use_carry))
        wrappedTotal = total % 0x10000
        self.set_flag('Z', int(wrappedTotal == 0))
        self.set_flag('N', 1)
        self.set_flag('H', int((val1 & 0xFFF) < ((val2 & 0xFFF) + int(use_carry))))
        self.set_flag('C', int(total < 0x0000))
        return wrappedTotal

    def tick(self):
        op = self.fetch_8()
        self.execute(op)
        self.handle_interrupts()

    def execute(self, op):
        ## 8-bit loads
        # LD nn, n
        if (op == 0x06):
            n = self.fetch_8()
            self.LD_nn_n('B', n)
        elif (op == 0x0E):
            n = self.fetch_8()
            self.LD_nn_n('C', n)
        elif (op == 0x16):
            n = self.fetch_8()
            self.LD_nn_n('D', n)
        elif (op == 0x1E):
            n = self.fetch_8()
            self.LD_nn_n('E', n)
        elif (op == 0x26):
            n = self.fetch_8()
            self.LD_nn_n('H', n)
        elif (op == 0x2E):
            n = self.fetch_8()
            self.LD_nn_n('L', n)

        # LD r1, r2
        elif (op == 0x7F):
            self.LD_r1_r2('A', 'A')
        elif (op == 0x78):
            self.LD_r1_r2('A', 'B')
        elif (op == 0x79):
            self.LD_r1_r2('A', 'C')
        elif (op == 0x7A):
            self.LD_r1_r2('A', 'D')
        elif (op == 0x7B):
            self.LD_r1_r2('A', 'E')
        elif (op == 0x7C):
            self.LD_r1_r2('A', 'H')
        elif (op == 0x7D):
            self.LD_r1_r2('A', 'L')
        elif (op == 0x40):
            self.LD_r1_r2('B', 'B')
        elif (op == 0x41):
            self.LD_r1_r2('B', 'C')
        elif (op == 0x42):
            self.LD_r1_r2('B', 'D')
        elif (op == 0x43):
            self.LD_r1_r2('B', 'E')
        elif (op == 0x44):
            self.LD_r1_r2('B', 'H')
        elif (op == 0x45):
            self.LD_r1_r2('B', 'L')
        elif (op == 0x48):
            self.LD_r1_r2('C', 'B')
        elif (op == 0x49):
            self.LD_r1_r2('C', 'C')
        elif (op == 0x4A):
            self.LD_r1_r2('C', 'D')
        elif (op == 0x4B):
            self.LD_r1_r2('C', 'E')
        elif (op == 0x4C):
            self.LD_r1_r2('C', 'H')
        elif (op == 0x4D):
            self.LD_r1_r2('C', 'L')
        elif (op == 0x50):
            self.LD_r1_r2('D', 'B')
        elif (op == 0x51):
            self.LD_r1_r2('D', 'C')
        elif (op == 0x52):
            self.LD_r1_r2('D', 'D')
        elif (op == 0x53):
            self.LD_r1_r2('D', 'E')
        elif (op == 0x54):
            self.LD_r1_r2('D', 'H')
        elif (op == 0x55):
            self.LD_r1_r2('D', 'L')
        elif (op == 0x58):
            self.LD_r1_r2('E', 'B')
        elif (op == 0x59):
            self.LD_r1_r2('E', 'C')
        elif (op == 0x5A):
            self.LD_r1_r2('E', 'D')
        elif (op == 0x5B):
            self.LD_r1_r2('E', 'E')
        elif (op == 0x5C):
            self.LD_r1_r2('E', 'H')
        elif (op == 0x5D):
            self.LD_r1_r2('E', 'L')
        elif (op == 0x60):
            self.LD_r1_r2('H', 'B')
        elif (op == 0x61):
            self.LD_r1_r2('H', 'C')
        elif (op == 0x62):
            self.LD_r1_r2('H', 'D')
        elif (op == 0x63):
            self.LD_r1_r2('H', 'E')
        elif (op == 0x64):
            self.LD_r1_r2('H', 'H')
        elif (op == 0x65):
            self.LD_r1_r2('H', 'L')
        elif (op == 0x68):
            self.LD_r1_r2('L', 'B')
        elif (op == 0x69):
            self.LD_r1_r2('L', 'C')
        elif (op == 0x6A):
            self.LD_r1_r2('L', 'D')
        elif (op == 0x6B):
            self.LD_r1_r2('L', 'E')
        elif (op == 0x6C):
            self.LD_r1_r2('L', 'H')
        elif (op == 0x6D):
            self.LD_r1_r2('L', 'L')

        # LD r, (HL)   #Technically part of LD r1, r2
        elif (op == 0x7E):
            self.LD_r_HL('A')
        elif (op == 0x46):
            self.LD_r_HL('B')
        elif (op == 0x4E):
            self.LD_r_HL('C')
        elif (op == 0x56):
            self.LD_r_HL('D')
        elif (op == 0x5E):
            self.LD_r_HL('E')
        elif (op == 0x66):
            self.LD_r_HL('H')
        elif (op == 0x6E):
            self.LD_r_HL('L')

        # LD (HL), r   #Technically part of LD r1, r2
        elif (op == 0x70):
            self.LD_HL_r('B')
        elif (op == 0x71):
            self.LD_HL_r('C')
        elif (op == 0x72):
            self.LD_HL_r('D')
        elif (op == 0x73):
            self.LD_HL_r('E')
        elif (op == 0x74):
            self.LD_HL_r('H')
        elif (op == 0x75):
            self.LD_HL_r('L')

        # LD (HL), n   #Technically part of LD r1, r2
        elif (op == 0x36):
            self.LD_HL_n()

        # LD A, n
        elif (op == 0x0A):
            self.LD_A_rr('BC')
        elif (op == 0x1A):
            self.LD_A_rr('DE')
        elif (op == 0x7E):
            self.LD_A_rr('HL')
        elif (op == 0xFA):
            self.LD_A_nn()
        elif (op == 0x3E):
            self.LD_A_n()

        # LD n, A
        elif (op == 0x47):
            self.LD_n_A('B')
        elif (op == 0x4F):
            self.LD_n_A('C')
        elif (op == 0x57):
            self.LD_n_A('D')
        elif (op == 0x5F):
            self.LD_n_A('E')
        elif (op == 0x67):
            self.LD_n_A('H')
        elif (op == 0x6F):
            self.LD_n_A('L')
        elif (op == 0x02):
            self.LD_rr_A('BC')
        elif (op == 0x12):
            self.LD_rr_A('DE')
        elif (op == 0x77):
            self.LD_rr_A('HL')
        elif (op == 0xEA):
            self.LD_nn_A()

        # LD A,C & LD C, A
        elif (op == 0xF2):
            self.LD_A_C()
        elif (op == 0xE2):
            self.LD_C_A()

        # LDD & LDI
        elif (op == 0x3A):
            self.LDD_A_HL()
        elif (op == 0x32):
            self.LDD_HL_A()
        elif (op == 0x2A):
            self.LDI_A_HL()
        elif (op == 0x22):
            self.LDI_HL_A()

        # LDH
        elif (op == 0xE0):
            self.LDH_n_A()
        elif (op == 0xF0):
            self.LDH_A_n()

        ## 16-bit loads
        # LD n, nn
        elif (op == 0x01):
            self.LD_n_nn('BC')
        elif (op == 0x11):
            self.LD_n_nn('DE')
        elif (op == 0x21):
            self.LD_n_nn('HL')
        elif (op == 0x31):
            self.LD_n_nn('SP')

        # LD SP
        elif (op == 0xF9):
            self.LD_SP_HL()
        elif (op == 0xF8):
            self.LD_HL_SPn()
        elif (op == 0x08):
            self.LD_nn_SP()

        # Stack
        elif (op == 0xF5):
            self.PUSH_nn('AF')
        elif (op == 0xC5):
            self.PUSH_nn('BC')
        elif (op == 0xD5):
            self.PUSH_nn('DE')
        elif (op == 0xE5):
            self.PUSH_nn('HL')
        elif (op == 0xF1):
            self.POP_nn('AF')
        elif (op == 0xC1):
            self.POP_nn('BC')
        elif (op == 0xD1):
            self.POP_nn('DE')
        elif (op == 0xE1):
            self.POP_nn('HL')

        ## 8-bit ALU
        # Addition
        elif (op == 0x87):
            self.ADD_A_r('A')
        elif (op == 0x80):
            self.ADD_A_r('B')
        elif (op == 0x81):
            self.ADD_A_r('C')
        elif (op == 0x82):
            self.ADD_A_r('D')
        elif (op == 0x83):
            self.ADD_A_r('E')
        elif (op == 0x84):
            self.ADD_A_r('H')
        elif (op == 0x85):
            self.ADD_A_r('L')
        elif (op == 0x86):
            self.ADD_A_HL()
        elif (op == 0xC6):
            self.ADD_A_n()
        elif (op == 0x8F):
            self.ADC_A_r('A')
        elif (op == 0x88):
            self.ADC_A_r('B')
        elif (op == 0x89):
            self.ADC_A_r('C')
        elif (op == 0x8A):
            self.ADC_A_r('D')
        elif (op == 0x8B):
            self.ADC_A_r('E')
        elif (op == 0x8C):
            self.ADC_A_r('H')
        elif (op == 0x8D):
            self.ADC_A_r('L')
        elif (op == 0x8E):
            self.ADC_A_HL()
        elif (op == 0xCE):
            self.ADC_A_n()

        # Subtraction
        elif (op == 0x97):
            self.SUB_A_r('A')
        elif (op == 0x90):
            self.SUB_A_r('B')
        elif (op == 0x91):
            self.SUB_A_r('C')
        elif (op == 0x92):
            self.SUB_A_r('D')
        elif (op == 0x93):
            self.SUB_A_r('E')
        elif (op == 0x94):
            self.SUB_A_r('H')
        elif (op == 0x95):
            self.SUB_A_r('L')
        elif (op == 0x96):
            self.SUB_A_HL()
        elif (op == 0xD6):
            self.SUB_A_n()
        elif (op == 0x9F):
            self.SBC_A_r('A')
        elif (op == 0x98):
            self.SBC_A_r('B')
        elif (op == 0x99):
            self.SBC_A_r('C')
        elif (op == 0x9A):
            self.SBC_A_r('D')
        elif (op == 0x9B):
            self.SBC_A_r('E')
        elif (op == 0x9C):
            self.SBC_A_r('H')
        elif (op == 0x9D):
            self.SBC_A_r('L')
        elif (op == 0x9E):
            self.SBC_A_HL()
        elif (op == 0xDE):
            self.SBC_A_n()

        # AND/OR/XOR
        elif (op == 0xA7):
            self.AND_r('A')
        elif (op == 0xA0):
            self.AND_r('B')
        elif (op == 0xA1):
            self.AND_r('C')
        elif (op == 0xA2):
            self.AND_r('D')
        elif (op == 0xA3):
            self.AND_r('E')
        elif (op == 0xA4):
            self.AND_r('H')
        elif (op == 0xA5):
            self.AND_r('L')
        elif (op == 0xA6):
            self.AND_HL()
        elif (op == 0xE6):
            self.AND_n()
        elif (op == 0xB7):
            self.OR_r('A')
        elif (op == 0xB0):
            self.OR_r('B')
        elif (op == 0xB1):
            self.OR_r('C')
        elif (op == 0xB2):
            self.OR_r('D')
        elif (op == 0xB3):
            self.OR_r('E')
        elif (op == 0xB4):
            self.OR_r('H')
        elif (op == 0xB5):
            self.OR_r('L')
        elif (op == 0xB6):
            self.OR_HL()
        elif (op == 0xF6):
            self.OR_n()
        elif (op == 0xAF):
            self.XOR_r('A')
        elif (op == 0xA8):
            self.XOR_r('B')
        elif (op == 0xA9):
            self.XOR_r('C')
        elif (op == 0xAA):
            self.XOR_r('D')
        elif (op == 0xAB):
            self.XOR_r('E')
        elif (op == 0xAC):
            self.XOR_r('H')
        elif (op == 0xAD):
            self.XOR_r('L')
        elif (op == 0xAE):
            self.XOR_HL()
        elif (op == 0xEE):
            self.XOR_n()
        elif (op == 0xBF):
            self.CP_r('A')
        elif (op == 0xB8):
            self.CP_r('B')
        elif (op == 0xB9):
            self.CP_r('C')
        elif (op == 0xBA):
            self.CP_r('D')
        elif (op == 0xBB):
            self.CP_r('E')
        elif (op == 0xBC):
            self.CP_r('H')
        elif (op == 0xBD):
            self.CP_r('L')
        elif (op == 0xBE):
            self.CP_HL()
        elif (op == 0xFE):
            self.CP_n()
        elif (op == 0x3C):
            self.INC_r('A')
        elif (op == 0x04):
            self.INC_r('B')
        elif (op == 0x0C):
            self.INC_r('C')
        elif (op == 0x14):
            self.INC_r('D')
        elif (op == 0x1C):
            self.INC_r('E')
        elif (op == 0x24):
            self.INC_r('H')
        elif (op == 0x2C):
            self.INC_r('L')
        elif (op == 0x34):
            self.INC_HL()
        elif (op == 0x3D):
            self.DEC_r('A')
        elif (op == 0x05):
            self.DEC_r('B')
        elif (op == 0x0D):
            self.DEC_r('C')
        elif (op == 0x15):
            self.DEC_r('D')
        elif (op == 0x1D):
            self.DEC_r('E')
        elif (op == 0x25):
            self.DEC_r('H')
        elif (op == 0x2D):
            self.DEC_r('L')
        elif (op == 0x35):
            self.DEC_HL()

        ## 16-bit ALU
        elif (op == 0x09):
            self.ADD_HL_n('BC')
        elif (op == 0x19):
            self.ADD_HL_n('DE')
        elif (op == 0x29):
            self.ADD_HL_n('HL')
        elif (op == 0x39):
            self.ADD_HL_n('SP')
        elif (op == 0xE8):
            self.ADD_SP_n()
        elif (op == 0x03):
            self.INC_nn('BC')
        elif (op == 0x13):
            self.INC_nn('DE')
        elif (op == 0x23):
            self.INC_nn('HL')
        elif (op == 0x33):
            self.INC_nn('SP')
        elif (op == 0x0B):
            self.DEC_nn('BC')
        elif (op == 0x1B):
            self.DEC_nn('DE')
        elif (op == 0x2B):
            self.DEC_nn('HL')
        elif (op == 0x3B):
            self.DEC_nn('SP')

        # Misc
        elif (op == 0x27):
            self.DAA()
        elif (op == 0x2F):
            self.CPL()
        elif (op == 0x3F):
            self.CCF()
        elif (op == 0x37):
            self.SCF()

        # Rotates & shifts
        elif (op == 0x07):
            self.RLCA()
        elif (op == 0x17):
            self.RLA()
        elif (op == 0x0F):
            self.RRCA()
        elif (op == 0x1F):
            self.RRA()

        # Control flow
        # TODO: Sort out interrupts and the likes
        elif (op == 0x00):
            self.NOP()
        elif (op == 0x76):
            self.HALT()
        elif (op == 0x10):
            op2 = self.fetch_8()
            if (op2 == 0x00):
                self.STOP()
        elif (op == 0xF3):
            self.DI()
        elif (op == 0xFB):
            self.EI()

        # Jumps
        elif (op == 0xC3):
            self.JP_nn()
        elif (op == 0xC2):
            self.JP_NZ()
        elif (op == 0xCA):
            self.JP_Z()
        elif (op == 0xD2):
            self.JP_NC()
        elif (op == 0xDA):
            self.JP_C()
        elif (op == 0xE9):
            self.JP_HL()
        elif (op == 0x18):
            self.JR_n()
        elif (op == 0x20):
            self.JR_NZ()
        elif (op == 0x28):
            self.JR_Z()
        elif (op == 0x30):
            self.JR_NC()
        elif (op == 0x38):
            self.JR_C()

        # Calls
        elif (op == 0xCD):
            self.CALL_nn()
        elif (op == 0xC4):
            self.CALL_NZ()
        elif (op == 0xCC):
            self.CALL_Z()
        elif (op == 0xD4):
            self.CALL_NC()
        elif (op == 0xDC):
            self.CALL_C()

        # Restarts
        elif (op == 0xC7):
            self.RST(0x00)
        elif (op == 0xCF):
            self.RST(0x08)
        elif (op == 0xD7):
            self.RST(0x10)
        elif (op == 0xDF):
            self.RST(0x18)
        elif (op == 0xE7):
            self.RST(0x20)
        elif (op == 0xEF):
            self.RST(0x28)
        elif (op == 0xF7):
            self.RST(0x30)
        elif (op == 0xFF):
            self.RST(0x38)

        # Returns
        elif (op == 0xC9):
            self.RET()
        elif (op == 0xC0):
            self.RET_NZ()
        elif (op == 0xC8):
            self.RET_Z()
        elif (op == 0xD0):
            self.RET_NC()
        elif (op == 0xD8):
            self.RET_C()
        elif (op == 0xD9):
            self.RETI()

        # Extended operations:
        elif (op == 0xCB):
            op2 = self.fetch_8()

            # Swaps
            if (op2 == 0x37):
                self.SWAP_r('A')
            elif (op2 == 0x30):
                self.SWAP_r('B')
            elif (op2 == 0x31):
                self.SWAP_r('C')
            elif (op2 == 0x32):
                self.SWAP_r('D')
            elif (op2 == 0x33):
                self.SWAP_r('E')
            elif (op2 == 0x34):
                self.SWAP_r('H')
            elif (op2 == 0x35):
                self.SWAP_r('L')
            elif (op2 == 0x36):
                self.SWAP_HL()

            # Rotates
            elif (op2 == 0x07):
                self.RLC_n('A')
            elif (op2 == 0x00):
                self.RLC_n('B')
            elif (op2 == 0x01):
                self.RLC_n('C')
            elif (op2 == 0x02):
                self.RLC_n('D')
            elif (op2 == 0x03):
                self.RLC_n('E')
            elif (op2 == 0x04):
                self.RLC_n('H')
            elif (op2 == 0x05):
                self.RLC_n('L')
            elif (op2 == 0x17):
                self.RL_n('A')
            elif (op2 == 0x10):
                self.RL_n('B')
            elif (op2 == 0x11):
                self.RL_n('C')
            elif (op2 == 0x12):
                self.RL_n('D')
            elif (op2 == 0x13):
                self.RL_n('E')
            elif (op2 == 0x14):
                self.RL_n('H')
            elif (op2 == 0x15):
                self.RL_n('L')
            elif (op2 == 0x0F):
                self.RRC_n('A')
            elif (op2 == 0x08):
                self.RRC_n('B')
            elif (op2 == 0x09):
                self.RRC_n('C')
            elif (op2 == 0x0A):
                self.RRC_n('D')
            elif (op2 == 0x0B):
                self.RRC_n('E')
            elif (op2 == 0x0C):
                self.RRC_n('H')
            elif (op2 == 0x0D):
                self.RRC_n('L')
            elif (op2 == 0x1F):
                self.RR_n('A')
            elif (op2 == 0x18):
                self.RR_n('B')
            elif (op2 == 0x19):
                self.RR_n('C')
            elif (op2 == 0x1A):
                self.RR_n('D')
            elif (op2 == 0x1B):
                self.RR_n('E')
            elif (op2 == 0x1C):
                self.RR_n('H')
            elif (op2 == 0x1D):
                self.RR_n('L')
            elif (op2 == 0x06):
                self.RLC_HL()
            elif (op2 == 0x16):
                self.RL_HL()
            elif (op2 == 0x0E):
                self.RRC_HL()
            elif (op2 == 0x1E):
                self.RR_HL()

            # Shifts

            elif (op2 == 0x27):
                self.SLA_n('A')
            elif (op2 == 0x20):
                self.SLA_n('B')
            elif (op2 == 0x21):
                self.SLA_n('C')
            elif (op2 == 0x22):
                self.SLA_n('D')
            elif (op2 == 0x23):
                self.SLA_n('E')
            elif (op2 == 0x24):
                self.SLA_n('H')
            elif (op2 == 0x25):
                self.SLA_n('L')
            elif (op2 == 0x2F):
                self.SRA_n('A')
            elif (op2 == 0x28):
                self.SRA_n('B')
            elif (op2 == 0x29):
                self.SRA_n('C')
            elif (op2 == 0x2A):
                self.SRA_n('D')
            elif (op2 == 0x2B):
                self.SRA_n('E')
            elif (op2 == 0x2C):
                self.SRA_n('H')
            elif (op2 == 0x2D):
                self.SRA_n('L')
            elif (op2 == 0x3F):
                self.SRL_n('A')
            elif (op2 == 0x38):
                self.SRL_n('B')
            elif (op2 == 0x39):
                self.SRL_n('C')
            elif (op2 == 0x3A):
                self.SRL_n('D')
            elif (op2 == 0x3B):
                self.SRL_n('E')
            elif (op2 == 0x3C):
                self.SRL_n('H')
            elif (op2 == 0x3D):
                self.SRL_n('L')
            elif (op2 == 0x26):
                self.SLA_HL()
            elif (op2 == 0x2E):
                self.SRA_HL()
            elif (op2 == 0x3E):
                self.SRL_HL()

            # Bit functions

            elif (op2 >= 0x40 and op2 <= 0x7F):
                self.BIT(op2)
            elif (op2 >= 0xC0 and op2 <= 0xFF):
                self.SET(op2)
            elif (op2 >= 0x80 and op2 <= 0xBF):
                self.RES(op2)
            else:
                raise NotImplementedError('Unknown opcode: 0xCB, ' + hex(op2))


        else:
            raise NotImplementedError('Unknown opcode: ' + hex(op))

    def handle_interrupts(self):
        if self.interrupt_master_enable:
            interrupt_flags = self.mmu.get(0xFF0F)
            interrupt_enable = self.mmu.get(0xFFFF)
            if interrupt_flags & interrupt_enable:
                if (interrupt_flags & 1) & (interrupt_enable & 1):
                    #V-Blank
                    self.push_stack(self.pc)
                    self.pc = 0x0040
                    self.mmu.set(0xFF0F, interrupt_flags & ~1)
                elif (interrupt_flags & 2) & (interrupt_enable & 2):
                    #LCDC status
                    self.push_stack(self.pc)
                    self.pc = 0x0048
                    self.mmu.set(0xFF0F, interrupt_flags & ~2)
                elif (interrupt_flags & 4) & (interrupt_enable & 4):
                    #Timer overflow
                    self.push_stack(self.pc)
                    self.pc = 0x0050
                    self.mmu.set(0xFF0F, interrupt_flags & ~4)
                elif (interrupt_flags & 8) & (interrupt_enable & 8):
                    #Serial transfer complete
                    self.push_stack(self.pc)
                    self.pc = 0x0058
                    self.mmu.set(0xFF0F, interrupt_flags & ~8)
                elif (interrupt_flags & 16) & (interrupt_enable & 16):
                    #P10-P13 input low
                    self.push_stack(self.pc)
                    self.pc = 0x0060
                    self.mmu.set(0xFF0F, interrupt_flags & ~16)
                self.interrupt_master_enable = False

    ## OPCODE FUNCTIONS
    # 8-bit loads

    def LD_nn_n(self, r, val):
        self.regs[r] = val

    def LD_r1_r2(self, r1, r2):
        self.regs[r1] = self.regs[r2]

    def LD_HL_r(self, r): #Technically part of LD r1, r2
        addr = self.get_reg_16('HL')
        self.mmu.set(addr, self.regs[r])

    def LD_r_HL(self, r): #Technically part of LD r1, r2
        addr = self.get_reg_16('HL')
        self.regs[r] = self.mmu.get(addr)

    def LD_HL_n(self): #Technically part of LD r1, r2
        n = self.fetch_8()
        addr = self.get_reg_16('HL')
        self.mmu.set(addr, n)

    def LD_A_rr(self, reg):
        addr = self.get_reg_16(reg)
        self.set_reg_8('A', self.mmu.get(addr))

    def LD_A_nn(self):
        addr = self.fetch_16()
        self.set_reg_8('A', self.mmu.get(addr))

    def LD_A_n(self):
        self.set_reg_8('A', self.fetch_8())

    def LD_n_A(self, reg):
        self.set_reg_8(reg, self.get_reg_8('A'))

    def LD_rr_A(self, reg):
        addr = self.get_reg_16(reg)
        self.mmu.set(addr, self.get_reg_8('A'))

    def LD_nn_A(self):
        addr = self.fetch_16()
        self.mmu.set(addr, self.get_reg_8('A'))

    def LD_A_C(self):
        self.set_reg_8('A', self.mmu.get(0xFF00 + self.get_reg_8('C')))

    def LD_C_A(self):
        self.mmu.set(0xFF00 + self.get_reg_8('C'), self.get_reg_8('A'))

    def LDD_A_HL(self):
        self.set_reg_8('A', self.mmu.get(self.get_reg_16('HL')))
        HL = self.get_reg_16('HL')
        self.set_reg_16('HL', HL - (1 if (HL > 0x00) else -0xFFFF))

    def LDD_HL_A(self):
        self.mmu.set(self.get_reg_16('HL'), self.get_reg_8('A'))
        HL = self.get_reg_16('HL')
        self.set_reg_16('HL', HL - (1 if (HL > 0x00) else -0xFFFF))

    def LDI_A_HL(self):
        self.set_reg_8('A', self.mmu.get(self.get_reg_16('HL')))
        HL = self.get_reg_16('HL')
        self.set_reg_16('HL', HL + (1 if (HL < 0xFFFF) else -0xFFFF))

    def LDI_HL_A(self):
        self.mmu.set(self.get_reg_16('HL'), self.get_reg_8('A'))
        HL = self.get_reg_16('HL')
        self.set_reg_16('HL', HL + (1 if (HL < 0xFFFF) else -0xFFFF))

    def LDH_n_A(self):
        n = self.fetch_8()
        self.mmu.set(0xFF00 + n, self.get_reg_8('A'))

    def LDH_A_n(self):
        n = self.fetch_8()
        self.set_reg_8('A', self.mmu.get(0xFF00 + n))

    # 16-bit loads

    def LD_n_nn(self, reg):
        self.set_reg_16(reg, self.fetch_16())

    def LD_SP_HL(self):
        self.set_reg_16('SP', self.get_reg_16('HL'))

    def LD_HL_SPn(self):
        self.set_reg_16('HL', self.add_16(self.fetch_8(), self.get_reg_16('SP')))

    def LD_nn_SP(self):
        val = self.get_reg_16('SP')
        addr = self.fetch_16()
        self.mmu.set(addr, (val & 0x00FF))
        self.mmu.set(addr + 1, (val & 0xFF00) >> 8)

    def PUSH_nn(self, reg):
        self.push_stack(self.get_reg_16(reg))

    def POP_nn(self, reg):
        self.set_reg_16(reg, self.pop_stack())

    def ADD_A_r(self, reg):
        self.set_reg_8('A', self.add_8(
            self.get_reg_8('A'),
            self.get_reg_8(reg)
        ))

    def ADD_A_HL(self):
        self.set_reg_8('A', self.add_8(
            self.get_reg_8('A'),
            self.mmu.get(self.get_reg_16('HL'))
        ))

    def ADD_A_n(self):
        self.set_reg_8('A', self.add_8(
            self.get_reg_8('A'),
            self.fetch_8()
        ))

    def ADC_A_r(self, reg):
        self.set_reg_8('A', self.add_8(
            self.get_reg_8('A'),
            self.get_reg_8(reg),
            True
        ))

    def ADC_A_HL(self):
        self.set_reg_8('A', self.add_8(
            self.get_reg_8('A'),
            self.mmu.get(self.get_reg_16('HL')),
            True
        ))

    def ADC_A_n(self):
        self.set_reg_8('A', self.add_8(
            self.get_reg_8('A'),
            self.fetch_8(),
            True
        ))

    def SUB_A_r(self, reg):
        self.set_reg_8('A', self.sub_8(
            self.get_reg_8('A'),
            self.get_reg_8(reg)
        ))

    def SUB_A_HL(self):
        self.set_reg_8('A', self.sub_8(
            self.get_reg_8('A'),
            self.mmu.get(self.get_reg_16('HL'))
        ))

    def SUB_A_n(self):
        self.set_reg_8('A', self.sub_8(
            self.get_reg_8('A'),
            self.fetch_8()
        ))

    def SBC_A_r(self, reg):
        self.set_reg_8('A', self.sub_8(
            self.get_reg_8('A'),
            self.get_reg_8(reg),
            True
        ))

    def SBC_A_HL(self):
        self.set_reg_8('A', self.sub_8(
            self.get_reg_8('A'),
            self.mmu.get(self.get_reg_16('HL')),
            True
        ))

    def SBC_A_n(self):
        self.set_reg_8('A', self.sub_8(
            self.get_reg_8('A'),
            self.fetch_8(),
            True
        ))

    def AND_r(self, reg):
        result = self.get_reg_8('A') & self.get_reg_8(reg)
        self.set_reg_8('A', result)
        self.set_flag('Z', int(result == 0x00))
        self.set_flag('N', 0)
        self.set_flag('H', 1)
        self.set_flag('C', 0)

    def AND_HL(self):
        result = self.get_reg_8('A') & self.mmu.get(self.get_reg_16('HL'))
        self.set_reg_8('A', result)
        self.set_flag('Z', int(result == 0x00))
        self.set_flag('N', 0)
        self.set_flag('H', 1)
        self.set_flag('C', 0)

    def AND_n(self):
        result = self.get_reg_8('A') & self.fetch_8()
        self.set_reg_8('A', result)
        self.set_flag('Z', int(result == 0x00))
        self.set_flag('N', 0)
        self.set_flag('H', 1)
        self.set_flag('C', 0)

    def OR_r(self, reg):
        result = self.get_reg_8('A') | self.get_reg_8(reg)
        self.set_reg_8('A', result)
        self.set_flag('Z', int(result == 0x00))
        self.set_flag('N', 0)
        self.set_flag('H', 0)
        self.set_flag('C', 0)

    def OR_HL(self):
        result = self.get_reg_8('A') | self.mmu.get(self.get_reg_16('HL'))
        self.set_reg_8('A', result)
        self.set_flag('Z', int(result == 0x00))
        self.set_flag('N', 0)
        self.set_flag('H', 0)
        self.set_flag('C', 0)

    def OR_n(self):
        result = self.get_reg_8('A') | self.fetch_8()
        self.set_reg_8('A', result)
        self.set_flag('Z', int(result == 0x00))
        self.set_flag('N', 0)
        self.set_flag('H', 0)
        self.set_flag('C', 0)

    def XOR_r(self, reg):
        result = self.get_reg_8('A') ^ self.get_reg_8(reg)
        self.set_reg_8('A', result)
        self.set_flag('Z', int(result == 0x00))
        self.set_flag('N', 0)
        self.set_flag('H', 0)
        self.set_flag('C', 0)

    def XOR_HL(self):
        result = self.get_reg_8('A') ^ self.mmu.get(self.get_reg_16('HL'))
        self.set_reg_8('A', result)
        self.set_flag('Z', int(result == 0x00))
        self.set_flag('N', 0)
        self.set_flag('H', 0)
        self.set_flag('C', 0)

    def XOR_n(self):
        result = self.get_reg_8('A') ^ self.fetch_8()
        self.set_reg_8('A', result)
        self.set_flag('Z', int(result == 0x00))
        self.set_flag('N', 0)
        self.set_flag('H', 0)
        self.set_flag('C', 0)

    def CP_r(self, reg):
        a = self.get_reg_8('A')
        self.SUB_A_r(reg)
        self.set_reg_8('A', a)

    def CP_HL(self):
        a = self.get_reg_8('A')
        self.SUB_A_HL()
        self.set_reg_8('A', a)

    def CP_n(self):
        a = self.get_reg_8('A')
        self.SUB_A_n()
        self.set_reg_8('A', a)

    def INC_r(self, reg):
        result = (self.get_reg_8(reg) + 1) % 0x100
        self.set_flag('Z', (result == 0x00))
        self.set_flag('N', False)
        self.set_flag('H', int(((self.get_reg_8(reg) & 0x0F) + 0x01) > 0x0F))
        self.set_reg_8(reg, result)

    def INC_HL(self):
        result = (self.mmu.get(self.get_reg_16('HL')) + 1) % 0x100
        self.set_flag('Z', (result == 0x00))
        self.set_flag('N', False)
        self.set_flag('H', int(((self.mmu.get(self.get_reg_16('HL')) & 0x0F) + 0x01) > 0x0F))
        self.mmu.set(self.get_reg_16('HL'), result)

    def DEC_r(self, reg):
        result = (self.get_reg_8(reg) - 1) % 0x100
        self.set_flag('Z', (result == 0x00))
        self.set_flag('N', True)
        self.set_flag('H', int(self.get_reg_8(reg) & 0x0F) == 0)
        self.set_reg_8(reg, result)

    def DEC_HL(self):
        result = (self.mmu.get(self.get_reg_16('HL')) - 1) % 0x100
        self.set_flag('Z', (result == 0x00))
        self.set_flag('N', True)
        self.set_flag('H', int((self.mmu.get(self.get_reg_16('HL')) & 0x0F) == 0))
        self.mmu.set(self.get_reg_16('HL'), result)

    def ADD_HL_n(self, reg):
        # Ensure Z isn't affected
        z = self.get_flag('Z')
        self.set_reg_16('HL', self.add_16(
            self.get_reg_16('HL'),
            self.get_reg_16(reg),
            False
        ))
        self.set_flag('Z', z)

    def ADD_SP_n(self):
        self.set_reg_16('SP', self.add_16(
            self.get_reg_16('SP'),
            self.fetch_16(),
            False
        ))
        self.set_flag('Z', 0)

    def INC_nn(self, reg):
        self.set_reg_16(reg, (self.get_reg_16(reg) + 1) % 0x10000)

    def DEC_nn(self, reg):
        self.set_reg_16(reg, (self.get_reg_16(reg) - 1) % 0x10000)

    def SWAP_r(self, reg):
        oldval = self.get_reg_8(reg)
        hi = (oldval & 0xF0) >> 4
        lo = oldval & 0x0F
        newval = (lo << 4) | hi

        self.set_reg_8(reg, newval)

    def SWAP_HL(self):
        oldval = self.mmu.get(self.get_reg_16('HL'))
        hi = (oldval & 0xF0) >> 4
        lo = oldval & 0x0F
        newval = (lo << 4) | hi

        self.mmu.set(self.get_reg_16('HL'), newval)

    def DAA(self):
        a = self.get_reg_8('A')
        c = self.get_flag('C')
        h = self.get_flag('H')

        if (self.get_flag('N')):
            if (c): a -= 0x60
            if (h): a -= 0x06
        else:
            if (c or a > 0x99):
                a += 0x60
                self.set_flag('C', 1)
            if (h or (a & 0x0F) > 0x09):
                a += 0x06

        self.set_reg_8('A', a % 0x100)
        self.set_flag('Z', int(a == 0))
        self.set_flag('H', 0)

    def CPL(self):
        self.set_reg_8('A', self.get_reg_8('A') ^ 0xFF)
        self.set_flag('N', 1)
        self.set_flag('H', 1)

    def CCF(self):
        self.set_flag('C', self.get_flag('C') ^ 1)
        self.set_flag('N', 0)
        self.set_flag('H', 0)

    def SCF(self):
        self.set_flag('C', 1)
        self.set_flag('N', 0)
        self.set_flag('H', 0)

    def NOP(self):
        pass

    def HALT(self):
        print('HALT called, not implemented, passing')
        pass

    def STOP(self):
        print('STOP called, not implemented, passing')
        pass

    def DI(self):
        self.interrupt_master_enable = False

    def EI(self):
        self.interrupt_master_enable = True

    # Rotates

    def RLCA(self):
        val = self.get_reg_8('A') << 1

        if ((val & 0x100) >> 8 == 1):
            val -= 0x100
            val += 0x01

        self.set_flag('C', (self.get_reg_8('A') & 0b10000000) >> 7)
        self.set_flag('Z', 1 if val == 0 else 0)
        self.set_flag('N', 0)
        self.set_flag('H', 0)
        self.set_reg_8('A', val)

    def RLA(self):
        val = self.get_reg_8('A') << 1

        if ((val & 0x100) >> 8 == 1):
            val -= 0x100

        val += self.get_flag('C')

        self.set_flag('C', (self.get_reg_8('A') & 0b10000000) >> 7)
        self.set_flag('Z', 1 if val == 0 else 0)
        self.set_flag('N', 0)
        self.set_flag('H', 0)
        self.set_reg_8('A', val)

    def RRCA(self):
        val = self.get_reg_8('A')

        carry = val % 2
        self.set_flag('C', carry)
        val -= carry
        val = val >> 1
        val += 0x80 * carry

        self.set_reg_8('A', val)
        self.set_flag('Z', 1 if val == 0 else 0)
        self.set_flag('N', 0)
        self.set_flag('H', 0)

    def RRA(self):
        val = self.get_reg_8('A')
        old_c = self.get_flag('C')

        self.set_flag('C', val % 2)
        val -= val % 2

        self.set_reg_8('A', (val >> 1) + (old_c * 0x80))
        self.set_flag('Z', 1 if val == 0 else 0)
        self.set_flag('N', 0)
        self.set_flag('H', 0)

    def RLC_n(self, reg):
        val = self.get_reg_8(reg) << 1

        if ((val & 0x100) >> 8 == 1):
            val -= 0x100
            val += 0x01

        self.set_flag('C', (self.get_reg_8(reg) & 0b10000000) >> 7)
        self.set_flag('Z', 1 if val == 0 else 0)
        self.set_flag('N', 0)
        self.set_flag('H', 0)
        self.set_reg_8(reg, val)

    def RL_n(self, reg):
        val = self.get_reg_8(reg) << 1

        if ((val & 0x100) >> 8 == 1):
            val -= 0x100

        val += self.get_flag('C')

        self.set_flag('C', (self.get_reg_8(reg) & 0b10000000) >> 7)
        self.set_flag('Z', 1 if val == 0 else 0)
        self.set_flag('N', 0)
        self.set_flag('H', 0)
        self.set_reg_8(reg, val)

    def RRC_n(self, reg):
        val = self.get_reg_8(reg)

        carry = val % 2
        self.set_flag('C', carry)
        val -= carry
        val = val >> 1
        val += 0x80 * carry

        self.set_reg_8(reg, val)
        self.set_flag('Z', 1 if val == 0 else 0)
        self.set_flag('N', 0)
        self.set_flag('H', 0)

    def RR_n(self, reg):
        val = self.get_reg_8(reg)
        old_c = self.get_flag('C')

        self.set_flag('C', val % 2)
        val -= val % 2

        self.set_reg_8(reg, (val >> 1) + (old_c * 0x80))
        self.set_flag('Z', 1 if val == 0 else 0)
        self.set_flag('N', 0)
        self.set_flag('H', 0)

    def RLC_HL(self):
        val = self.mmu.get(self.get_reg_16('HL')) << 1

        if ((val & 0x100) >> 8 == 1):
            val -= 0x100
            val += 0x01

        self.set_flag('C', (self.mmu.get(self.get_reg_16('HL')) & 0b10000000) >> 7)
        self.set_flag('Z', 1 if val == 0 else 0)
        self.set_flag('N', 0)
        self.set_flag('H', 0)
        self.mmu.set(self.get_reg_16('HL'), val)

    def RL_HL(self):
        val = self.mmu.get(self.get_reg_16('HL')) << 1

        if ((val & 0x100) >> 8 == 1):
            val -= 0x100

        val += self.get_flag('C')

        self.set_flag('C', (self.mmu.get(self.get_reg_16('HL')) & 0b10000000) >> 7)
        self.set_flag('Z', 1 if val == 0 else 0)
        self.set_flag('N', 0)
        self.set_flag('H', 0)
        self.mmu.set(self.get_reg_16('HL'), val)

    def RRC_HL(self):
        val = self.mmu.get(self.get_reg_16('HL'))

        carry = val % 2
        self.set_flag('C', carry)
        val -= carry
        val = val >> 1
        val += 0x80 * carry

        self.mmu.set(self.get_reg_16('HL'), val)
        self.set_flag('Z', 1 if val == 0 else 0)
        self.set_flag('N', 0)
        self.set_flag('H', 0)

    def RR_HL(self):
        val = self.mmu.get(self.get_reg_16('HL'))
        old_c = self.get_flag('C')

        self.set_flag('C', val % 2)
        val -= val % 2

        self.mmu.set(self.get_reg_16('HL'), (val >> 1) + (old_c * 0x80))
        self.set_flag('Z', 1 if val == 0 else 0)
        self.set_flag('N', 0)
        self.set_flag('H', 0)

    # Shifts

    def SLA_n(self, reg):
        val = self.get_reg_8(reg) << 1

        if ((val & 0x100) >> 8 == 1):
            val -= 0x100

        self.set_flag('C', (self.get_reg_8(reg) & 0b10000000) >> 7)
        self.set_flag('Z', 1 if val == 0 else 0)
        self.set_flag('N', 0)
        self.set_flag('H', 0)
        self.set_reg_8(reg, val)

    def SRA_n(self, reg):
        val = self.get_reg_8(reg)
        msb = val & 0b10000000

        self.set_flag('C', val % 2)
        val -= val % 2
        val = val >> 1
        val += msb

        self.set_reg_8(reg, val)
        self.set_flag('Z', 1 if val == 0 else 0)
        self.set_flag('N', 0)
        self.set_flag('H', 0)

    def SRL_n(self, reg):
        val = self.get_reg_8(reg)

        self.set_flag('C', val % 2)
        val -= val % 2
        val = val >> 1

        self.set_reg_8(reg, val)
        self.set_flag('Z', 1 if val == 0 else 0)
        self.set_flag('N', 0)
        self.set_flag('H', 0)

    def SLA_HL(self):
        val = self.mmu.get(self.get_reg_16('HL')) << 1

        if ((val & 0x100) >> 8 == 1):
            val -= 0x100

        self.set_flag('C', (self.mmu.get(self.get_reg_16('HL')) & 0b10000000) >> 7)
        self.set_flag('Z', 1 if val == 0 else 0)
        self.set_flag('N', 0)
        self.set_flag('H', 0)
        self.mmu.set(self.get_reg_16('HL'), val)

    def SRA_HL(self):
        val = self.mmu.get(self.get_reg_16('HL'))
        msb = val & 0b10000000

        self.set_flag('C', val % 2)
        val -= val % 2
        val = val >> 1
        val += msb

        self.mmu.set(self.get_reg_16('HL'), val)
        self.set_flag('Z', 1 if val == 0 else 0)
        self.set_flag('N', 0)
        self.set_flag('H', 0)

    def SRL_HL(self):
        val = self.mmu.get(self.get_reg_16('HL'))

        self.set_flag('C', val % 2)
        val -= val % 2
        val = val >> 1

        self.mmu.set(self.get_reg_16('HL'), val)
        self.set_flag('Z', 1 if val == 0 else 0)
        self.set_flag('N', 0)
        self.set_flag('H', 0)

    def BIT(self, opcode):
        opcode -= 0x40
        reg_index = opcode & 0b00000111

        reg = ''
        if (reg_index == 0):
            reg = 'B'
        elif (reg_index == 1):
            reg = 'C'
        elif (reg_index == 2):
            reg = 'D'
        elif (reg_index == 3):
            reg = 'E'
        elif (reg_index == 4):
            reg = 'H'
        elif (reg_index == 5):
            reg = 'L'
        elif (reg_index == 6):
            reg = 'HL'
        elif (reg_index == 7):
            reg = 'A'

        bit = int((opcode & 0b11111000) / 0x08)

        if (reg == 'HL'):
            self.set_flag('Z', (self.mmu.get(self.get_reg_16(reg)) >> bit) ^ 0x01)
        else:
            self.set_flag('Z', (self.get_reg_8(reg) >> bit) ^ 0x01)

        self.set_flag('N', 0)
        self.set_flag('H', 1)

    def SET(self, opcode):
        opcode -= 0xC0
        reg_index = opcode & 0b00000111

        reg = ''
        if (reg_index == 0):
            reg = 'B'
        elif (reg_index == 1):
            reg = 'C'
        elif (reg_index == 2):
            reg = 'D'
        elif (reg_index == 3):
            reg = 'E'
        elif (reg_index == 4):
            reg = 'H'
        elif (reg_index == 5):
            reg = 'L'
        elif (reg_index == 6):
            reg = 'HL'
        elif (reg_index == 7):
            reg = 'A'

        bit = int((opcode & 0b11111000) / 0x08)

        if (reg == 'HL'):
            self.mmu.set(self.get_reg_16(reg), self.mmu.get(self.get_reg_16(reg)) | (0x01 << bit))
        else:
            self.set_reg_8(reg, self.get_reg_8(reg) | (0x01 << bit))
        self.set_flag('H', 1)

    def RES(self, opcode):
        opcode -= 0x80
        reg_index = opcode & 0b00000111

        reg = ''
        if (reg_index == 0):
            reg = 'B'
        elif (reg_index == 1):
            reg = 'C'
        elif (reg_index == 2):
            reg = 'D'
        elif (reg_index == 3):
            reg = 'E'
        elif (reg_index == 4):
            reg = 'H'
        elif (reg_index == 5):
            reg = 'L'
        elif (reg_index == 6):
            reg = 'HL'
        elif (reg_index == 7):
            reg = 'A'

        bit = int((opcode & 0b11111000) / 0x08)

        if (reg == 'HL'):
            self.mmu.set(self.get_reg_16(reg), self.mmu.get(self.get_reg_16(reg)) & ((0x01 << bit)^ 0xFF))
        else:
            self.set_reg_8(reg, self.get_reg_8(reg) & ((0x01 << bit) ^ 0xFF))

    # Jumps

    def JP_nn(self):
        self.pc = self.fetch_16()

    def JP_NZ(self):
        if (self.get_flag('Z') == 0):
            self.pc = self.fetch_16()
        else:
            self.pc += 2

    def JP_Z(self):
        if (self.get_flag('Z') == 1):
            self.pc = self.fetch_16()
        else:
            self.pc += 2

    def JP_NC(self):
        if (self.get_flag('C') == 0):
            self.pc = self.fetch_16()
        else:
            self.pc += 2

    def JP_C(self):
        if (self.get_flag('C') == 1):
            self.pc = self.fetch_16()
        else:
            self.pc += 2

    def JP_HL(self):
        self.pc = self.get_reg_16('HL')

    def JR_n(self):
        self.pc += self.fetch_8()

    def JR_NZ(self):
        if (self.get_flag('Z') == 0):
            self.pc += self.fetch_8()
        else:
            self.pc += 1

    def JR_Z(self):
        if (self.get_flag('Z') == 1):
            self.pc += self.fetch_8()
        else:
            self.pc += 1

    def JR_NC(self):
        if (self.get_flag('C') == 0):
            self.pc += self.fetch_8()
        else:
            self.pc += 1

    def JR_C(self):
        if (self.get_flag('C') == 1):
            self.pc += self.fetch_8()
        else:
            self.pc += 1

    # Calls

    def CALL_nn(self):
        self.push_stack(self.pc+2)
        self.pc = self.fetch_16()

    def CALL_NZ(self):
        if (self.get_flag('Z') == 0):
            self.CALL_nn()
        else:
            self.pc += 2

    def CALL_Z(self):
        if (self.get_flag('Z') == 1):
            self.CALL_nn()
        else:
            self.pc += 2

    def CALL_NC(self):
        if (self.get_flag('C') == 0):
            self.CALL_nn()
        else:
            self.pc += 2

    def CALL_C(self):
        if (self.get_flag('C') == 1):
            self.CALL_nn()
        else:
            self.pc += 2

    # Restarts

    def RST(self, n):
        self.push_stack(self.pc)
        self.pc = n

    # Returns

    def RET(self):
        self.pc = self.pop_stack()

    def RET_NZ(self):
        if (self.get_flag('Z') == 0):
            self.RET()

    def RET_Z(self):
        if (self.get_flag('Z') == 1):
            self.RET()

    def RET_NC(self):
        if (self.get_flag('C') == 0):
            self.RET()

    def RET_C(self):
        if (self.get_flag('C') == 1):
            self.RET()

    def RETI(self):
        self.EI()
        self.RET()
