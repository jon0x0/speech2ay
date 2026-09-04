"""Run each comparison selection through its real playback dispatch in Fuse."""
import argparse
import json
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tsaudio.build import assemble
from run_fuse_debug import run_fuse

def main():
    p = argparse.ArgumentParser()
    p.add_argument('directory', type=Path)
    p.add_argument('--pasmo', required=True)
    p.add_argument('--fuse', required=True, type=Path)
    a = p.parse_args()
    folder = a.directory.resolve()
    m = json.loads((folder / 'manifest.json').read_text())
    harness = '''
test_start:
 di
 xor a
 ld (ui),a
 ld (ui+1),a
 jp play
test_next:
 di
 ld hl,(wave_src)
 call test_report
 xor a
 ld (ui+2),a
 ld a,(ui+1)
 inc a
 cp CODEC_COUNT
 jr c,test_codec
 xor a
 ld (ui+1),a
 ld a,(ui)
 inc a
 cp SAMPLE_COUNT
 jp z,test_finished
 ld (ui),a
 jp play
test_codec:
 ld (ui+1),a
 jp play
test_report: ret
test_finished: jp test_finished
'''
    source = (folder / 'player.asm').read_text()
    source = source.replace('menu:\n', 'menu:\n jp test_start\n', 1)
    source = source.replace('\ndone:\n', '\ndone:\n jp test_next\n', 1) + harness
    target = folder / 'playback-verification'
    target.mkdir(exist_ok=True)
    (target / 'wave-tiles.bin').write_bytes((folder / 'wave-tiles.bin').read_bytes())
    raw, symbols = assemble(source, target, a.pasmo)
    assert len(raw) <= 8192
    rom = bytearray((folder / 'picorom.bin').read_bytes())
    rom[32768:40960] = raw.ljust(8192, b'\xff')
    (target / 'test.dck').write_bytes(bytes([0] + [2] * 8) + rom)
    commands = f'''breakpoint {symbols['test_report']}
commands 1
print z80:hl
continue
end
breakpoint {symbols['test_finished']}
commands 2
exit 0
end'''
    result = run_fuse(machine='ts2068', media=target / 'test.dck', fuse=a.fuse,
                      debugger_command=commands, timeout=55)
    (target / 'trace.log').write_text(result.stdout + result.stderr)
    pointers = [int(x, 16) for x in re.findall(r'^0x([0-9a-f]+)$', result.stdout, re.M | re.I)]
    assert len(pointers) == len(m['entries']), (len(pointers), len(m['entries']))
    assert all(0xa000 <= x < 0xa800 and x % 128 == 0 for x in pointers)
    assert len(set(pointers)) > 1, 'Animation phase did not advance'
    report = {'completed_selections': len(pointers), 'wave_pointers': pointers,
              'scope': 'Real loader/playback/ISR dispatch; keyboard scanning bypassed'}
    (target / 'result.json').write_text(json.dumps(report, indent=2))
    print(report)

if __name__ == '__main__':
    main()
