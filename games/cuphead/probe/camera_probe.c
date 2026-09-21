/* Local gameplay-only investigation: presentation changes, original logical bounds. */
typedef struct { float x,y,w,h; } Rect;
typedef struct { float e[16]; } Matrix;
extern void original_rect(void*,void*);
extern void *get_camera(void*,void*);
extern Rect get_bounds(void*,void*);
extern Rect get_rect(void*,void*);
extern void set_rect(void*,Rect,void*);
extern void reset_projection(void*,void*);
extern Matrix get_projection(void*,void*);
extern void set_projection(void*,Matrix,void*);
extern float get_size(void*,void*);
extern int get_orthographic(void*,void*);
extern int screen_width(void*,void*);
extern int screen_height(void*,void*);
extern int frame_count(void*,void*);
extern void *string_new(const char*);
extern void debug_log(void*,void*,void*);
extern int access(const char*,int);
extern int sprintf(char*,const char*,...);
static int equal(const char*a,const char*b){while(*a&&*a==*b){++a;++b;}return *a==*b;}
__attribute__((visibility("default"))) void camera_probe(void *self,void *method){
 original_rect(self,method);
 const char *name=*(const char**)(*(char**)self+16);
 if(!equal(name,"CupheadLevelCamera")&&!equal(name,"CupheadMapCamera")) return;
 void *camera=get_camera(self,0);
 if(!camera||!get_orthographic(camera,0))return;
 reset_projection(camera,0);
 Matrix matrix=get_projection(camera,0);
 int w=screen_width(0,0),h=screen_height(0,0);
 int enabled=access("/sdcard/Android/data/com.gabedeveloper.cuphead/files/camera-baseline",0)!=0;
 if(enabled&&w>0&&h>0){
  /* m00 (horizontal projection) is retained exactly. m11 gets the live aspect. */
  matrix.e[5]=matrix.e[0]*(float)w/(float)h;
  set_rect(camera,(Rect){0,0,1,1},0);
  set_projection(camera,matrix,0);
 }
 if(frame_count(0,0)%120==0){
  Rect rect=get_rect(camera,0),bounds=get_bounds(self,0);
  float size=get_size(camera,0),zoom=*(float*)((char*)self+0x88);
  Matrix actual=get_projection(camera,0);
  char line[640];
  sprintf(line,"CUPHEAD4X3 mode=%d type=%s screen=%dx%d ortho=%.6f zoom=%.6f rect=%.4f,%.4f,%.4f,%.4f view=%.6fx%.6f logicalBounds=%.6f,%.6f,%.6f,%.6f m00=%.9f m11=%.9f",
   enabled,name,w,h,(double)size,(double)zoom,(double)rect.x,(double)rect.y,(double)rect.w,(double)rect.h,
   (double)(2.f/actual.e[0]),(double)(2.f/actual.e[5]),(double)bounds.x,(double)bounds.y,(double)bounds.w,(double)bounds.h,(double)actual.e[0],(double)actual.e[5]);
  debug_log(0,string_new(line),0);
 }
}
