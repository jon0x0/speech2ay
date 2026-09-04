from pathlib import Path
import sys
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
from tsaudio.assembly import runtime
(root/'asm/audio_runtime.asm').write_text(runtime(),encoding='utf-8')
