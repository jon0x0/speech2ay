"""Generate cycle-budgeted packed DAC loops; export readable Pasmo source."""
from .codecs import DELTAS

def pad(t, label, preserve=False):
    for n in ([0] if preserve else range(40,-1,-1)):
        rest=t-(13*n+2 if n else 0)
        for sevens in range(8):
            fours=rest-7*sevens
            if fours>=0 and fours%4==0:
                return (f' ld b,{n}\n{label}: djnz {label}\n' if n else '')+' ld b,0\n'*sevens+' nop\n'*(fours//4)
    raise ValueError(f'Cannot pad {t} T states')

def dac(name, bits, count, periods, animated=False):
    scroll = animated == 'scroll'
    preparation = 166 if scroll else 200
    out=f'''; {name}: HL=packed data, DE=nonzero group count. DI on entry/return.
; Clobbers AF BC DE HL IX IY. No self-modifying code.
; AY4 low nibble first; DPCM3 LSB-first groups, accumulator starts at11.
; Each output has{preparation}T preparation,12T OUT, then padding/group work.
; Replace padding ONLY with equal-cycle bounded work. Interrupts stay disabled.
{name}:
 push hl
 push de
 call audio_init
 pop de
 pop hl
 ld a,d
 or e
 ret z
 push hl
 pop ix
 push de
 pop iy
 ld a,11
 ld (state+4),a
{name}_loop:
'''
    for i in range(count):
        bit=i*bits; offset,shift=divmod(bit,8)
        code=f' ld a,(ix+{offset})\n'+' rrca\n'*shift
        cost=19+4*shift
        if shift+bits>8:
            first=8-shift
            code+=f' and {(1<<first)-1}\n ld e,a\n ld a,(ix+{offset+1})\n and {(1<<(bits-first))-1}\n'+' rlca\n'*first+' or e\n'
            cost+=7+4+19+7+4*first+4
        else:
            code+=f' and {(1<<bits)-1}\n';cost+=7
        if bits==3:
            code+=' ld l,a\n ld a,(state+4)\n rlca\n rlca\n rlca\n or l\n ld l,a\n ld h,delta_table / 256\n ld a,(hl)\n ld (state+4),a\n'
            cost+=4+13+12+4+4+7+7+13
        out+=f'; Sample {i}: decode {cost}T; interval {periods[i%len(periods)]}T.\n'+code
        out+=pad(preparation-cost-10,f'{name}_pre{i}',True)+' ld bc,$fff6\n'
        out+=f'{name}_out{i}: out (c),a\n'
        tail=0
        if i==count-1:
            tail=count*bits//8*10+36+(133 if animated and not scroll else 0)
        if scroll:out+=scroll_slot(f'{name}_scroll{i}',periods[i%len(periods)])
        out+=pad(periods[i%len(periods)]-preparation-12-tail-(340 if scroll else 0),f'{name}_wait{i}')
        if i==count-1:
            if animated and not scroll:out+=flip(name,sum(periods))
            out+=' inc ix\n'*(count*bits//8)+f' dec iy\n ld a,iyh\n or iyl\n jp nz,{name}_loop\n'
    if scroll:
        out=out.replace(f'{name}_loop:', ' ld hl,0\n ld (state+10),hl\n exx\n ld hl,(wave_src)\n ld de,$50c8\n exx\n ei\n halt\n di\n'+f'{name}_loop:',1)
        out+=" exx\n ld a,l\n and 128\n ld l,a\n ld (wave_src),hl\n exx\n"
    elif animated:
        out=out.replace(f'{name}_loop:', ' xor a\n ld (state+12),a\n ld hl,0\n ld (state+10),hl\n ei\n halt\n di\n'+f'{name}_loop:',1)
    return out+' jp audio_stop\n'


def scroll_slot(name,period):
    """340T on every path. Eight wave bytes copied only during blanking.

    Alternate HL/DE retain wave source/destination. Sixteen128-byte frames
    at HOME A000..A7FF; display band is primary y176..183. The short demo ISR
    is required for the initial EI/HALT synchronization. No paging here.
    """
    return f''' ld hl,(state+10)
 ld de,{period}
 add hl,de
 ld de,58688
 or a
 sbc hl,de
 jr c,{name}_nowrap
 ld (state+10),hl
 inc bc
 jp {name}_phase
{name}_nowrap:
 add hl,de
 ld (state+10),hl
{name}_phase:
 ; Phase normalization105T. Permit copies below7168T only.
 ld a,h
 cp 28
 jr c,{name}_copy
'''+pad(207,name+'_idle')+f''' jp {name}_done
{name}_copy:
 exx
'''+ ' ldi\n'*8+f''' bit 3,e
 jr z,{name}_row
 inc d
 ld e,$c8
 jp {name}_next
{name}_row:
 nop
 nop
 nop
 nop
{name}_next:
 res 3,d
 res 3,h
 exx
'''+ ' nop\n'*6+f'{name}_done:\n'

def runtime(animated=False):
    text='''; TS2068 audio-tools reference runtime. CPU3528000Hz, AY1764750Hz.
; All state is native HOME RAM at STATE (16 bytes); never select DOCK6.
; API jump table: init,+3 AY4/5k,+6 AY4/6k,+9 DPCM3/6k,
; +12 AY start,+15 AY tick,+18 stop. Caller owns interrupt/memory mapping.
; Init/start/stop must be serialized with ISR (DI). Tick does not EI or RETI.
audio_api:
 jp audio_init
 jp dac5
 jp dac6
 jp dpcm6
 jp ay_start
 jp ay_tick
 jp audio_stop
audio_init:
 xor a
 ld (state),a
 ld (state+1),a
 ld (state+2),a
 ld (state+3),a
 ld e,7
 ld a,63
 call ay_write
 call audio_stop
 ld e,8
 ld bc,$fff5
 out (c),e
 ret
; E=register,A=value. Preserves A/DE/HL; clobbers BC.
ay_write:
 ld bc,$fff5
 out (c),e
 ld bc,$fff6
 out (c),a
 ret
audio_stop:
 xor a
 out ($ff),a
 ld (state+2),a
 ld (state+3),a
 ld (state+5),a
 ld e,8
 call ay_write
 inc e
 call ay_write
 inc e
 jp ay_write
; HL=address of14-byte frames, DE=frame count. Data may be ROM or RAM.
; R0..12 always written. R13=255 skips envelope restart. R14/15 untouched.
ay_start:
 ld (state),hl
 ld (state+2),de
 ld a,1
 ld (state+5),a
 ret
ay_tick:
 ld hl,(state+2)
 ld a,h
 or l
 jp z,ay_finish
 dec hl
 ld (state+2),hl
 ld hl,(state)
 ld e,0
ay_next:
 ld a,(hl)
 call ay_write
 inc hl
 inc e
 ld a,e
 cp 13
 jr nz,ay_next
 ld a,(hl)
 inc hl
 cp 255
 jr z,ay_no_shape
 call ay_write
ay_no_shape:
 ld (state),hl
 ret
'''
    text+='ay_finish:\n ld a,(state+5)\n or a\n ret z\n jp audio_stop\n'
    text+=dac('dac5',4,10,[705,706,705,706,706]*2,animated)
    text+=dac('dac6',4,2,[588,588],animated)
    text+=dac('dpcm6',3,8,[588]*8,animated)
    text+=' defs (256-($ % 256)) % 256,0\ndelta_table:\n'
    vals=[min(15,max(0,p+d)) for p in range(16) for d in DELTAS]
    text+=' defb '+','.join(map(str,vals))+'\n'
    return text


def flip(name,group_t):
    #133T either branch. Writes only in first group after frame wrap.
    return f""" ld hl,(state+10)
 ld de,{58688-group_t}
 or a
 sbc hl,de
 jr c,{name}_no_flip
 ld (state+10),hl
 ld a,(state+12)
 xor 1
 ld (state+12),a
 ld bc,$ffff
 out (c),a
 jp {name}_flipped
{name}_no_flip:
 add hl,de
 ld de,{group_t}
 add hl,de
 ld (state+10),hl
"""+' nop\n'*7+f'{name}_flipped:\n'
