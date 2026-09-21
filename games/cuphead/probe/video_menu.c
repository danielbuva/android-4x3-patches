/* New Video choices integrated with Cuphead's existing controller navigation. */
#include "ui.h"
extern void original_options_update(void*,void*);
extern void original_visual_select(void*,void*);
extern void *object_new(void*);
extern Array *array_new(void*,unsigned long);
extern void *instantiate_parent(void*,void*,void*,int,void*);
extern void *get_transform(void*,void*);
extern void *go_transform(void*,void*);
extern void *get_parent(void*,void*);
extern void *get_child(void*,int,void*);
extern void *component_go(void*,void*);
extern void *get_component(void*,void*,void*);
extern void *type_object(void*);
extern void *class_type(void*);
extern void set_sibling(void*,int,void*);
extern void set_active(void*,int,void*);
extern void set_name(void*,void*,void*);
extern void text_set(void*,void*,void*);
extern void text_font_size(void*,int,void*);
extern void set_scale(void*,Vec3,void*);
extern Vec3 get_local_position(void*,void*);
extern void set_local_position(void*,Vec3,void*);
extern void *graphic_rect(void*,void*);
extern void *graphic_canvas(void*,void*);
extern void *canvas_camera(void*,void*);
extern int mouse_down(void*,int,void*);
extern Vec3 mouse_position(void*,void*);
extern int rect_contains(void*,void*,Vec2,void*,void*);
extern void vertical_selection(void*,int,void*);
extern void menu_select_sound(void*,void*);
extern void debug_log(void*,void*,void*);
extern int sprintf(char*,const char*,...);
#define PTR(o,off) (*(void**)((char*)(o)+(off)))
#define INT(o,off) (*(int*)((char*)(o)+(off)))
static Array *buttons(void *self){return (Array*)PTR(self,0xa8);}
static void *button_text(void *button){return PTR(button,0x10);}
static const char *label(int i,int chosen){
 if(i==0)return chosen?"[X] 16:9 ORIGINAL":"[ ] 16:9 ORIGINAL";
 if(i==1)return chosen?"[X] 4:3 EXPANDED":"[ ] 4:3 EXPANDED";
 return chosen?"[X] 4:3 CROPPED":"[ ] 4:3 CROPPED";
}
static void paint(void *self){
 Array *a=buttons(self);if(!a||a->count!=12)return;
 int mode=display_mode();
 for(int i=0;i<3;++i)text_set(button_text(a->items[8+i]),string_new(label(i,mode==i)),0);
}
static void choose(void *self,int mode){
 if(mode<0||mode>2)return;
 if(display_mode()!=mode){
  const char *value=mode==0?"0":mode==1?"1":"2";
  prefs_set(0,string_new("cuphead_4x3_display_mode"),string_new(value),0);prefs_save(0,0);
  char line[128];sprintf(line,"CUPHEAD_VIDEO selected=%d persisted=1 mapExpanded=%d",mode,mode!=0);
  debug_log(0,string_new(line),0);
 }
 menu_select_sound(self,0);paint(self);
}
static void initialize(void *self){
 Array *old=buttons(self);if(!old||old->count!=9)return;
 void *back=old->items[8],*text=button_text(back);
 if(!back||!text)return;
 void *holder=get_parent(get_transform(text,0),0),*column=get_parent(holder,0);
 if(!holder||!column)return;
 Array *next=array_new(*(void**)back,12);
 for(int i=0;i<8;++i)next->items[i]=old->items[i];
 next->items[11]=back;
 for(int i=0;i<3;++i){
  void *row=instantiate_parent(0,component_go(holder,0),column,0,0);
  void *transform=go_transform(row,0);set_sibling(transform,8+i,0);
  void *child=get_child(transform,0,0);
  void *cloned=get_component(component_go(child,0),type_object(class_type(*(void**)text)),0);
  void *button=object_new(*(void**)back);
  PTR(button,0x10)=cloned;PTR(button,0x18)=0;PTR(button,0x20)=PTR(back,0x20);
  INT(button,0x28)=0;*((char*)button+0x2c)=0;
  next->items[8+i]=button;
  set_name(row,string_new(i==0?"CupheadMode16x9":i==1?"CupheadModeExpanded":"CupheadModeCropped"),0);
  text_font_size(cloned,36,0);set_active(row,1,0);
 }
 PTR(self,0xa8)=next;
 paint(self);
 debug_log(0,string_new("CUPHEAD_VIDEO initialized=3 navigationItems=12"),0);
}
void options_update(void *self,void *method){
 initialize(self);
 original_options_update(self,method);
 Array *a=buttons(self);if(!a||a->count!=12)return;
 int visual=INT(self,0x14c)==1;
 /* Uniform enlargement, never an aspect-changing transform. */
 void *visualGO=PTR(self,0x58);if(visualGO){
  void *transform=go_transform(visualGO,0);
  set_scale(transform,(Vec3){2.f,2.f,1.f},0);
  Vec3 position=get_local_position(transform,0);position.y=142.f;
  set_local_position(transform,position,0);
 }
 void *card=PTR(self,0x98);if(card){float s=visual?1.3f:1.f;set_scale(go_transform(card,0),(Vec3){s,s,s},0);}
 if(!visual||!*((char*)self+0x151))return;
 paint(self);
 if(mouse_down(0,0,0)){
  Vec3 p=mouse_position(0,0);
  for(int i=0;i<3;++i){
   void *text=button_text(a->items[8+i]);void *canvas=graphic_canvas(text,0);
   void *camera=canvas?canvas_camera(canvas,0):0;
   if(rect_contains(0,graphic_rect(text,0),(Vec2){p.x,p.y},camera,0)){
    vertical_selection(self,8+i,0);choose(self,i);break;
   }
  }
 }
}
void visual_select(void *self,void *method){
 Array *a=buttons(self);int index=INT(self,0x11c);
 if(a&&a->count==12){
  if(index>=8&&index<=10){choose(self,index-8);return;}
  if(index==11)INT(self,0x11c)=8;
 }
 original_visual_select(self,method);
}
