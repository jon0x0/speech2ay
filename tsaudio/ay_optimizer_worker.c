/* Stateful candidate renderer using external Ayumi (its license is unchanged).
 * Binary little-endian protocol: int32 op,n,count. op0 renders count R0..13
 * candidates from the SAME anchor, returning float32[count][n]; op1 commits
 * candidate index n from last evaluation; op2 resets; op3 exits.
 * R13=255 means don't write the envelope shape (no restart).
 */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <math.h>
#include "ayumi.h"
typedef struct { struct ayumi ay; double xp,lp; } State;
static State anchor, candidates[512];
static double clock_hz,cutoff,gain_ratio;
static void init_state(void) {
  anchor=(State){0};
  ayumi_configure(&anchor.ay,0,clock_hz,44100);
  for(int c=0;c<3;c++) ayumi_set_pan(&anchor.ay,c,.5,0);
}
int main(int argc,char **argv) {
  if(argc!=4) return 2;
  clock_hz=atof(argv[1]);cutoff=atof(argv[2]);gain_ratio=atof(argv[3]);
  if(cutoff<=0 || gain_ratio<1) return 3;
  /* Normalized noninverting feedback shelf: H=(1+sRC/gain)/(1+sRC).
     Bilinear one-pole LP; no guessed speaker resonance or diode model. */
  double k=44100/(3.141592653589793*cutoff), b=1/(1+k), a=(k-1)/(k+1);
  init_state();
  int32_t op,n,count,last_count=0;
  while(fread(&op,4,1,stdin)==1 && fread(&n,4,1,stdin)==1 && fread(&count,4,1,stdin)==1) {
    if(op==3) return 0;
    if(op==2) {init_state();last_count=0;continue;}
    if(op==1) {if(n<0 || n>=last_count)return 4;anchor=candidates[n];continue;}
    if(op!=0 || n<1 || n>4096 || count<1 || count>512)return 5;
    int32_t regs[512][14];
    if(fread(regs,4,count*14,stdin)!=(size_t)(count*14))return 6;
    float *output=malloc((size_t)count*n*sizeof(float));if(!output)return 7;
    for(int j=0;j<count;j++) {
      State *s=&candidates[j];*s=anchor;
      int32_t *r=regs[j];
      ayumi_set_noise(&s->ay,r[6]);
      for(int c=0;c<3;c++) {
        ayumi_set_tone(&s->ay,c,r[c*2]|(r[c*2+1]<<8));
        ayumi_set_volume(&s->ay,c,r[8+c]&15);
        ayumi_set_mixer(&s->ay,c,(r[7]>>c)&1,(r[7]>>(c+3))&1,(r[8+c]>>4)&1);
      }
      ayumi_set_envelope(&s->ay,r[11]|(r[12]<<8));
      if(r[13]!=255)ayumi_set_envelope_shape(&s->ay,r[13]);
      for(int i=0;i<n;i++) {
        ayumi_process(&s->ay);
        double x=s->ay.left;
        s->lp=b*(x+s->xp)+a*s->lp;s->xp=x;
        output[j*n+i]=(float)(x/gain_ratio+(1-1/gain_ratio)*s->lp);
      }
    }
    last_count=count;
    if(fwrite(output,sizeof(float),(size_t)count*n,stdout)!=(size_t)count*n)return 8;
    fflush(stdout);free(output);
  }
  return 0;
}
