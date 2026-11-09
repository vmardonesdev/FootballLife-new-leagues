/* Actual shared scheduler with a CONCACAF fallback league, without game pointers. */
#define FL26_RCAL_TEST
#include "fl26swiss.c"
#include <assert.h>
int rcal_test_today(void) { return 0; }
int rcal_test_invites(int k, uint16_t id) { (void)k; (void)id; return 0; }
int rcal_test_recday(uint16_t id) { (void)id; return -1; }
int main(void)
{
  g_test_year=2026;
  g_cq_enabled=1; g_cq.ko=500; g_cq.pre=501;
  g_cq.days[0]=33; g_cq.days[1]=40; g_cq.ns=2;
  g_cq.source[0].reg=300; g_cq.source[1].reg=301;
  g_nccup=2; memset(g_ccup,0,sizeof g_ccup);
  g_ccup[0].reg=g_ccup[0].ko=500;
  const uint16_t days[7]={61,68,89,96,117,124,145};
  memcpy(g_ccup[0].days,days,sizeof days); g_ccup[0].nd=7;
  g_ccup[0].n=16; g_ccup[0].ereg[0]=300; g_ccup[0].erank[0]=1;
  g_ccup[1].reg=g_ccup[1].ko=510;
  assert(ccup_feeds(0,300)); assert(ccup_feeds(0,301)); /* fallback source also protected */
  assert(!ccup_feeds(0,302)); assert(!ccup_feeds(1,301));
  busy_t busy[BUSY_MAX]; int n=busy_set(301,busy), found=0;
  uint32_t reserved[9]={33,40,61,68,89,96,117,124,145};
  for (int i=0;i<n;i++) if (busy[i].kind==BZ_CONT) {
    for (int j=0;j<9;j++) if (busy[i].day==reserved[j]) found++;
  }
  assert(found==9);
  uint16_t recipe[8]={301,51,339,0,0,96,16,0};
  assert(fl26_swiss_rcal(recipe,1)==1);
  date_t rounds[30]; memset(rounds,0,sizeof rounds);
  assert(rcal_dates(301,rcal_of(301),rounds,30,1)>=0);
  for (int i=0;i<30;i++) for (int j=0;j<9;j++) {
    int gap=abs((int)rounds[i].day-(int)reserved[j]); if (gap>182) gap=365-gap;
    assert(gap>=3);
  }
  /* The actual adapter must fail closed if hooks are absent: neither legacy
   * filler may touch game pointers after the rejected modern contract. */
  uint16_t v[200]={1,500,501,243,33,40,1,300,0,0,28}; int words=11;
  for (int i=0;i<27;i++) {
    v[words++]=(uint16_t)(i<5); v[words++]=0; v[words++]=1; v[words++]=1; v[words++]=0;
  }
  assert(fl26_swiss_concacaf(v,words)==-3);
  assert(g_cq_blocked && !g_cq_enabled);
  g_lpre[0].reg=501;
  lpre_fill(0);
  assert(ccup_fill_one(0,0)==0);
  puts("CONCACAF: both qualification leagues reserve all nine dates; 30 domestic rounds stay at least three days clear; unrelated cup unchanged");
  return 0;
}
