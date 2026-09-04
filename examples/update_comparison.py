"""Replace matching codec entries in a comparison without re-encoding other clips."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tsaudio.comparison import build_comparison
from tsaudio.storage import decode

def read_entries(folder):
    manifest=json.loads((folder/'manifest.json').read_text())
    rom=(folder/'picorom.bin').read_bytes()
    flags=manifest.get('record_compression',[0]*len(manifest['records']))
    result=[]
    for entry,segments,flag in zip(manifest['entries'],manifest['records'],flags):
        raw=b''.join(rom[address:address+count] for _,address,count in segments)
        data=decode(raw) if flag else raw
        if len(data)!=entry['bytes']:raise ValueError('Manifest/stream length mismatch')
        result.append(dict(entry,data=data))
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base',type=Path,required=True)
    p.add_argument('--replacement',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--pasmo',required=True)
    p.add_argument('--replace-sample', action='append', default=[], metavar='NAME',
                   help='Allow a changed source WAV only when replacing every codec for this sample')
    a=p.parse_args()
    entries=read_entries(a.base)
    replacements={(e['name'],e['codec']):e for e in read_entries(a.replacement)}
    keys={(e['name'],e['codec']) for e in entries}
    if replacements.keys()-keys:p.error('Replacement contains entries absent from base')
    for name in a.replace_sample:
        sample_keys={key for key in keys if key[0]==name}
        if not sample_keys or not sample_keys<=replacements.keys():
            p.error('--replace-sample requires all existing codecs for the named sample')
        if len({replacements[key]['sha256'] for key in sample_keys})!=1:
            p.error('Replacement codecs must share one source WAV')
    for index,entry in enumerate(entries):
        key=entry['name'],entry['codec']
        if key in replacements:
            if replacements[key]['sha256']!=entry['sha256'] and entry['name'] not in a.replace_sample:
                p.error('Replacement must use the same source WAV; rebuild the full sample when changing sources')
            entries[index]=replacements[key]
    result=build_comparison(entries,a.out,a.pasmo)
    print(f"Updated {len(replacements)} entries; {len(entries)} total; {result['payload_bytes']} ROM payload bytes")

if __name__=='__main__':main()
