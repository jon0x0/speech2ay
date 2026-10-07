import {render} from './synth.mjs';
self.onmessage=({data})=>{try{const t=performance.now(),samples=render(data.rows);self.postMessage({id:data.id,samples,ms:performance.now()-t},[samples.buffer]);}catch(e){self.postMessage({id:data.id,error:e.message});}};
