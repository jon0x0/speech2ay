"""Storage estimates for an alternative AY stream with unused channels omitted.

These records are estimates only; the reference player still consumes R0..R13.
Keep shared noise, mixer and envelope registers, including the R13 skip marker.
"""
from .storage import encode


def compact_estimate(entry):
    codec = entry['codec']
    if codec not in ('harmonic1', 'optimized1', 'harmonic2', 'optimized2'):
        return None
    channels = int(codec[-1])
    registers = list(range(channels * 2)) + [6, 7] + list(range(8, 8 + channels)) + [11, 12, 13]
    data = entry['data']
    if len(data) % 14:
        raise ValueError('AY stream must contain complete 14-byte frames')
    for offset in range(0, len(data), 14):
        if any(data[offset + r] for r in range(8 + channels, 11)):
            raise ValueError('Cannot omit an audible AY channel')
    projected = bytes(data[offset + r] for offset in range(0, len(data), 14) for r in registers)
    packed = encode(projected)
    stored = len(packed) if len(packed) < len(projected) and len(packed) <= 0x1800 else len(projected)
    return {'bytes_per_frame': len(registers), 'raw_bytes': len(projected), 'stored_bytes': stored}


def display_bytes(entry):
    estimate = entry.get('compact_estimate')
    return str(estimate['stored_bytes']) + '*' if estimate else str(entry['stored_bytes'])
