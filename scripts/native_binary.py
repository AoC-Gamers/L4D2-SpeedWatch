"""Read ELF/PE metadata without executing the target or needing its SDK."""
import struct
from pathlib import Path
REQUIRED={'GetSMExtAPI','CreateInterface_MMS'}
def validate_binary(path: Path, platform: str):
    data=path.read_bytes()
    def unpack(fmt, offset): return struct.unpack_from(fmt,data,offset)
    if platform=='linux':
        if len(data)<52 or data[:7]!=b'\x7fELF\x01\x01\x01' or unpack('<HH',16)!=(3,3): raise ValueError('Expected x86 ELF shared object')
        shoff=unpack('<I',32)[0]; entsize,count=unpack('<HH',46)
        if entsize!=40 or shoff+count*40>len(data): raise ValueError('Invalid ELF sections')
        sections=[unpack('<10I',shoff+i*40) for i in range(count)]
        symbols=set()
        for s in sections:
            if s[1]!=11: continue
            strings=sections[s[6]]; names=data[strings[4]:strings[4]+strings[5]]
            if s[9]!=16: raise ValueError('Invalid ELF symbols')
            for off in range(s[4],s[4]+s[5],16):
                name,value,size,info,other,section=unpack('<IIIBBH',off)
                if section and (info>>4) in (1,2) and (other&3)==0:
                    symbols.add(names[name:].split(b'\0',1)[0].decode('ascii',errors='replace'))
    elif platform=='windows':
        if len(data)<64 or data[:2]!=b'MZ': raise ValueError('Expected PE image')
        pe=unpack('<I',60)[0]
        if data[pe:pe+4]!=b'PE\0\0' or unpack('<H',pe+4)[0]!=0x14c: raise ValueError('Expected x86 PE')
        count=unpack('<H',pe+6)[0]; optsize=unpack('<H',pe+20)[0]; opt=pe+24
        if unpack('<H',opt)[0]!=0x10b or not (unpack('<H',pe+22)[0]&0x2000): raise ValueError('Expected PE32 DLL')
        sections=[unpack('<8s6I2HI',opt+optsize+i*40) for i in range(count)]
        def offset(rva):
            for s in sections:
                if s[2]<=rva<s[2]+s[3]: return s[4]+rva-s[2]
            raise ValueError('Unmapped PE RVA')
        export=offset(unpack('<I',opt+96)[0]); n=unpack('<I',export+24)[0]
        if n>65536: raise ValueError('Invalid export count')
        names=offset(unpack('<I',export+32)[0]); symbols=set()
        for i in range(n):
            pos=offset(unpack('<I',names+4*i)[0]); symbols.add(data[pos:].split(b'\0',1)[0].decode('ascii'))
    else: raise ValueError('Unknown platform')
    if not REQUIRED <= symbols: raise ValueError('Missing extension exports: '+str(REQUIRED-symbols))
