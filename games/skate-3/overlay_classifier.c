/* Original patch code; no game assets/code. The caller supplies the renderer's
 * immutable per-frame draw snapshot, never the concurrently published vector.
 * Return 0: proportional; 1: full canvas; 2: proportional cover;
 * 3/4: proportional top/bottom anchor; 5: enlarged startup dialog.
 */
typedef struct { float l,t,r,b; unsigned rect; } Bounds;
static float dot4(const float *a, const float *b) {
    return a[0]*b[0]+a[1]*b[1]+a[2]*b[2]+a[3]*b[3];
}
static int near(float a,float b) { return a>=b-2 && a<=b+2; }
static int bounds(const unsigned char *d, Bounds *b) {
    unsigned count=*(const unsigned *)(d+4);
    const float *m=(const float *)(d+0x60);
    const unsigned char *begin=*(const unsigned char *const *)(d+0xf0);
    const unsigned char *end=*(const unsigned char *const *)(d+0xf8);
    if (!count || count>1024 || !begin || end<begin || (unsigned long)(end-begin)<count*28ul ||
        m[12]!=0 || m[13]!=0 || m[14]!=0 || m[15]!=1) return 0;
    b->l=16384; b->t=16384; b->r=-16384; b->b=-16384;
    for (unsigned i=0;i<count;i++) {
        const float *p=(const float *)(begin+i*28);
        float w[4]={dot4(p,m+16),dot4(p,m+20),dot4(p,m+24),dot4(p,m+28)};
        float x=dot4(w,m),y=dot4(w,m+4);
        if (!(x>=-16 && x<=16 && y>=-16 && y<=16)) return 0;
        x=(x+1)*640; y=(1-y)*360;
        if (x<b->l) b->l=x;
        if (x>b->r) b->r=x;
        if (y<b->t) b->t=y;
        if (y>b->b) b->b=y;
    }
    b->rect=0;
    if (count==4 || count==6) {
        unsigned corners=0;
        for(unsigned i=0;i<count;i++) {
            const float *p=(const float *)(begin+i*28);
            float w[4]={dot4(p,m+16),dot4(p,m+20),dot4(p,m+24),dot4(p,m+28)};
            float x=(dot4(w,m)+1)*640,y=(1-dot4(w,m+4))*360;
            int l=near(x,b->l),r=near(x,b->r),t=near(y,b->t),bot=near(y,b->b);
            if (!(l||r) || !(t||bot)) return 1;
            corners|=1u<<((r?1:0)+(bot?2:0));
        }
        b->rect=corners==15;
    }
    return b->r>b->l && b->b>b->t;
}
static unsigned frame_count(const unsigned char *begin,const unsigned char *end) {
    if (!begin || end<begin || (unsigned long)(end-begin)%264) return 0;
    unsigned long n=(unsigned long)(end-begin)/264;
    return n<=512 ? (unsigned)n : 0;
}
static int full(const Bounds *b) {
    /* Modal dimmers deliberately overscan the authored viewport by a few
     * pixels. Accept that margin, but never promote a partial panel. */
    return b->rect && b->l>=-32 && b->l<=2 && b->t>=-32 && b->t<=2 &&
           b->r>=1278 && b->r<=1312 && b->b>=718 && b->b<=752;
}
/* A repeating grain/dim layer is one screen-sized effect even when APT emits
 * dozens of small tiles. Require matching texture/color, rectangular tiles,
 * complete canvas coverage and no overlap beyond the padded bottom row. */
static int tiled_canvas(const unsigned char *d,const unsigned char *begin,unsigned n) {
    unsigned texture=*(const unsigned *)(d+0x1c), tiles=0;
    float area=0; Bounds all={16384,16384,-16384,-16384,0};
    const float *color=(const float *)(d+0xe0);
    for(unsigned i=0;i<n;i++) {
        const unsigned char *p=begin+i*264;
        const float *c=(const float *)(p+0xe0);
        if (*(const unsigned *)(p+12)!=24 || *(const unsigned *)(p+0x1c)!=texture ||
            c[0]!=color[0] || c[1]!=color[1] || c[2]!=color[2] || c[3]!=color[3]) continue;
        Bounds b;
        if (!bounds(p,&b) || !b.rect || b.l < -2 || b.t < -2 || b.r>1282 || b.b>770) return 0;
        float bottom=b.b>720 ? 720 : b.b;
        if (bottom>b.t) area+=(b.r-b.l)*(bottom-b.t);
        if(b.l<all.l)all.l=b.l;
        if(b.r>all.r)all.r=b.r;
        if(b.t<all.t)all.t=b.t;
        if(b.b>all.b)all.b=b.b;
        tiles++;
    }
    return tiles>=4 && near(all.l,0) && near(all.r,1280) && near(all.t,0) && all.b>=718 &&
           area>=1280*720*.99f && area<=1280*720*1.01f;
}
/* The optional outpaint pack is BC1; the stock opaque title tiles are BC3.
 * Require the complete four-tile arrangement before changing other artwork. */
static int stock_title(const unsigned char *begin,unsigned n) {
    unsigned seen=0;
    for(unsigned i=0;i<n;i++) {
        const unsigned char *d=begin+i*264;
        if (*(const unsigned *)(d+12)!=24 || (*(const unsigned *)(d+28)&63)!=20) continue;
        unsigned dim=*(const unsigned *)(d+32),tw=(dim&8191)+1,th=((dim>>13)&8191)+1;
        Bounds b;
        if(!bounds(d,&b) || !b.rect)continue;
        int col=(near(b.l,0)&&near(b.r,1024)&&tw==1024) ? 0 :
                (near(b.l,1024)&&near(b.r,1280)&&tw==256) ? 1 : -1;
        int row=(near(b.t,0)&&near(b.b,512)&&th==512) ? 0 :
                (near(b.t,512)&&near(b.b,768)&&th==256) ? 1 : -1;
        if(col>=0 && row>=0)seen|=1u<<(row*2+col);
    }
    return seen==15;
}
static int hud_piece(const unsigned char *d,Bounds *b) {
    return (*(const unsigned *)(d+20)&8) && bounds(d,b) &&
           b->l>=-64 && b->r<=1344 && b->t>=-64 && b->b<=784 &&
           b->r-b->l<1100 && b->b-b->t<720;
}
/* Move connected artwork, glow, panel, and text batches as a unit. A portrait
 * split over texture tiles must never have its head/body anchored separately.
 * Full-screen fades are excluded. Bound work and fail to centered placement
 * if a malformed or excessively connected frame cannot converge. */
static int hud_anchor(const unsigned char *d,Bounds group,const unsigned char *begin,unsigned n) {
    Bounds pieces[512];
    unsigned used=0;
    for(unsigned i=0;i<n;i++) {
        Bounds b;
        if(hud_piece(begin+i*264,&b)) pieces[used++]=b;
    }
    for(unsigned pass=0;pass<32;pass++) {
        int changed=0;
        for(unsigned i=0;i<used;i++) {
            Bounds b=pieces[i];
            if (b.r+12<group.l || b.l-12>group.r || b.b+12<group.t || b.t-12>group.b) continue;
            if(b.l<group.l){group.l=b.l;changed=1;}
            if(b.r>group.r){group.r=b.r;changed=1;}
            if(b.t<group.t){group.t=b.t;changed=1;}
            if(b.b>group.b){group.b=b.b;changed=1;}
        }
        if(!changed) {
            float center=(group.t+group.b)*.5f;
            return center<288 ? 3 : center>432 ? 4 : 0;
        }
    }
    return 0;
}
int full_canvas_overlay(const unsigned char *draw,unsigned movie_state,
                        unsigned screen,unsigned warmup,unsigned in_menu,unsigned video,
                        const unsigned char *scene_begin,const unsigned char *scene_end) {
    int title=(movie_state&255)==1 && screen==0xffffffffu && warmup;
    /* Only the first movie while its lifecycle is active: title idle/attract
     * videos share an empty frontend stack, so screen identity alone is unsafe. */
    if(video && title && movie_state==1) return 2;
    unsigned stride=*(const unsigned *)(draw+12);
    const float *m=(const float *)(draw+0x60);
    Bounds b;
    if(!bounds(draw,&b))return 0;
    unsigned dim=*(const unsigned *)(draw+0x20),fmt=*(const unsigned *)(draw+0x1c)&63;
    unsigned tw=(dim&8191)+1,th=((dim>>13)&8191)+1;
    int fill=!video && (stride==16 || (m[32]==0 && m[33]==0 && m[34]==0));
    unsigned n=frame_count(scene_begin,scene_end);
    if(!video && full(&b) && (fill || (stride==24 && tw<=128 && th<=128)))return 1;
    if(!video && stride==24 && b.rect && n && tiled_canvas(draw,scene_begin,n))return 1;
    /* Off-canvas APT prompts were intentionally hidden below/above 16:9.
     * Carry them beyond the new edge too; their activation/hit logic is intact. */
    if(!video && b.t>=718)return 4;
    if(!video && b.b<=2)return 3;
    int startup=warmup && (screen==9 || screen==10);
    int backdrop=title || startup || (warmup && screen==0);
    float width=b.r-b.l,height=b.b-b.t;
    if(!video && backdrop && stride==24 &&
       (full(&b) || (width>=1200 && height>=700 && b.l<=80 && b.r>=1200 && b.t<=80 && b.b>=640)))return 1;
    if(!video && title && stride==24 && m[32]==1 && m[33]==1 && m[34]==1) {
        int col=(near(b.l,0)&&near(b.r,1024)&&tw==1024)||
                (near(b.l,1024)&&near(b.r,1280)&&tw==256);
        int row=(near(b.t,0)&&near(b.b,512)&&th==512)||
                (near(b.t,512)&&near(b.b,768)&&th==256);
        if(col&&row)return fmt==18 ? 1 : 2;
    }
    /* Logo letters, prompt, and their animated 32px glow sprites form one
     * top-left title group. Character highlights to the right stay registered
     * with the original central artwork in the optional outpainted image. */
    if(title && ((width<=640 && height<=160 && b.l>=100 && b.r<=620 && b.t>=70 && b.b<240) ||
       (stride==24 && tw==32 && th==32 && width<=640 && height<=400 &&
        (b.l+b.r)*.5f>=100 && (b.l+b.r)*.5f<=620 && (b.t+b.b)*.5f>=70 && (b.t+b.b)*.5f<240)))return 3;
    /* Both loading swirls share this corner, but rotate independently. Their
     * vertices need not occupy the corners of their axis-aligned bounds. */
    unsigned count=*(const unsigned *)(draw+4);
    if(!video && (warmup||in_menu) && stride==24 && (count==4 || count==6) &&
        b.l>=1024 && b.r<=1282 && b.t>=576 && b.b<=722 &&
        width>=12 && width<=128 && height>=12 && height<=128 && width<height*2 && height<width*2)return 4;
    /* Stock title highlights follow the same cover crop as their background.
     * With outpainted art the original center is retained, so no crop is used. */
    if(!video && title && stride==24 && n && stock_title(scene_begin,n))return 2;
    if(startup && b.l>=200 && b.r<=1080 && b.t>=80 && b.b<=660)return 5;
    if(!video && !warmup && !in_menu && n && hud_piece(draw,&b))return hud_anchor(draw,b,scene_begin,n);
    return 0;
}
