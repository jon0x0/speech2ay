"""Stage a portable skill and ZIP, excluding local recordings and build scratch."""
import argparse,hashlib,json,shutil,zipfile
from pathlib import Path
def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,default=Path('build/skill-package'));a=p.parse_args()
    root=Path(__file__).resolve().parent;dest=a.out.resolve()/'ts2068-audio-development'
    if dest.exists():raise SystemExit('Output exists; select a fresh staging directory')
    dest.mkdir(parents=True)
    shutil.copy2(root/'skill/SKILL.md',dest/'SKILL.md')
    toolkit=dest/'assets/audio-tools'
    shutil.copytree(root,toolkit,ignore=shutil.ignore_patterns('.git','build','dist','web','node_modules','skill','__pycache__','*.pyc','*.egg-info','package_skill.py'))
    # Only generated synthetic audio belongs in the portable examples.
    examples=toolkit/'examples';examples.mkdir(exist_ok=True)
    for path,name in [(root/'build/exports/dck/demo.dck','synthetic.dck'),
                      (root/'build/exports/dck/picorom.bin','synthetic-picorom.bin'),
                      (root/'build/exports/tap/demo.tap','synthetic.tap')]:
        if path.exists():shutil.copy2(path,examples/name)
    (examples/'README.md').write_text('Generated six-codec test tone demo. Q/A select; Space plays.\nRebuild with tests/verify_exports.py --pasmo PATH. No game recordings included.\n')
    hashes={str(f.relative_to(dest)).replace('\\','/'):hashlib.sha256(f.read_bytes()).hexdigest() for f in dest.rglob('*') if f.is_file()}
    (dest/'SHA256SUMS.json').write_text(json.dumps(hashes,indent=2))
    archive=dest.with_suffix('.zip')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for f in dest.rglob('*'):
            if f.is_file():z.write(f,f.relative_to(dest.parent))
    with zipfile.ZipFile(archive) as z:assert z.testzip() is None
    print(dest);print(archive)
if __name__=='__main__':main()
