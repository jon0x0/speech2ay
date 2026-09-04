"""Small cartridge FFT display: offline heights, runtime two-pixel bars."""
from PIL import Image, ImageDraw, ImageFont

def offset(y):
    return ((y&192)<<5)|((y&7)<<8)|((y&56)<<2)

def background():
    im=Image.new('1',(256,192));d=ImageDraw.Draw(im);font=ImageFont.load_default()
    d.text((8,64),'Original          0 to -48 dB',font=font,fill=1)
    d.line((32,112,224,112),fill=1)
    d.text((32,112),'80 Hz',font=font,fill=1)
    d.text((112,112),'log frequency',font=font,fill=1)
    d.text((207,112),'7k',font=font,fill=1)
    d.text((8,124),'Modeled output',font=font,fill=1)
    d.line((32,168,224,168),fill=1)
    d.text((8,182),'S menu   Full clip / RMS matched',font=font,fill=1)
    return im

def preview(name,index,total,codec_label,stored,heights):
    im=background();d=ImageDraw.Draw(im);font=ImageFont.load_default()
    d.text((8,2),'TS2068 AUDIO LAB',font=font,fill=1)
    d.text((8,18),'O/P sample    Q/A codec    SPACE play',font=font,fill=1)
    d.text((8,32),f'{index+1}/{total}  {name}',font=font,fill=1)
    d.text((16,46),codec_label,font=font,fill=1)
    value=str(stored);d.text((246-d.textlength(value,font=font),46),value,font=font,fill=1)
    for panel,baseline in enumerate((112,168)):
        for column,height in enumerate(heights[panel*32:panel*32+32]):
            if height:d.rectangle((32+column*6,baseline-height,33+column*6,baseline-1),fill=1)
    return im

ASM='''
; S toggles a precomputed whole-clip FFT view. Never computes FFTs on the Z80.
spectrum_toggle:
 ld a,(ui+17)
 xor 1
 ld (ui+17),a
 jp release
redraw_spectrum:
 call redraw_menu
 ; Move the chosen codec/byte-count glyph row into the spectrum header.
 ld a,(ui+1)
 ld l,a
 ld h,0
 add hl,hl
 ld de,spectrum_row_addresses
 add hl,de
 ld e,(hl)
 inc hl
 ld d,(hl)
 ex de,hl
 ld de,$40c0
 ld b,2
spectrum_header_block:
 push bc
 ld a,8
spectrum_header_row:
 push hl
 push de
 ld bc,32
 ldir
 pop de
 pop hl
 inc h
 inc d
 dec a
 jr nz,spectrum_header_row
 pop bc
 dec b
 jr z,spectrum_header_done
 ld a,h
 sub 8
 ld h,a
 ld a,l
 add a,32
 ld l,a
 ld a,d
 sub 8
 ld d,a
 ld a,e
 add a,32
 ld e,a
 jr spectrum_header_block
spectrum_header_done:
 ld a,SPECTRA_BACKGROUND
 call load_record
 ld hl,$d000
 ld de,$4800
 call unpack
 ; Remove the menu cursor and give the modeled plot cyan attributes.
 ld hl,$58c0
 ld de,$58c1
 ld bc,575
 ld (hl),7
 ldir
 ld hl,$5a20
 ld de,$5a21
 ld bc,127
 ld (hl),5
 ldir
 ld a,(ui)
 ld l,a
 ld h,0
 ld de,sample_bases
 add hl,de
 ld a,(ui+1)
 add a,(hl)
 add a,SPECTRA_FIRST
 call load_record
 ld hl,$d000
 ld d,112
 call spectrum_bars
 ld d,168
 jp spectrum_bars
; HL=32 heights (0..31), D=baseline Y. Width2, spacing6, x32..219.
spectrum_bars:
 ld c,32
 ld b,32
spectrum_column:
 ld a,(hl)
 inc hl
 push bc
 push hl
 ld b,d
spectrum_vertical:
 or a
 jr z,spectrum_column_done
 dec b
 push af
 call spectrum_pixel
 pop af
 dec a
 jr spectrum_vertical
spectrum_column_done:
 pop hl
 pop bc
 ld a,c
 add a,6
 ld c,a
 djnz spectrum_column
 ret
; Plot two adjacent pixels at B=y,C=x, preserving BC/DE/HL.
; x is even so the two-pixel mask never crosses a byte boundary.
spectrum_pixel:
 push bc
 push de
 push hl
 ld a,c
 and 7
 ld l,a
 ld h,0
 ld de,spectrum_masks
 add hl,de
 ld e,(hl)
 ld a,b
 and $38
 rlca
 rlca
 ld d,a
 ld a,c
 rrca
 rrca
 rrca
 and 31
 or d
 ld l,a
 ld a,b
 and 7
 or $40
 ld h,a
 ld a,b
 and $c0
 rrca
 rrca
 rrca
 or h
 ld h,a
 ld a,(hl)
 or e
 ld (hl),a
 pop hl
 pop de
 pop bc
 ret
spectrum_masks: defb $c0,0,$30,0,$0c,0,$03,0
'''
