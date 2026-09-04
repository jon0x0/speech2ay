"""Lossless cartridge records: literals and overlapping LZ backreferences.

Token0 ends the record;1..127 copies that many literal bytes.128..255 copies
3..130 bytes from a following little-endian backward distance. Distances are
relative to the next output byte. Decoder needs no external dictionary.
"""
from collections import defaultdict, deque

def encode(data):
    positions = defaultdict(lambda: deque(maxlen=32))
    output = bytearray()
    literals = bytearray()
    def flush():
        if literals:
            output.append(len(literals))
            output.extend(literals)
            literals.clear()
    at = 0
    while at < len(data):
        length = distance = 0
        for previous in reversed(positions[data[at:at+3]]):
            if at-previous > 65535:
                continue
            n = 0
            while n < 130 and at+n < len(data) and data[previous+n] == data[at+n]:
                n += 1
            if n > length:
                length, distance = n, at-previous
        if length >= 4:
            flush()
            output.append(128+length-3)
            output.extend(distance.to_bytes(2, 'little'))
            step = length
        else:
            literals.append(data[at])
            if len(literals) == 127:
                flush()
            step = 1
        for index in range(at, at+step):
            positions[data[index:index+3]].append(index)
        at += step
    flush()
    return bytes(output) + b'\0'

def decode(data):
    output = bytearray()
    at = 0
    while data[at]:
        token = data[at]
        at += 1
        if token < 128:
            output.extend(data[at:at+token])
            at += token
        else:
            distance = int.from_bytes(data[at:at+2], 'little')
            at += 2
            if not 0 < distance <= len(output):
                raise ValueError('Invalid cartridge backreference')
            for _ in range(token-128+3):
                output.append(output[-distance])
    return bytes(output)
