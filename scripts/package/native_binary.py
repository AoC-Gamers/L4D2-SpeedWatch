"""Read ELF/PE metadata without executing the target or needing its SDK."""
import struct
from pathlib import Path

REQUIRED = {'GetSMExtAPI', 'CreateInterface_MMS'}


def elf_section_symbols(data, sections, section):
    strings = sections[section[6]]
    names = data[strings[4]:strings[4] + strings[5]]
    if section[9] != 16:
        raise ValueError('Invalid ELF symbols')
    symbols = set()
    for off in range(section[4], section[4] + section[5], 16):
        name, _, _, info, other, index = struct.unpack_from('<IIIBBH', data, off)
        if index and (info >> 4) in (1, 2) and (other & 3) == 0:
            symbols.add(names[name:].split(b'\0', 1)[0].decode('ascii', errors='replace'))
    return symbols


def elf_symbols(data):
    if len(data) < 52 or data[:7] != b'\x7fELF\x01\x01\x01' or struct.unpack_from('<HH', data, 16) != (3, 3):
        raise ValueError('Expected x86 ELF shared object')
    shoff = struct.unpack_from('<I', data, 32)[0]
    entsize, count = struct.unpack_from('<HH', data, 46)
    if entsize != 40 or shoff + count * 40 > len(data):
        raise ValueError('Invalid ELF sections')
    sections = [struct.unpack_from('<10I', data, shoff + i * 40) for i in range(count)]
    symbols = set()
    for section in sections:
        if section[1] == 11:
            symbols.update(elf_section_symbols(data, sections, section))
    return symbols


def pe_offset(sections, rva):
    for section in sections:
        if section[2] <= rva < section[2] + section[3]:
            return section[4] + rva - section[2]
    raise ValueError('Unmapped PE RVA')


def pe_symbols(data):
    if len(data) < 64 or data[:2] != b'MZ':
        raise ValueError('Expected PE image')
    pe = struct.unpack_from('<I', data, 60)[0]
    if data[pe:pe + 4] != b'PE\0\0' or struct.unpack_from('<H', data, pe + 4)[0] != 0x14c:
        raise ValueError('Expected x86 PE')
    count = struct.unpack_from('<H', data, pe + 6)[0]
    optsize = struct.unpack_from('<H', data, pe + 20)[0]
    opt = pe + 24
    if struct.unpack_from('<H', data, opt)[0] != 0x10b or not (struct.unpack_from('<H', data, pe + 22)[0] & 0x2000):
        raise ValueError('Expected PE32 DLL')
    sections = [struct.unpack_from('<8s6I2HI', data, opt + optsize + i * 40) for i in range(count)]
    export = pe_offset(sections, struct.unpack_from('<I', data, opt + 96)[0])
    count = struct.unpack_from('<I', data, export + 24)[0]
    if count > 65536:
        raise ValueError('Invalid export count')
    names = pe_offset(sections, struct.unpack_from('<I', data, export + 32)[0])
    symbols = set()
    for i in range(count):
        pos = pe_offset(sections, struct.unpack_from('<I', data, names + 4 * i)[0])
        symbols.add(data[pos:].split(b'\0', 1)[0].decode('ascii'))
    return symbols


def validate_binary(path: Path, platform: str):
    data = path.read_bytes()
    if platform == 'linux':
        symbols = elf_symbols(data)
    elif platform == 'windows':
        symbols = pe_symbols(data)
    else:
        raise ValueError('Unknown platform')
    missing = REQUIRED - symbols
    if missing:
        raise ValueError('Missing extension exports: ' + str(missing))
