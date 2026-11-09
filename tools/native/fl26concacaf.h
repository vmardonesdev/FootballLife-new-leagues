/* Versioned CONCACAF contract and pure qualification/handover checks.
 * No game pointers: the DLL adapter supplies completed rankings and actual winners. */
#ifndef FL26CONCACAF_H
#define FL26CONCACAF_H
#include <stdint.h>
#include <string.h>
#define CQ_VERSION 1
#define CQ_SOURCES 64
#define CQ_RANKS 40
#define CQ_PLACES 27
#define CQ_PREF 8
typedef struct { uint16_t reg, kind, region, capacity, n; int status;
                 uint32_t club[CQ_RANKS]; } cq_source;
typedef struct { uint16_t direct, np, nf, local, source[CQ_PREF], rank[CQ_PREF], fallback[CQ_SOURCES]; } cq_place;
typedef struct { uint16_t ko, pre, fill, days[2], ns;
                 cq_source source[CQ_SOURCES]; cq_place place[CQ_PLACES]; } cq_config;
static int cq_has(const uint32_t* a, int n, uint32_t c)
{
  for (int i = 0; i < n; i++) if ((a[i] >> 14) == (c >> 14)) return 1;
  return 0;
}
static int cq_unique(const uint32_t* a, int n)
{
  for (int i = 0; i < n; i++) if (!(a[i] >> 14) || cq_has(a, i, a[i])) return 0;
  return 1;
}
static int cq_snapshot_valid(const uint32_t* clubs, int n, int saved_day, int today_day)
{
  return n==27 && saved_day<=today_day && (saved_day+183)/365==(today_day+183)/365 && cq_unique(clubs,27);
}
static int cq_first_edition(int built, int today)
{
  return built>=0 && today>=built && (built+183)/365==(today+183)/365;
}
/* Match ownership varies between master and replica across engine versions.
 * Count by the actual tie's two clubs, once per live match record. */
static int cq_count_match(const uint32_t* clubs, uint32_t a, uint32_t b, int played,
                           int* scheduled, int* unplayed)
{
  for (int i=0;i<11;i++) if (cq_has(clubs+2*i,2,a) && cq_has(clubs+2*i,2,b)
                            && (a>>14)!=(b>>14)) {
    scheduled[i]++; unplayed[i]+=!played; return 1;
  }
  return 0;
}
/* Promotion/relegation: retain the completed eligible order, then append new
 * members in domestic entry order. Never qualify a departed/deleted club. */
static int cq_current_ranking(uint32_t* ranked, int n, const uint32_t* current, int nc)
{
  if (n<1 || n>CQ_RANKS || nc<1 || nc>CQ_RANKS || !cq_unique(ranked,n) || !cq_unique(current,nc)) return 0;
  uint32_t out[CQ_RANKS]; int count=0;
  for (int i=0;i<n;i++) if (cq_has(current,nc,ranked[i])) out[count++]=ranked[i];
  for (int i=0;i<nc;i++) if (!cq_has(out,count,current[i])) out[count++]=current[i];
  memcpy(ranked,out,(size_t)count*sizeof(uint32_t)); return count;
}
/* Packed u16: version, ko, pre, fill, d1, d2, ns; source records
 * (reg, kind 0 league/1 cup, region 0 north/1 central/2 Caribbean, capacity);
 * 27 place records (direct,np,nf,local, [zero-based source,rank]*np, [source]*nf). */
static int cq_parse(cq_config* c, const uint16_t* v, int n)
{
  if (!c || !v || n < 7 || v[0] != CQ_VERSION) return 0;
  memset(c, 0, sizeof *c);
  c->ko=v[1]; c->pre=v[2]; c->fill=v[3]; c->days[0]=v[4]; c->days[1]=v[5]; c->ns=v[6];
  if (c->ko < 176 || c->ko > 1023 || c->pre < 176 || c->pre > 1023 || c->ko == c->pre
      || c->fill < 1 || c->fill > 365 || c->days[0] < 1 || c->days[1] > 181
      || c->days[0] >= c->days[1] || !c->ns || c->ns > CQ_SOURCES) return 0;
  int p=7, direct=0;
  for (int i=0; i<c->ns; i++) {
    if (n-p < 4) return 0;
    cq_source* s=&c->source[i]; s->reg=v[p++]; s->kind=v[p++]; s->region=v[p++]; s->capacity=v[p++];
    if (!s->reg || s->reg>1023 || s->reg==c->ko || s->reg==c->pre || s->kind>1 || s->region>2
        || s->capacity>CQ_RANKS || (!s->kind && !s->capacity)) return 0;
    for (int j=0; j<i; j++) if (c->source[j].reg==s->reg) return 0;
  }
  for (int i=0; i<CQ_PLACES; i++) {
    if (n-p < 4) return 0;
    cq_place* s=&c->place[i]; s->direct=v[p++]; s->np=v[p++]; s->nf=v[p++]; s->local=v[p++];
    if (s->direct>1 || s->np>CQ_PREF || !s->nf || s->nf>CQ_SOURCES || s->local>s->nf || n-p < 2*s->np+s->nf) return 0;
    direct+=s->direct;
    for (int j=0; j<s->np; j++) {
      s->source[j]=v[p++]; s->rank[j]=v[p++];
      if (s->source[j]>=c->ns || !s->rank[j] || s->rank[j]>CQ_RANKS) return 0;
    }
    for (int j=0; j<s->nf; j++) {
      s->fallback[j]=v[p++];
      if (s->fallback[j]>=c->ns || c->source[s->fallback[j]].kind) return 0;
    }
  }
  return p==n && direct==5;
}
/* out: five byes first, then 22 Round One entrants. 0 invalid/missing,
 * -1 pending, 1 exact field. No partial output may be installed by the adapter. */
static int cq_resolve(const cq_config* c, uint32_t* out)
{
  int n=0;
  for (int pass=1; pass>=0; pass--) for (int i=0; i<CQ_PLACES; i++) {
    const cq_place* p=&c->place[i]; if (p->direct!=pass) continue;
    uint32_t chosen=0;
    for (int j=0; j<p->np && !chosen; j++) {
      const cq_source* s=&c->source[p->source[j]];
      if (s->status!=1) return s->status==2 ? -1 : 0;
      for (int r=p->rank[j]-1; r<s->n; r++) if (!cq_has(out,n,s->club[r])) { chosen=s->club[r]; break; }
    }
    if (!chosen) {
      /* The Python list puts same-region sources first. Finish that region's
       * ranks before crossing a boundary, matching the reference resolver. */
      int first=0;
      for (int tier=0;tier<2 && !chosen;tier++) {
        int end=tier ? p->nf : p->local;
        for (int j=first;j<end;j++) {
          int status=c->source[p->fallback[j]].status;
          if (status!=1) return status==2 ? -1 : 0;
        }
        for (int r=0;r<CQ_RANKS && !chosen;r++) for (int j=first;j<end;j++) {
          const cq_source* s=&c->source[p->fallback[j]];
          if (r<s->n && !cq_has(out,n,s->club[r])) { chosen=s->club[r]; break; }
        }
        first=end;
      }
    }
    if (!(chosen>>14)) return 0;
    out[n++]=chosen;
  }
  return n==27 && cq_unique(out,27);
}
/* Strict per-tie proof: exactly two scheduled matches, both played, a real
 * winner belonging to that tie. No aggregate/first-leg/seeded guess. */
static int cq_handover(const uint32_t* direct, const uint32_t* clubs,
                       const int* scheduled, const int* unplayed, const uint32_t* winners,
                       uint32_t* out)
{
  if (!cq_unique(direct,5) || !cq_unique(clubs,22)) return 0;
  for (int i=0;i<5;i++) if (cq_has(clubs,22,direct[i])) return 0;
  for (int i=0;i<11;i++) {
    if (scheduled[i]!=2 || unplayed[i]!=0 || !(winners[i]>>14)
        || !cq_has(clubs+2*i,2,winners[i])) return 0;
  }
  /* Five bye/winner ties, then three winner/winner ties. */
  for (int i=0;i<5;i++) { out[2*i]=winners[i]; out[2*i+1]=direct[i]; }
  for (int i=5;i<11;i++) out[i+5]=winners[i];
  return cq_unique(out,16);
}
#endif
