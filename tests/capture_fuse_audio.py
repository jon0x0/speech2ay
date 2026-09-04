"""Capture Fuse's rendered PCM via its documented FMF movie recording."""
import argparse
from pathlib import Path
import subprocess
import wave
import zlib

def extract(path):
    raw=path.read_bytes();assert raw[:7]==b'FMF_V1e'
    # Debugger exit can omit the final zlib footer; retain complete chunks.
    data=zlib.decompressobj().decompress(raw[16:]) if raw[7:8]==b'Z' else raw[16:]
    screen=raw[9];at=0;pcm=bytearray();rate=channels=None
    while at<len(data):
        tag=data[at];at+=1
        if tag==ord('X'):break
        if tag==ord('N'):
            screen=data[at+1];at+=3
        elif tag==ord('$'):
            width=data[at+3];height=int.from_bytes(data[at+4:at+6],'little');at+=6
            for _ in range(3 if screen==ord('R') else 2):
                count=0;previous=None
                while count<width*height:
                    value=data[at];at+=1;count+=1
                    if value==previous:
                        count+=data[at];at+=1;previous=None
                    else:previous=value
                assert count==width*height
        elif tag==ord('S'):
            assert data[at]==ord('P'),'Use lossless PCM movie recording'
            new_rate=int.from_bytes(data[at+1:at+3],'little')
            new_channels=2 if data[at+3]==ord('S') else 1
            count=int.from_bytes(data[at+4:at+6],'little')+1;at+=6
            if rate is not None:assert (rate,channels)==(new_rate,new_channels)
            rate,channels=new_rate,new_channels
            size=count*channels*2;pcm.extend(data[at:at+size]);at+=size
        else:raise ValueError(f'Unknown FMF chunk {tag} at {at-1}')
    assert pcm,'Fuse did not record sound'
    with wave.open(str(path.with_suffix('.wav')),'wb') as wav:
        wav.setparams((channels,2,rate,0,'NONE','not compressed'));wav.writeframes(pcm)
    return len(pcm)/(2*channels*rate)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dock',required=True,type=Path)
    p.add_argument('--stop',required=True,type=lambda s:int(s,0))
    p.add_argument('--out',required=True,type=Path)
    p.add_argument('--fuse',required=True,type=Path)
    a=p.parse_args();a.out.parent.mkdir(parents=True,exist_ok=True)
    command=f'breakpoint {a.stop}\ncommands 1\nexit 0\nend'
    args=[str(a.fuse),'--machine','ts2068','--speed','100','--sound','--no-loading-sound',
          '--movie-start',str(a.out.resolve()),'--movie-compr','Lossless',
          '--dock',str(a.dock.resolve()),'--debugger-command',command]
    startup=subprocess.STARTUPINFO();startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW
    result=subprocess.run(args,capture_output=True,text=True,timeout=50,startupinfo=startup,creationflags=subprocess.CREATE_NO_WINDOW)
    a.out.with_suffix('.log').write_text(result.stdout+result.stderr)
    assert result.returncode==0,(result.returncode,result.stderr)
    print(a.out.with_suffix('.wav'),extract(a.out),'seconds')

if __name__=='__main__':main()
