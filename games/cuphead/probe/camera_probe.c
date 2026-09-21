#include "ui.h"
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
extern void *current_level(void*,void*);
extern int object_alive(void*,void*,void*);
extern int sprintf(char*,const char*,...);

extern void *domain_get(void);
extern void *assembly_open(void*,const char*);
extern void *assembly_image(void*);
extern void *class_from_name(void*,const char*,const char*);
extern void *object_new(void*);
extern void *class_type(void*);
extern void *type_object(void*);
extern void gameobject_ctor(void*,void*,void*);
extern void *gameobject_find(void*,void*,void*);
extern void *add_component(void*,void*,void*);
extern void *get_component(void*,void*,void*);
extern void *get_transform(void*,void*);
extern void set_parent(void*,void*,int,void*);
extern void camera_copy(void*,void*,void*);
extern float get_depth(void*,void*);
extern void set_depth(void*,float,void*);
extern void set_mask(void*,int,void*);
extern void set_clear(void*,int,void*);
extern void set_enabled(void*,int,void*);
extern void set_size(void*,float,void*);
extern void scaler_set(void*,Vec2,void*);
void canvas_reference(void *self,Vec2 value,void *method){
 int w=screen_width(0,0),h=screen_height(0,0);
 if(display_mode()!=0&&w>0&&h>0)value.y=value.x*(float)h/(float)w;
 scaler_set(self,value,method);
}
static void split_background(void *camera, Matrix original, int w,int h){
 void *marker=gameobject_find(0,string_new("lv1-1_mg_meadow-loop"),0);
 if(!marker) return;
 void *cameraType=type_object(class_type(*(void**)camera));
 void *go=gameobject_find(0,string_new("Cuphead4x3BackgroundTrial"),0);
 void *background=go?get_component(go,cameraType,0):0;
 if(!background){
  void *assembly=assembly_open(domain_get(),"UnityEngine.CoreModule");
  if(!assembly)assembly=assembly_open(domain_get(),"UnityEngine");
  if(!assembly)return;
  void *klass=class_from_name(assembly_image(assembly),"UnityEngine","GameObject");
  if(!klass)return;
  go=object_new(klass);
  gameobject_ctor(go,string_new("Cuphead4x3BackgroundTrial"),0);
  background=add_component(go,cameraType,0);
  if(!background)return;
  set_parent(get_transform(background,0),get_transform(camera,0),0,0);
 }
 camera_copy(background,camera,0);
 set_depth(background,get_depth(camera,0)-1.f,0);
 set_mask(background,1<<29,0);
 set_clear(background,2,0);
 set_rect(background,(Rect){0,0,1,1},0);
 /* Keep original vertical coverage; proportionally crop only decoration in X. */
 original.e[0]=original.e[5]*(float)h/(float)w;
 set_projection(background,original,0);
 set_enabled(background,1,0);
 set_mask(camera,~(1<<29),0);
 set_clear(camera,3,0);
 if(frame_count(0,0)%120==0){
  char line[256];
  sprintf(line,"CUPHEAD_BACKGROUND view=%.6fx%.6f depth=%.1f",
    (double)(2.f/original.e[0]),(double)(2.f/original.e[5]),(double)get_depth(background,0));
  debug_log(0,string_new(line),0);
 }
}
static int equal(const char*a,const char*b){while(*a&&*a==*b){++a;++b;}return *a==*b;}
__attribute__((visibility("default"))) void camera_probe(void *self,void *method){
 original_rect(self,method);
 const char *name=*(const char**)(*(char**)self+16);
 int ui=equal(name,"CupheadUICamera"),level=equal(name,"CupheadLevelCamera");
 if(!ui&&!level&&!equal(name,"CupheadMapCamera")) return;
 void *camera=get_camera(self,0);
 if(!camera||!get_orthographic(camera,0))return;
 int mode=display_mode();
 int width=screen_width(0,0),height=screen_height(0,0);
 if(ui){
  if(mode==0){set_size(camera,360.f,0);reset_projection(camera,0);return;}
  if(width>0&&height>0){set_size(camera,640.f*(float)height/(float)width,0);set_rect(camera,(Rect){0,0,1,1},0);reset_projection(camera,0);}
  return;
 }
 reset_projection(camera,0);
 Matrix matrix=get_projection(camera,0);
 int w=screen_width(0,0),h=screen_height(0,0);
 int enabled=mode!=0;
 /* Cropped framing applies only while a live gameplay Level exists. */
 if(mode==2&&level&&!object_alive(0,current_level(0,0),0))enabled=0;
 if(level&&!enabled){
  void *go=gameobject_find(0,string_new("Cuphead4x3BackgroundTrial"),0);
  if(go){
   void *bg=get_component(go,type_object(class_type(*(void**)camera)),0);
   if(bg)set_enabled(bg,0,0);
   set_mask(camera,-1,0);set_clear(camera,2,0);
  }
 }
 if(enabled&&w>0&&h>0){
  /* m00 (horizontal projection) is retained exactly. m11 gets the live aspect. */
  if(equal(name,"CupheadLevelCamera"))split_background(camera,matrix,w,h);
  if(mode==2&&level)matrix.e[0]=matrix.e[5]*(float)h/(float)w;
  else matrix.e[5]=matrix.e[0]*(float)w/(float)h;
  set_rect(camera,(Rect){0,0,1,1},0);
  set_projection(camera,matrix,0);
 }
 if(frame_count(0,0)%120==0){
  Rect rect=get_rect(camera,0),bounds=get_bounds(self,0);
  float size=get_size(camera,0),zoom=*(float*)((char*)self+0x88);
  Matrix actual=get_projection(camera,0);
  char line[640];
  sprintf(line,"CUPHEAD4X3 mode=%d type=%s screen=%dx%d ortho=%.6f zoom=%.6f rect=%.4f,%.4f,%.4f,%.4f view=%.6fx%.6f logicalBounds=%.6f,%.6f,%.6f,%.6f m00=%.9f m11=%.9f",
   mode,name,w,h,(double)size,(double)zoom,(double)rect.x,(double)rect.y,(double)rect.w,(double)rect.h,
   (double)(2.f/actual.e[0]),(double)(2.f/actual.e[5]),(double)bounds.x,(double)bounds.y,(double)bounds.w,(double)bounds.h,(double)actual.e[0],(double)actual.e[5]);
  debug_log(0,string_new(line),0);
 }
}
