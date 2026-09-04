"""Pasmo, TAP and ROM-only DCK/PicoROM exports with explicit bounds."""
import json, os, re, shutil, struct, subprocess
from pathlib import Path
from .assembly import runtime

def wsl(path):
    s=Path(path).resolve().as_posix()
    return '/mnt/'+s[0].lower()+s[2:]

def assemble(source, out, pasmo):
    asm=out/'player.asm'; asm.write_text(source,encoding='utf-8')
    if os.name=='nt' and not str(pasmo).lower().endswith('.exe'):
        cmd=['wsl',wsl(pasmo),'--bin',wsl(asm),wsl(out/'player.bin'),wsl(out/'player.sym')]
    else:
        cmd=[str(pasmo),'--bin',str(asm),str(out/'player.bin'),str(out/'player.sym')]
    result=subprocess.run(cmd,capture_output=True,text=True,cwd=out)
    (out/"assembler.log").write_text(result.stdout+result.stderr)
    if result.returncode:raise ValueError(result.stdout+result.stderr)
    symbols={k:int(v,16) for k,v in re.findall(r'^(\w+)\s+EQU\s+0([0-9A-F]+)H', (out/'player.sym').read_text(),re.M)}
    return (out/'player.bin').read_bytes(),symbols

def block(flag,data):
    b=bytes([flag])+data; checksum=0
    for v in b: checksum^=v
    return struct.pack('<H',len(b)+1)+b+bytes([checksum])

def header(kind,name,n,p1,p2):
    return block(0,bytes([kind])+name.encode('ascii')[:10].ljust(10)+struct.pack('<HHH',n,p1,p2))

def tap(raw,origin,start):
    def number(n): return str(n).encode()+bytes([14,0,0,n&255,n>>8,0])
    line=bytes([253])+number(origin-1)+b':'+bytes([239])+b'""'+bytes([175])+b':'+bytes([249,192])+number(start)+b'\r'
    basic=b'\x00\x0a'+struct.pack('<H',len(line))+line
    return header(0,'AUDIO',len(basic),10,len(basic))+block(255,basic)+header(3,'AUDIOCODE',len(raw),origin,32768)+block(255,raw)

def screen(entries,phase=0):
    from PIL import Image,ImageDraw,ImageFont
    import math
    im=Image.new('1',(256,192));d=ImageDraw.Draw(im);font=ImageFont.load_default()
    lines=['TS2068 AUDIO LAB','Q/A SELECT  SPACE PLAY']+[f'{i+1:02} {e["name"][:13]} {e["codec"]}' for i,e in enumerate(entries)]
    for i,line in enumerate(lines): d.text((0,i*8-2),line,font=font,fill=1)
    d.line([(x,174+int(9*math.sin((x+phase)/12))) for x in range(256)],fill=1)
    raw=bytearray(6912)
    for y in range(192):
        for x in range(256):
            if im.getpixel((x,y)):raw[((y&192)<<5)|((y&7)<<8)|((y&56)<<2)|(x>>3)] |=128>>(x&7)
    raw[6144:]=bytes([7])*768
    return raw

DEMO='''demo:
 di
 {paging}
 xor a
 out ($ff),a
 out ($fe),a
 ld sp,$ff00
 ld hl,screen_data
 ld de,$4000
 ld bc,6912
 ldir
 ld hl,screen2_data
 ld de,$6000
 call unpack_screen
 ld hl,$c000
 ld de,$c001
 ld bc,256
 ld (hl),$c1
 ldir
 ld a,$c3
 ld ($c1c1),a
 ld hl,isr
 ld ($c1c2),hl
 ld a,$c0
 ld i,a
 im 2
 call audio_init
 xor a
 ld (state+6),a
 ld (state+8),a
 ei
menu:
 halt
 call marker
 ld bc,$fbfe
 in a,(c)
 bit 0,a
 jr z,up
 ld bc,$fdfe
 in a,(c)
 bit 0,a
 jr z,down
 ld bc,$7ffe
 in a,(c)
 bit 0,a
 jr z,play
 jr menu
up:
 ld a,(state+8)
 or a
 jr z,release
 dec a
 ld (state+8),a
 jr release
down:
 ld a,(state+8)
 cp {last}
 jr z,release
 inc a
 ld (state+8),a
release:
 ld bc,$00fe
 in a,(c)
 and 31
 cp 31
 jr nz,release
 jr menu
play:
 di
 call audio_init
 ld a,(state+8)
 ld l,a
 ld h,0
 add hl,hl
 add hl,hl
 ld e,a
 ld d,0
 add hl,de
 ld de,directory
 add hl,de
 ld a,(hl)
 ld (state+9),a
 inc hl
 ld e,(hl)
 inc hl
 ld d,(hl)
 inc hl
 push de
 ld e,(hl)
 inc hl
 ld d,(hl)
 pop hl
 ld a,(state+9)
 cp 0
 jr nz,not5
 call dac5
 jr done
not5:
 cp 1
 jr nz,not6
 call dac6
 jr done
not6:
 cp 2
 jr nz,tonal
 call dpcm6
 jr done
tonal:
 call ay_start
 ei
playing:
 halt
 ld a,(state+5)
 or a
 jr nz,playing
 di
 call audio_stop
done:
 ei
 jp release
marker:
 ld hl,$5840
 ld b,{count}
 xor a
marker_loop:
 ld (hl),7
 ld e,a
 ld a,(state+8)
 cp e
 jr nz,marker_skip
 ld (hl),$47
marker_skip:
 ld a,e
 inc a
 ld de,32
 add hl,de
 djnz marker_loop
 ret
isr:
 push af
 push bc
 push de
 push hl
 call ay_tick
 ; Moving bright cell in the bottom row; harmonic playback continues.
 ld a,(state+6)
 ld l,a
 ld h,$5a
 ld (hl),7
 inc a
 and 31
 ld (state+6),a
 ld l,a
 ld (hl),$5e
 pop hl
 pop de
 pop bc
 pop af
 ei
 reti
'''

def build(entries,out,formats,origin,pasmo,separate=False,data_origin=0xd000):
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True)
    cartridge='dck' in formats
    if cartridge and origin!=0x8000: raise ValueError('DCK requires origin0x8000; binary/TAP permit relocation')
    if not 0x6000<=origin<0xc000:raise ValueError('Origin must be0x6000..0xbfff; C000+ reserved native RAM')
    if set(formats)&{'tap','dck'} and origin<0x8000:
        raise ValueError('Two-screen demos require origin >=0x8000; 6000..7AFF holds the second display')
    if len(entries)>16:raise ValueError('A demo volume supports16 selections; split the input list')
    # Always generate a separate callable runtime, plus the selected demo media.
    rt=runtime();(out/'runtime.asm').write_text(rt)
    source=f' org {origin}\nstate equ $c210\n'+rt
    data=b''.join(e['data'] for e in entries);(out/'data.bin').write_bytes(data)
    offset=0;directory=[]
    for i,e in enumerate(entries):
        e['offset']=offset;offset+=len(e['data'])
        directory.append(f' defb {0 if e["codec"]=="ay4-5k" else 1 if e["codec"]=="ay4-6k" else 2 if e["codec"]=="dpcm3-6k" else 3}\n defw data_base+{e["offset"]},{e["count"]}\n')
    if separate:
        if data_origin<0xc300 or data_origin+len(data)>0xfe00:raise ValueError('Separate data must fit C300..FDFF (stack reserve above)')
        source+=f'data_base equ {data_origin}\n'
    else:source+='data_base:\n incbin "'+'data.bin'+'"\n'
    raw,symbols=assemble(source,out,pasmo)
    if origin+len(raw)>0xc000:raise ValueError('Runtime + data exceeds C000; use --separate-data or shorter input')
    (out/'module.bin').write_bytes(raw);(out/'module.asm').write_text(source)
    (out/'module.sym').write_text((out/'player.sym').read_text())
    manifest={'version':1,'origin':origin,'state_address':0xc210,'state_bytes':16,
              'api':{n:symbols[n] for n in ['audio_api','audio_init','dac5','dac6','dpcm6','ay_start','ay_tick','audio_stop']},
              'data_address':symbols['data_base'],'separate_data':separate,'entries':[
                  {k:v for k,v in e.items() if k!='data'} for e in entries]}
    if set(formats)&{'tap','dck'}:
        if separate:raise ValueError('--separate-data is for callable binary output; demo media embed data')
        (out/'screen.bin').write_bytes(screen(entries))
        # Screen is stored compressed as attribute/bitmap runs to leave space for audio.
        from .rle import encode as rle
        (out/'screen.rle').write_bytes(rle(screen(entries)))
        (out/'screen2.rle').write_bytes(rle(screen(entries,16)))
        demo=DEMO.format(paging='ld a,$30\n out ($f4),a' if cartridge else '',last=len(entries)-1,count=len(entries))
        demo=demo.replace(' ld bc,6912\n ldir',' call unpack_screen',1)
        source=f' org {origin}\nstate equ $c210\n'+(' defb 2,2,8,$80,$ef,1,0,0\n jp demo\n' if cartridge else ' jp demo\n')+runtime(animated=True)+demo+'''
unpack_screen:
 ld a,(hl)
 inc hl
 or a
 ret z
 ld b,a
 ld a,(hl)
 inc hl
unpack_run:
 ld (de),a
 inc de
 djnz unpack_run
 jr unpack_screen
screen_data:
 incbin "'''+'screen.rle'+'"\nscreen2_data:\n incbin "screen2.rle"\ndirectory:\n'+''.join(directory)+'data_base:\n incbin "'+'data.bin'+'"\n'
        raw,symbols=assemble(source,out,pasmo)
        if origin+len(raw)>0xc000:raise ValueError(f'Demo needs{len(raw)} bytes; limit{0xc000-origin}. Split samples/codecs into volumes.')
        if 'tap' in formats:(out/'demo.tap').write_bytes(tap(raw,origin,origin+8 if cartridge else origin))
        if cartridge:
            rom=raw.ljust(16384,b'\xff')
            (out/'demo.dck').write_bytes(bytes([0,0,0,0,0,2,2,0,0])+rom)
            (out/'picorom.bin').write_bytes(bytes([255])*32768+rom+bytes([255])*16384)
        manifest['demo_symbols']=symbols
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2))
    (out/'api.inc').write_text('\n'.join(f'{k.upper()} equ ${v:04x}' for k,v in manifest['api'].items())+'\n')
    return manifest
