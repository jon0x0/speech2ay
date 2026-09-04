"""Confirm real TS2068 ROM autoload reaches the demo menu for TAP and DCK."""
import argparse,json
from pathlib import Path
from run_fuse_debug import run_fuse
def main():
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--fuse',required=True,type=Path);a=p.parse_args()
    for fmt in ['tap','dck']:
        folder=a.root/f'volume-01-{fmt}';m=json.loads((folder/'manifest.json').read_text());pc=m['demo_symbols']['menu']
        command=f'breakpoint {pc}\ncommands 1\nprint z80:pc\nexit 0\nend'
        r=run_fuse(machine='ts2068',media=(folder/f'demo.{fmt}').resolve(),fuse=a.fuse,tape=fmt=='tap',debugger_command=command,timeout=30)
        (folder/'boot.log').write_text(r.stdout+r.stderr)
        assert f'0x{pc:x}' in r.stdout and 'Invalid debugger' not in r.stderr,(fmt,r.stdout,r.stderr)
        print(fmt+' ROM autoload/menu reached')
if __name__=='__main__':main()
