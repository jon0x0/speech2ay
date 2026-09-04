"""Exercise every banked record and every composed menu in real Fuse."""
import argparse,json,re,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tsaudio.build import assemble
from tsaudio.storage import decode
from run_fuse_debug import run_fuse

def checksum(data):
    a=b=0
    for v in data:a=(a+v)&255;b=(b+a)&255
    return a*256+b

def unrle(data):
    out=bytearray();i=0
    while data[i]:out.extend(bytes([data[i+1]])*data[i]);i+=2
    assert len(out)==6912
    return out

def main():
    p=argparse.ArgumentParser();p.add_argument('directory',type=Path);p.add_argument('--pasmo',required=True);p.add_argument('--fuse',required=True,type=Path);a=p.parse_args()
    folder=a.directory.resolve();m=json.loads((folder/'manifest.json').read_text());rom=(folder/'picorom.bin').read_bytes()
    blobs=[b''.join(rom[addr:addr+n] for _,addr,n in record) for record in m['records']]
    blobs=[decode(blob) if flag else blob for blob,flag in zip(blobs,m.get('record_compression',[0]*len(blobs)))]
    expected=[checksum(blob) for blob in blobs]
    n=len(m['entries']);pages=(len(m['codecs'])+5)//6
    lines=['test_sequence:','xor a','ld ($c250),a','test_record:','call load_record',
           'ld a,($c250)','ld l,a','ld h,0','add hl,hl','ld de,test_lengths','add hl,de',
           'ld c,(hl)','inc hl','ld b,(hl)','ld hl,$d000','call checksum','call report_result',
           'ld a,($c250)','inc a','ld ($c250),a',f'cp {len(blobs)}','jr nz,test_record',
           'xor a','ld (ui),a','ld (ui+1),a','ld (ui+17),a','test_menu:',
           'call redraw','ld hl,$4000','ld bc,6912','call checksum','call report_result']
    if m.get('spectra'):
        lines+=['ld a,1','ld (ui+17),a','call redraw','ld hl,$4000','ld bc,6912','call checksum','call report_result','xor a','ld (ui+17),a']
    lines+=['ld a,(ui+1)','inc a','cp CODEC_COUNT','jr z,test_sample','ld (ui+1),a','jr test_menu',
            'test_sample: xor a','ld (ui+1),a','ld a,(ui)','inc a','cp SAMPLE_COUNT','jr z,test_done','ld (ui),a','jr test_menu']
    for sample in range(len(m['sample_names'])):
        for codec in range(len(m['codecs'])):
            page=codec//6;base=unrle(blobs[n+page]);overlay=unrle(blobs[n+pages+sample*pages+page])
            image=bytearray(x|y for x,y in zip(base,overlay));image[6144+(8+2*(codec%6))*32]=0x5e
            expected.append(checksum(image))
            if m.get('spectra'):
                expected.append(checksum((folder/f'spectrum-{sample*len(m["codecs"])+codec+1}.scr').read_bytes()))
    lines+=['test_done: jp test_done','report_result: ret','checksum: ld de,0','sum_loop: ld a,(hl)','inc hl','add a,d','ld d,a','add a,e','ld e,a','dec bc','ld a,b','or c','jr nz,sum_loop','ret']
    lines+=['test_lengths: defw '+','.join(str(len(blob)) for blob in blobs)]
    src=(folder/'player.asm').read_text().replace(' call redraw\n ei\nmenu:',' call redraw\n di\nmenu:\n jp test_sequence',1)+'\n'+'\n'.join(lines)+'\n'
    test=folder/'verification';test.mkdir(exist_ok=True)
    (test/'wave-tiles.bin').write_bytes((folder/'wave-tiles.bin').read_bytes())
    raw,s=assemble(src,test,a.pasmo)
    if len(raw)>8192:raise AssertionError(f'Test harness exceeds resident chunk:{len(raw)}')
    image=bytearray(rom);image[32768:40960]=raw.ljust(8192,b'\xff');(test/'test.dck').write_bytes(bytes([0]+[2]*8)+image)
    command=f'''breakpoint {s['report_result']}
commands 1
print z80:de
continue
end
breakpoint {s['test_done']}
commands 2
exit 0
end'''
    r=run_fuse(machine='ts2068',media=test/'test.dck',fuse=a.fuse,debugger_command=command,timeout=35)
    (test/'trace.log').write_text(r.stdout+r.stderr)
    actual=[int(x,16) for x in re.findall(r'^0x([0-9a-f]+)$',r.stdout,re.M|re.I)]
    assert actual==expected,[(i,x,expected[i]) for i,x in enumerate(actual) if x!=expected[i]] or (len(actual),len(expected))
    report={'records':len(blobs),'menus':len(m['entries']),'spectrum_views':len(m['entries']) if m.get('spectra') else 0,'ROM_chunks_read':sorted({(mask^16).bit_length()-1 for row in m['records'] for mask,_,_ in row}),'runtime_checksums_match':True}
    (test/'result.json').write_text(json.dumps(report,indent=2));print(report)
if __name__=='__main__':main()
