#include <assert.h>
#include <stdio.h>
#include "fl26concacaf.h"
#define CLUB(n) ((uint32_t)(n)<<14)
int main(int argc, char** argv)
{
  uint32_t direct[5], clubs[22], win[11], out[27]; int matches[11], left[11];
  for (int i=0;i<5;i++) direct[i]=CLUB(i+1);
  for (int i=0;i<22;i++) clubs[i]=CLUB(i+6);
  for (int i=0;i<11;i++) { win[i]=clubs[2*i+1]; matches[i]=2; left[i]=0; }
  assert(cq_handover(direct,clubs,matches,left,win,out));
  int counted[11]={0}, pending[11]={0};
  for (int i=0;i<11;i++) {
    assert(cq_count_match(clubs,clubs[2*i],clubs[2*i+1],1,counted,pending));
    assert(cq_count_match(clubs,clubs[2*i+1],clubs[2*i],0,counted,pending));
    assert(counted[i]==2 && pending[i]==1);
  }
  assert(!cq_handover(direct,clubs,counted,pending,win,out));
  assert(!cq_count_match(clubs,CLUB(100),CLUB(101),1,counted,pending));
  for (int i=0;i<11;i++) {
    left[i]=1; assert(!cq_handover(direct,clubs,matches,left,win,out)); left[i]=0;
    matches[i]=1; assert(!cq_handover(direct,clubs,matches,left,win,out)); matches[i]=2;
    uint32_t w=win[i]; win[i]=0; assert(!cq_handover(direct,clubs,matches,left,win,out));
    win[i]=CLUB(100); assert(!cq_handover(direct,clubs,matches,left,win,out)); win[i]=w;
  }
  direct[0]=clubs[0]; assert(!cq_handover(direct,clubs,matches,left,win,out)); direct[0]=CLUB(1);
  for (int i=0;i<27;i++) out[i]=CLUB(i+1);
  assert(cq_snapshot_valid(out,27,243,405));
  assert(!cq_snapshot_valid(out,27,243,548)); /* July rollover */
  assert(!cq_snapshot_valid(out,27,243,240)); /* older save */
  assert(!cq_snapshot_valid(out,26,243,405));
  assert(cq_first_edition(0,33));
  assert(!cq_first_edition(0,243)); /* January career's September is its second edition. */
  assert(cq_first_edition(216,405));
  assert(!cq_first_edition(216,608));
  uint32_t old[40]={CLUB(3),CLUB(1),CLUB(2),CLUB(4)};
  uint32_t current[4]={CLUB(1),CLUB(3),CLUB(5),CLUB(6)};
  assert(cq_current_ranking(old,4,current,4)==4);
  assert(old[0]==CLUB(3) && old[1]==CLUB(1) && old[2]==CLUB(5) && old[3]==CLUB(6));
  if (argc>1) {
    uint16_t words[8192]; FILE* f=fopen(argv[1],"rb"); assert(f);
    int n=(int)fread(words,sizeof(uint16_t),8192,f); fclose(f);
    static cq_config c, scratch;
    assert(cq_parse(&c,words,n));
    for (int i=0;i<n;i++) assert(!cq_parse(&scratch,words,i));
    words[0]=2; assert(!cq_parse(&scratch,words,n)); words[0]=1;
    unsigned club=1;
    for (int i=0;i<c.ns;i++) {
      cq_source* s=&c.source[i]; s->status=1;
      if (s->kind) { s->n=1; s->club[0]=CLUB(1); }
      else { s->n=s->capacity; for (int j=0;j<s->n;j++) s->club[j]=CLUB(club++); }
    }
    assert(cq_resolve(&c,out)==1); assert(cq_unique(out,27));
    for (int i=0;i<c.ns;i++) {
      int old=c.source[i].status; c.source[i].status=2;
      /* A missing used source can only wait/fail, never create a guessed field. */
      int r=cq_resolve(&c,out); assert(r==1 || r==-1); c.source[i].status=old;
    }
    for (int i=0;i<c.ns;i++) { c.source[i].n=1; c.source[i].club[0]=CLUB(1); }
    assert(cq_resolve(&c,out)==0);
  }
  puts("CONCACAF: strict 11-tie handover, uniqueness, season reset, contract bounds and qualification passed");
  return 0;
}
