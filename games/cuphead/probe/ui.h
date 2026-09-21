typedef struct { float x,y; } Vec2;
typedef struct { float x,y,z; } Vec3;
typedef struct { void *klass,*monitor,*bounds; unsigned long count; void *items[]; } Array;
extern void *string_new(const char*);
extern void *prefs_get(void*,void*,void*,void*);
extern void prefs_set(void*,void*,void*,void*);
extern void prefs_save(void*,void*);
static int display_mode(void){
 void *s=prefs_get(0,string_new("cuphead_4x3_display_mode"),string_new("1"),0);
 if(!s||*(int*)((char*)s+16)!=1)return 1;
 int n=*(unsigned short*)((char*)s+20)-'0';
 return n>=0&&n<=2?n:1;
}
