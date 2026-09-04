import argparse, hashlib, json, os, shutil
from pathlib import Path
from .codecs import CODECS, encode
from .build import build

def main(tool):
    p=argparse.ArgumentParser(description={'audio2aydac':'Packed digitized audio for TS2068 AY DAC','speech2ay':'Harmonic AY synthesis for speech and effects','ayfit':'Stateful waveform/spectrum AY optimizer','aydemo':'Interactive TS2068 multi-codec listening demo'}[tool])
    p.add_argument('inputs',nargs='+',type=Path,help='PCM WAV files or directories')
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--format',nargs='+',choices=['bin','tap','dck'],default=['dck'] if tool=='aydemo' else ['bin'])
    p.add_argument('--origin',type=lambda s:int(s,0),default=0x8000)
    p.add_argument('--separate-data',action='store_true')
    p.add_argument('--data-origin',type=lambda s:int(s,0),default=0xd000)
    p.add_argument('--pasmo',default=os.environ.get('PASMO',shutil.which('pasmo')),help='Pasmo executable; Windows also accepts a WSL executable path')
    p.add_argument('--audio2ay',type=Path,help='Optional upstream executable; add its results to aydemo')
    p.add_argument('--profile',choices=['filtered','berzerk'],default='filtered',help='AY conversion profile; berzerk reproduces the original game effect pipeline')
    p.add_argument('--sample-profile',action='append',default=[],metavar='NAME=PROFILE',help='Override the AY profile for one input filename stem; repeat as needed')
    if tool=='aydemo':p.add_argument('--spectra',action='store_true',help='Add offline original/modeled FFT view (requires --ayumi and GCC)')
    p.add_argument('--low',type=float,default=80)
    p.add_argument('--high',type=float)
    if tool in ('speech2ay','ayfit'):p.add_argument('--channels',type=int,choices=[1,2,3],default=3)
    else:p.add_argument('--codecs',nargs='+',choices=CODECS[:3] if tool=='audio2aydac' else CODECS,default=list(CODECS[:3]) if tool=='audio2aydac' else list(CODECS))
    if tool in ('ayfit','aydemo'):
        p.add_argument('--ayumi',required=tool=='ayfit')
        if tool=='aydemo':p.add_argument('--optimize',type=int,nargs='+',choices=[1,2,3],default=[],help='Add optimized AY channel counts for every sample')
        p.add_argument('--gcc',default='gcc')
        p.add_argument('--passes',type=int,choices=range(1,5))
        p.add_argument('--objective',choices=['joint','spectrum'],default='joint')
        p.add_argument('--feedback-cutoff',type=float)
        p.add_argument('--feedback-gain',type=float,default=7.8)
    args=p.parse_args()
    original=vars(args).copy();overrides={}
    for item in args.sample_profile:
        name,separator,profile=item.rpartition('=')
        if not separator or not name or profile not in ('filtered','berzerk'):p.error('--sample-profile requires NAME=filtered or NAME=berzerk')
        overrides[name]=profile
    def configured(profile):
        result=argparse.Namespace(**original);result.profile=profile
        if result.high is None:result.high=7000 if tool=='ayfit' or profile=='berzerk' else 6500
        if tool in ('ayfit','aydemo'):
            if result.passes is None:result.passes=2 if profile=='berzerk' else 3
            if result.feedback_cutoff is None:result.feedback_cutoff=1/(2*3.141592653589793*680000*20e-12) if profile=='berzerk' else 11702.57
        return result
    args=configured(args.profile)
    if tool in ('ayfit','aydemo') and (args.feedback_cutoff<=0 or args.feedback_gain<1):
        p.error('Feedback cutoff must be positive and feedback gain at least 1')
    if tool=='aydemo' and args.optimize and not args.ayumi:p.error('--optimize requires --ayumi')
    if tool=='aydemo' and args.spectra and not args.ayumi:p.error('--spectra requires --ayumi')
    if tool=='aydemo' and args.spectra and 'dck' not in args.format:p.error('--spectra requires DCK output')
    if not args.pasmo:p.error('Set PASMO or supply --pasmo')
    if args.separate_data and args.format!=['bin']:p.error('--separate-data requires --format bin')
    paths=[]
    for item in args.inputs:
        paths.extend(sorted((q for q in item.iterdir() if q.suffix.lower()=='.wav'),key=lambda q:q.name.lower()) if item.is_dir() else [item])
    if not paths:p.error('No WAV files found')
    if set(overrides)-{path.stem for path in paths}:p.error('A --sample-profile name does not match any input filename stem')
    args.out.mkdir(parents=True,exist_ok=True)
    codecs=[f'harmonic{args.channels}'] if tool in ('speech2ay','ayfit') else args.codecs
    if tool=='aydemo':codecs=list(codecs)+[f'optimized{c}' for c in args.optimize]
    entries=[]
    if args.audio2ay and tool=="aydemo":codecs=list(codecs)+["audio2ay"]
    try:
        for path in paths:
            for codec in codecs:
                args=configured(overrides.get(path.stem,original['profile']) if codec.startswith(('harmonic','optimized')) else 'filtered')
                settings={k:getattr(args,k,None) for k in ['low','high','passes','objective','feedback_cutoff','feedback_gain','audio2ay','profile']}
                dependency_hash=hashlib.sha256(b''.join(Path(__file__).with_name(n).read_bytes() for n in ['codecs.py','harmonic.py','bands.py','optimizer.py','search.py','audio2ay.py'])).hexdigest()
                key=hashlib.sha256(path.read_bytes()+codec.encode()+json.dumps(settings,default=str,sort_keys=True).encode()+dependency_hash.encode()).hexdigest()
                cache=args.out.resolve()/'encoded'/key;cache.mkdir(parents=True,exist_ok=True)
                if (cache/'result.json').exists() and (cache/'audio.bin').exists():
                    saved=json.loads((cache/'result.json').read_text());raw=(cache/'audio.bin').read_bytes();count=saved['count'];info=saved['info']
                else:
                    print(f'Encoding {path.stem}: {codec}',flush=True)
                    if codec=='audio2ay':
                        from .audio2ay import convert
                        raw,count,info=convert(path,args.audio2ay.resolve(),cache)
                    elif tool=='ayfit' or codec.startswith('optimized'):
                        from .optimizer import optimize
                        raw,count,info=optimize(path,int(codec[-1]),args,cache)
                    else:raw,count,info=encode(path,codec,args.low,args.high,args.profile)
                    (cache/'audio.bin').write_bytes(raw)
                    (cache/'result.json').write_text(json.dumps({'count':count,'info':info}))
                if not 1<=count<=65535:raise ValueError('Clip group/frame count exceeds16-bit API')
                entries.append({'name':path.stem,'codec':codec,'data':raw,'count':count,'bytes':len(raw),
                                'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),**info})
        if tool=='aydemo' and 'dck' in args.format:
            if args.spectra:
                from .spectrum import attach
                entries=attach(entries,{path.stem:path for path in paths},args.out/'spectra',args.ayumi,args.gcc)
            from .comparison import build_comparison
            destination=args.out/'cartridge' if len(args.format)>1 else args.out
            result=build_comparison(entries,destination,args.pasmo)
            print(f"Built one64K comparison cartridge: {len(entries)} choices, {result['payload_bytes']} payload bytes",flush=True)
            args.format=[f for f in args.format if f!='dck']
            if not args.format:return
        # Demo volumes keep every requested selection and respect fixed cartridge capacity.
        volumes=[];current=[];size=0
        for e in entries:
            if current and (size+e['bytes']>8500 or len(current)==16) and not args.separate_data:
                volumes.append(current);current=[];size=0
            current.append(e);size+=e['bytes']
        if current:volumes.append(current)
        index=[]
        for i,volume in enumerate(volumes):
            for fmt in args.format:
                out=args.out/(f'volume-{i+1:02}-{fmt}') if len(volumes)>1 or len(args.format)>1 else args.out
                manifest=build(volume,out,[fmt],args.origin,args.pasmo,args.separate_data,args.data_origin)
                index.append({'directory':str(out),'format':fmt,'entries':[e['name']+' '+e['codec'] for e in volume]})
        (args.out/'index.json').write_text(json.dumps(index,indent=2))
        print(f'Built {len(entries)} selections in {len(volumes)} volume(s): {args.out.resolve()}')
    except (ValueError,OSError) as e:p.error(str(e))
