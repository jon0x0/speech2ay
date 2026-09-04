; Assemble with an ORG and state EQU $C210 preceding this file.
; TS2068 audio-tools reference runtime. CPU3528000Hz, AY1764750Hz.
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
ay_finish:
 ld a,(state+5)
 or a
 ret z
 jp audio_stop
; dac5: HL=packed data, DE=nonzero group count. DI on entry/return.
; Clobbers AF BC DE HL IX IY. No self-modifying code.
; AY4 low nibble first; DPCM3 LSB-first groups, accumulator starts at11.
; Each output has200T preparation,12T OUT, then padding/group work.
; Replace padding ONLY with equal-cycle bounded work. Interrupts stay disabled.
dac5:
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
dac5_loop:
; Sample 0: decode 26T; interval 705T.
 ld a,(ix+0)
 and 15
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 ld bc,$fff6
dac5_out0: out (c),a
 ld b,36
dac5_wait0: djnz dac5_wait0
 ld b,0
 nop
 nop
 nop
 nop
; Sample 1: decode 42T; interval 706T.
 ld a,(ix+0)
 rrca
 rrca
 rrca
 rrca
 and 15
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 ld bc,$fff6
dac5_out1: out (c),a
 ld b,37
dac5_wait1: djnz dac5_wait1
 ld b,0
 nop
; Sample 2: decode 26T; interval 705T.
 ld a,(ix+1)
 and 15
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 ld bc,$fff6
dac5_out2: out (c),a
 ld b,36
dac5_wait2: djnz dac5_wait2
 ld b,0
 nop
 nop
 nop
 nop
; Sample 3: decode 42T; interval 706T.
 ld a,(ix+1)
 rrca
 rrca
 rrca
 rrca
 and 15
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 ld bc,$fff6
dac5_out3: out (c),a
 ld b,37
dac5_wait3: djnz dac5_wait3
 ld b,0
 nop
; Sample 4: decode 26T; interval 706T.
 ld a,(ix+2)
 and 15
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 ld bc,$fff6
dac5_out4: out (c),a
 ld b,37
dac5_wait4: djnz dac5_wait4
 ld b,0
 nop
; Sample 5: decode 42T; interval 705T.
 ld a,(ix+2)
 rrca
 rrca
 rrca
 rrca
 and 15
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 ld bc,$fff6
dac5_out5: out (c),a
 ld b,36
dac5_wait5: djnz dac5_wait5
 ld b,0
 nop
 nop
 nop
 nop
; Sample 6: decode 26T; interval 706T.
 ld a,(ix+3)
 and 15
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 ld bc,$fff6
dac5_out6: out (c),a
 ld b,37
dac5_wait6: djnz dac5_wait6
 ld b,0
 nop
; Sample 7: decode 42T; interval 705T.
 ld a,(ix+3)
 rrca
 rrca
 rrca
 rrca
 and 15
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 ld bc,$fff6
dac5_out7: out (c),a
 ld b,36
dac5_wait7: djnz dac5_wait7
 ld b,0
 nop
 nop
 nop
 nop
; Sample 8: decode 26T; interval 706T.
 ld a,(ix+4)
 and 15
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 ld bc,$fff6
dac5_out8: out (c),a
 ld b,37
dac5_wait8: djnz dac5_wait8
 ld b,0
 nop
; Sample 9: decode 42T; interval 706T.
 ld a,(ix+4)
 rrca
 rrca
 rrca
 rrca
 and 15
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 ld bc,$fff6
dac5_out9: out (c),a
 ld b,30
dac5_wait9: djnz dac5_wait9
 nop
 nop
 nop
 nop
 inc ix
 inc ix
 inc ix
 inc ix
 inc ix
 dec iy
 ld a,iyh
 or iyl
 jp nz,dac5_loop
 jp audio_stop
; dac6: HL=packed data, DE=nonzero group count. DI on entry/return.
; Clobbers AF BC DE HL IX IY. No self-modifying code.
; AY4 low nibble first; DPCM3 LSB-first groups, accumulator starts at11.
; Each output has200T preparation,12T OUT, then padding/group work.
; Replace padding ONLY with equal-cycle bounded work. Interrupts stay disabled.
dac6:
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
dac6_loop:
; Sample 0: decode 26T; interval 588T.
 ld a,(ix+0)
 and 15
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 ld bc,$fff6
dac6_out0: out (c),a
 ld b,27
dac6_wait0: djnz dac6_wait0
 ld b,0
 nop
 nop
 nop
 nop
; Sample 1: decode 42T; interval 588T.
 ld a,(ix+0)
 rrca
 rrca
 rrca
 rrca
 and 15
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 ld bc,$fff6
dac6_out1: out (c),a
 ld b,24
dac6_wait1: djnz dac6_wait1
 nop
 nop
 nop
 nop
 inc ix
 dec iy
 ld a,iyh
 or iyl
 jp nz,dac6_loop
 jp audio_stop
; dpcm6: HL=packed data, DE=nonzero group count. DI on entry/return.
; Clobbers AF BC DE HL IX IY. No self-modifying code.
; AY4 low nibble first; DPCM3 LSB-first groups, accumulator starts at11.
; Each output has200T preparation,12T OUT, then padding/group work.
; Replace padding ONLY with equal-cycle bounded work. Interrupts stay disabled.
dpcm6:
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
dpcm6_loop:
; Sample 0: decode 90T; interval 588T.
 ld a,(ix+0)
 and 7
 ld l,a
 ld a,(state+4)
 rlca
 rlca
 rlca
 or l
 ld l,a
 ld h,delta_table / 256
 ld a,(hl)
 ld (state+4),a
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 ld bc,$fff6
dpcm6_out0: out (c),a
 ld b,27
dpcm6_wait0: djnz dpcm6_wait0
 ld b,0
 nop
 nop
 nop
 nop
; Sample 1: decode 102T; interval 588T.
 ld a,(ix+0)
 rrca
 rrca
 rrca
 and 7
 ld l,a
 ld a,(state+4)
 rlca
 rlca
 rlca
 or l
 ld l,a
 ld h,delta_table / 256
 ld a,(hl)
 ld (state+4),a
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 ld bc,$fff6
dpcm6_out1: out (c),a
 ld b,27
dpcm6_wait1: djnz dpcm6_wait1
 ld b,0
 nop
 nop
 nop
 nop
; Sample 2: decode 156T; interval 588T.
 ld a,(ix+0)
 rrca
 rrca
 rrca
 rrca
 rrca
 rrca
 and 3
 ld e,a
 ld a,(ix+1)
 and 1
 rlca
 rlca
 or e
 ld l,a
 ld a,(state+4)
 rlca
 rlca
 rlca
 or l
 ld l,a
 ld h,delta_table / 256
 ld a,(hl)
 ld (state+4),a
 ld b,0
 ld b,0
 nop
 nop
 nop
 nop
 nop
 ld bc,$fff6
dpcm6_out2: out (c),a
 ld b,27
dpcm6_wait2: djnz dpcm6_wait2
 ld b,0
 nop
 nop
 nop
 nop
; Sample 3: decode 94T; interval 588T.
 ld a,(ix+1)
 rrca
 and 7
 ld l,a
 ld a,(state+4)
 rlca
 rlca
 rlca
 or l
 ld l,a
 ld h,delta_table / 256
 ld a,(hl)
 ld (state+4),a
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 ld bc,$fff6
dpcm6_out3: out (c),a
 ld b,27
dpcm6_wait3: djnz dpcm6_wait3
 ld b,0
 nop
 nop
 nop
 nop
; Sample 4: decode 106T; interval 588T.
 ld a,(ix+1)
 rrca
 rrca
 rrca
 rrca
 and 7
 ld l,a
 ld a,(state+4)
 rlca
 rlca
 rlca
 or l
 ld l,a
 ld h,delta_table / 256
 ld a,(hl)
 ld (state+4),a
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 ld bc,$fff6
dpcm6_out4: out (c),a
 ld b,27
dpcm6_wait4: djnz dpcm6_wait4
 ld b,0
 nop
 nop
 nop
 nop
; Sample 5: decode 156T; interval 588T.
 ld a,(ix+1)
 rrca
 rrca
 rrca
 rrca
 rrca
 rrca
 rrca
 and 1
 ld e,a
 ld a,(ix+2)
 and 3
 rlca
 or e
 ld l,a
 ld a,(state+4)
 rlca
 rlca
 rlca
 or l
 ld l,a
 ld h,delta_table / 256
 ld a,(hl)
 ld (state+4),a
 ld b,0
 ld b,0
 nop
 nop
 nop
 nop
 nop
 ld bc,$fff6
dpcm6_out5: out (c),a
 ld b,27
dpcm6_wait5: djnz dpcm6_wait5
 ld b,0
 nop
 nop
 nop
 nop
; Sample 6: decode 98T; interval 588T.
 ld a,(ix+2)
 rrca
 rrca
 and 7
 ld l,a
 ld a,(state+4)
 rlca
 rlca
 rlca
 or l
 ld l,a
 ld h,delta_table / 256
 ld a,(hl)
 ld (state+4),a
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 ld bc,$fff6
dpcm6_out6: out (c),a
 ld b,27
dpcm6_wait6: djnz dpcm6_wait6
 ld b,0
 nop
 nop
 nop
 nop
; Sample 7: decode 110T; interval 588T.
 ld a,(ix+2)
 rrca
 rrca
 rrca
 rrca
 rrca
 and 7
 ld l,a
 ld a,(state+4)
 rlca
 rlca
 rlca
 or l
 ld l,a
 ld h,delta_table / 256
 ld a,(hl)
 ld (state+4),a
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 nop
 ld bc,$fff6
dpcm6_out7: out (c),a
 ld b,22
dpcm6_wait7: djnz dpcm6_wait7
 ld b,0
 ld b,0
 nop
 nop
 inc ix
 inc ix
 inc ix
 dec iy
 ld a,iyh
 or iyl
 jp nz,dpcm6_loop
 jp audio_stop
 defs (256-($ % 256)) % 256,0
delta_table:
 defb 0,0,0,0,1,2,4,8,0,0,0,1,2,3,5,9,0,0,1,2,3,4,6,10,0,1,2,3,4,5,7,11,0,2,3,4,5,6,8,12,1,3,4,5,6,7,9,13,2,4,5,6,7,8,10,14,3,5,6,7,8,9,11,15,4,6,7,8,9,10,12,15,5,7,8,9,10,11,13,15,6,8,9,10,11,12,14,15,7,9,10,11,12,13,15,15,8,10,11,12,13,14,15,15,9,11,12,13,14,15,15,15,10,12,13,14,15,15,15,15,11,13,14,15,15,15,15,15
