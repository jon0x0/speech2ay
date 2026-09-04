"""Single64K comparison cartridge: banked ROM payload, native RAM playback."""
import json,math
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
from .assembly import runtime
from .size_estimates import compact_estimate, display_bytes
from .build import assemble
from .rle import encode as rle
from .storage import encode as compress, decode as decompress

LABELS={'ay4-5k':'AY4 5 kHz','ay4-6k':'AY4 6 kHz','dpcm3-6k':'DPCM3 6 kHz',
        **{f'harmonic{i}':f'AY harmonic {i} ch' for i in (1,2,3)},
        **{f'optimized{i}':f'AY optimized {i} ch' for i in (1,2,3)},'audio2ay':'audio2ay'}

def pixels(im,attributes=0):
    data=bytearray(6912)
    for y in range(192):
        for x in range(256):
            if im.getpixel((x,y)):data[((y&192)<<5)|((y&7)<<8)|((y&56)<<2)|(x>>3)]|=128>>(x&7)
    data[6144:]=bytes([attributes])*768
    return bytes(data)

def artwork(names,codecs,entries,out):
    font=ImageFont.load_default();assets=[];pages=(len(codecs)+5)//6
    for page in range(pages):
        im=Image.new('1',(256,192));d=ImageDraw.Draw(im)
        d.text((8,2),'TS2068 AUDIO LAB',font=font,fill=1)
        d.text((8,18),'O/P sample    Q/A codec    SPACE play',font=font,fill=1)
        heading='S spectrum' if all('spectrum' in e for e in entries) else f'Codec ({page*6+1}-{min(page*6+6,len(codecs))} of {len(codecs)})'
        d.text((8,46),heading,font=font,fill=1)
        label='ROM bytes'
        d.text((246-d.textlength(label,font=font),46),label,font=font,fill=1)
        for row,codec in enumerate(codecs[page*6:page*6+6]):
            d.text((16,62+row*16),LABELS.get(codec,codec),font=font,fill=1)
        d.text((8,160),'* compact stream estimate',font=font,fill=1)
        im.resize((768,576)).save(out/f'base-page-{page+1}.png')
        assets.append(rle(pixels(im,7)))
    for si,name in enumerate(names):
        for page in range(pages):
            im=Image.new('1',(256,192));d=ImageDraw.Draw(im)
            d.text((8,32),f'{si+1}/{len(names)}  {name}',font=font,fill=1)
            for row,codec in enumerate(codecs[page*6:page*6+6]):
                entry=entries[si*len(codecs)+page*6+row]
                value=display_bytes(entry)
                d.text((246-d.textlength(value,font=font),62+row*16),value,font=font,fill=1)
            assets.append(rle(pixels(im)))
            # Preview the actual composed menu; no substitute font.
            base=Image.open(out/f'base-page-{page+1}.png').resize((256,192)).convert('1')
            from PIL import ImageChops
            combined=ImageChops.logical_or(base,im)
            cd=ImageDraw.Draw(combined)
            cd.line([(x,180+round(3*math.sin(2*math.pi*x/32))) for x in range(64,192)],fill=1)
            combined.resize((768,576)).save(out/f'menu-{si+1}-{page+1}.png')
    return assets,pages

ASM='''; Full-control AROS. Only DOCK4 is resident. ROM payload is staged while DI.
state equ $c210
wave_src equ $c220
ui equ $c230
; ui+0 sample,+1 codec,+2 PCM guard,+3 menu page. Loader scratch+4..15.
demo:
 di
 ld a,$10
 out ($f4),a
 xor a
 out ($ff),a
 out ($fe),a
 ld sp,$c2ff
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
 ld (ui),a
 ld (ui+1),a
 ld (ui+2),a
 ; Expand16 small32-pixel wave tiles to16 centered128-pixel frames in HOME5.
 ld hl,wave_tiles
 ld de,$a000
 ld a,128
tile_row:
 push af
 ld b,4
tile_repeat:
 push bc
 push hl
 ld bc,4
 ldir
 pop hl
 pop bc
 djnz tile_repeat
 ld bc,4
 add hl,bc
 pop af
 dec a
 jr nz,tile_row
 ld hl,$a000
 ld (wave_src),hl
refresh:
 di
 call redraw
 ei
menu:
 halt
 ld bc,$fbfe
 in a,(c)
 bit 0,a
 jr z,up
 ld bc,$fdfe
 in a,(c)
 bit 0,a
 jr z,down
 ld bc,$dffe
 in a,(c)
 bit 1,a
 jr z,previous_sample
 bit 0,a
 jr z,next_sample
 ld bc,$7ffe
 in a,(c)
 bit 0,a
 jp z,play
 jr menu
up:
 ld a,(ui+1)
 or a
 jr z,release
 dec a
 ld (ui+1),a
 jr release
down:
 ld a,(ui+1)
 cp CODEC_COUNT-1
 jr z,release
 inc a
 ld (ui+1),a
 jr release
previous_sample:
 ld a,(ui)
 or a
 jr z,release
 dec a
 ld (ui),a
 jr release
next_sample:
 ld a,(ui)
 cp SAMPLE_COUNT-1
 jr z,release
 inc a
 ld (ui),a
release:
 halt
 ld bc,$00fe
 in a,(c)
 and 31
 cp 31
 jr nz,release
 jp refresh
; A=record index, resolved to its segment list. All mappings restore $10.
load_record:
 push af
 ld l,a
 ld h,0
 ld de,record_compression
 add hl,de
 ld a,(hl)
 ld (ui+16),a
 pop af
 ld l,a
 ld h,0
 add hl,hl
 ld de,records
 add hl,de
 ld e,(hl)
 inc hl
 ld d,(hl)
 ex de,hl
 ld a,(hl)
 ld (ui+4),a
 inc hl
 ld (ui+6),hl
 ld de,$d000
 ld (ui+12),de
load_segment:
 ld hl,(ui+6)
 ld a,(hl)
 ld (ui+8),a
 inc hl
 ld e,(hl)
 inc hl
 ld d,(hl)
 inc hl
 ld c,(hl)
 inc hl
 ld b,(hl)
 inc hl
 ld (ui+6),hl
 ld (ui+10),bc
 ex de,hl
 ld de,$7c00
 cp $18
 jr nz,bounce_ready
 ld de,$5b00
bounce_ready:
 ; No CALL/PUSH/POP or RAM-state access between these HSR writes.
 ; Even DOCK6 may hide the stack safely while this straight-line LDIR runs.
 out ($f4),a
 ldir
 ld a,$10
 out ($f4),a
 ld hl,$7c00
 ld a,(ui+8)
 cp $18
 jr nz,bounce_read
 ld hl,$5b00
bounce_read:
 ld de,(ui+12)
 ld bc,(ui+10)
 ldir
 ld (ui+12),de
 ld a,(ui+4)
 dec a
 ld (ui+4),a
 jr nz,load_segment
record_loaded:
 ld a,(ui+16)
 or a
 ret z
 ; Stored bytes fit A800..BFFF. Restore HOME before using this scratch.
 ; Expand into D000 only after the entire compressed record has been copied.
 ld hl,(ui+12)
 ld de,$d000
 or a
 sbc hl,de
 ld b,h
 ld c,l
 ld hl,$d000
 ld de,$a800
 ldir
 ld hl,$a800
 ld de,$d000
 jp storage_unpack
; HL=compressed input, DE=output. The builder bounds both buffers.
; Literals1..127; token128..255 gives length3..130 and a16-bit back-distance.
; LDIR deliberately permits overlap for repeated patterns. Token0 terminates.
storage_unpack:
 ld a,(hl)
 inc hl
 or a
 ret z
 bit 7,a
 jr nz,storage_match
 ld c,a
 ld b,0
 ldir
 jr storage_unpack
storage_match:
 and 127
 add a,3
 ld c,(hl)
 inc hl
 ld b,(hl)
 inc hl
 push hl
 ld h,d
 ld l,e
 or a
 sbc hl,bc
 ld c,a
 ld b,0
 ldir
 pop hl
 jr storage_unpack
redraw:
 ld a,(ui+1)
 ld l,a
 ld h,0
 ld de,codec_pages
 add hl,de
 ld a,(hl)
 ld (ui+3),a
 add a,AUDIO_COUNT
 call load_record
 ld hl,$d000
 ld de,$4000
 call unpack
 ld a,(ui)
 ld l,a
 ld h,0
 ld de,overlay_bases
 add hl,de
 ld a,(ui+3)
 add a,(hl)
 call load_record
 ld hl,$d000
 ld de,$4000
 call overlay
 ld a,(ui+1)
 ld l,a
 ld h,0
 ld de,marker_addresses
 add hl,hl
 add hl,de
 ld e,(hl)
 inc hl
 ld d,(hl)
 ld a,$5e
 ld (de),a
 ret
unpack:
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
 jr unpack
overlay:
 ld a,(hl)
 inc hl
 or a
 ret z
 ld b,a
 ld c,(hl)
 inc hl
overlay_run:
 ld a,(de)
 or c
 ld (de),a
 inc de
 djnz overlay_run
 jr overlay
play:
 di
 call audio_init
 ld a,(ui)
 ld l,a
 ld h,0
 ld de,sample_bases
 add hl,de
 ld a,(ui+1)
 add a,(hl)
 ld (ui+14),a
 call load_record
 ld a,(ui+14)
 ld l,a
 ld h,0
 add hl,hl
 ld de,counts
 add hl,de
 ld e,(hl)
 inc hl
 ld d,(hl)
 push de
 ld a,(ui+14)
 ld l,a
 ld h,0
 ld de,backends
 add hl,de
 ld a,(hl)
 pop de
 ld hl,$d000
 cp 3
 jr z,tonal
 push af
 ld a,1
 ld (ui+2),a
 pop af
 or a
 jr nz,not5
 call dac5
 jr done
not5:
 dec a
 jr nz,is_dpcm
 call dac6
 jr done
is_dpcm:
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
done:
 xor a
 ld (ui+2),a
 ei
 jp release
isr:
 push af
 push bc
 push de
 push hl
 call ay_tick
 ld a,(ui+2)
 or a
 call z,wave_frame
 pop hl
 pop de
 pop bc
 pop af
 ei
 reti
; AY/idle: update the complete wave each60Hz interrupt.
wave_frame:
 ld hl,(wave_src)
 ld de,$50c8
 ld a,8
wave_row:
 push de
 ld bc,16
 ldir
 pop de
 inc d
 dec a
 jr nz,wave_row
 res 3,h
 ld (wave_src),hl
 ret
'''

def build_comparison(entries,out,pasmo):
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True)
    names=list(dict.fromkeys(e['name'] for e in entries))
    codecs=list(dict.fromkeys(e['codec'] for e in entries))
    order=['ay4-5k','ay4-6k','dpcm3-6k','harmonic1','optimized1',
           'harmonic2','optimized2','harmonic3','optimized3','audio2ay']
    codecs.sort(key=lambda codec:order.index(codec) if codec in order else len(order))
    lookup={(e['name'],e['codec']):e for e in entries}
    entries=[lookup[(name,c)] for name in names for c in codecs]
    if any(len(e['data'])>0x2e00 for e in entries):raise ValueError('A clip exceeds the D000..FDFF playback buffer')
    entries=[dict(e) for e in entries]
    audio_blobs=[];compression=[]
    for entry in entries:
        packed=compress(entry['data'])
        use=len(packed)<len(entry['data']) and len(packed)<=0x1800
        audio_blobs.append(packed if use else entry['data'])
        compression.append(int(use))
        entry['stored_bytes']=len(audio_blobs[-1])
        entry['compact_estimate']=compact_estimate(entry)
    assets,pages=artwork(names,codecs,entries,out)
    decoded_blobs=[e['data'] for e in entries]+assets
    blobs=audio_blobs+assets
    compression += [0]*len(assets)
    spectra=all('spectrum' in e for e in entries)
    spectrum_first=len(blobs)
    if spectra:
        from . import spectrum_ui
        for i,e in enumerate(entries):
            heights=e['spectrum']['heights']
            if len(heights)!=64 or any(not 0<=h<=31 for h in heights):raise ValueError('Invalid spectrum heights')
            blobs.append(bytes(heights));decoded_blobs.append(bytes(heights));compression.append(0)
            im=spectrum_ui.preview(e['name'],i//len(codecs),len(names),LABELS.get(e['codec'],e['codec']),display_bytes(e),heights)
            screen=bytearray(pixels(im,7));screen[0x1a20:0x1aa0]=bytes([5])*128
            (out/f'spectrum-{i+1}.scr').write_bytes(screen)
            im.resize((768,576)).save(out/f'spectrum-{i+1}.png')
        spectrum_background=len(blobs)
        packed=rle(pixels(spectrum_ui.background())[2048:6144])
        blobs.append(packed);decoded_blobs.append(packed);compression.append(0)
    chunks=[0,1,2,3,5,6,7];flat=bytearray(b'\xff'*65536);logical=0;descriptors=[]
    for blob in blobs:
        segments=[];at=0
        while at<len(blob):
            slot,offset=divmod(logical,8192)
            if slot>=len(chunks):raise ValueError(f'Comparison payload exceeds56K ({sum(map(len,blobs))} bytes)')
            chunk=chunks[slot];n=min(256,len(blob)-at,8192-offset);addr=chunk*8192+offset
            flat[addr:addr+n]=blob[at:at+n];segments.append((16|(1<<chunk),addr,n));at+=n;logical+=n
        if len(segments)>255:raise ValueError('Too many record segments')
        descriptors.append(segments)
    if len(blobs)>255:raise ValueError('Comparison supports at most255 audio/UI records')
    tiles=bytearray()
    for phase in range(16):
        for y in range(8):
            bits=sum(1<<(31-x) for x in range(32) if y==4+round(3*math.sin(2*math.pi*(x-phase*2)/32)))
            tiles+=bits.to_bytes(4,'big')
    (out/'wave-tiles.bin').write_bytes(tiles)
    source=' org $8000\n defb 2,2,8,$80,$ef,1,0,0\n jp demo\n'
    source+=f'CODEC_COUNT equ {len(codecs)}\nSAMPLE_COUNT equ {len(names)}\nAUDIO_COUNT equ {len(entries)}\n'
    demo=ASM
    if spectra:
        demo=demo.replace(' ld (ui+2),a\n',' ld (ui+2),a\n ld (ui+17),a\n',1)
        demo=demo.replace(' jr z,down\n',' jr z,down\n bit 1,a\n jp z,spectrum_toggle\n',1)
        demo=demo.replace('redraw:\n','redraw:\n ld a,(ui+17)\n or a\n jp nz,redraw_spectrum\nredraw_menu:\n',1)
        source+=f'SPECTRA_FIRST equ {spectrum_first}\nSPECTRA_BACKGROUND equ {spectrum_background}\n'
    source+=runtime(animated='scroll')+demo
    if spectra:
        source+=spectrum_ui.ASM
        source+='spectrum_row_addresses: defw '+','.join(str(0x4000+spectrum_ui.offset(64+(i%6)*16)) for i in range(len(codecs)))+'\n'
    source+='record_compression: defb '+','.join(map(str,compression))+'\n'
    source+='codec_pages: defb '+','.join(str(i//6) for i in range(len(codecs)))+'\n'
    source+='overlay_bases: defb '+','.join(str(len(entries)+pages+i*pages) for i in range(len(names)))+'\n'
    source+='sample_bases: defb '+','.join(str(i*len(codecs)) for i in range(len(names)))+'\n'
    source+='marker_addresses: defw '+','.join(str(0x5800+(8+2*(i%6))*32) for i in range(len(codecs)))+'\n'
    source+='counts: defw '+','.join(str(e['count']) for e in entries)+'\n'
    source+='backends: defb '+','.join(str({'ay4-5k':0,'ay4-6k':1,'dpcm3-6k':2}.get(e['codec'],3)) for e in entries)+'\n'
    source+='records: defw '+','.join(f'record_{i}' for i in range(len(blobs)))+'\n'
    for i,segments in enumerate(descriptors):
        source+=f'record_{i}: defb {len(segments)}\n'
        for mask,addr,n in segments:source+=f' defb {mask}\n defw {addr},{n}\n'
    source+='wave_tiles: incbin "wave-tiles.bin"\n'
    raw,sym=assemble(source,out,pasmo)
    if len(raw)>8192:raise ValueError(f'Resident code/tables exceed8K: {len(raw)} bytes')
    flat[0x8000:0x8000+len(raw)]=raw
    (out/'comparison.dck').write_bytes(bytes([0]+[2]*8)+flat)
    (out/'picorom.bin').write_bytes(flat)
    for i,blob in enumerate(blobs):
        check=b''.join(flat[addr:addr+n] for _,addr,n in descriptors[i]);assert check==blob
    assert all((decompress(blob) if flag else blob)==original for blob,flag,original in zip(blobs,compression,decoded_blobs))
    manifest={'version':4 if spectra else 3,'resident_bytes':len(raw),'payload_bytes':logical,'symbols':sym,'spectra':spectra,
              'record_compression':compression,'record_decoded_bytes':list(map(len,decoded_blobs)),
              'sample_names':names,'codecs':codecs,'records':descriptors,
              'entries':[{k:v for k,v in e.items() if k!='data'}|{'bytes':len(e['data'])} for e in entries]}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2))
    return manifest
