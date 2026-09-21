/* Authored controller extensions. All native interfaces are version-guarded by the patcher. */
typedef struct { double real; unsigned flags, kind; } Value;
extern __attribute__((visibility("hidden"))) void *game_globals;
extern __attribute__((visibility("hidden"))) void **gamepads;
extern __attribute__((visibility("hidden"))) int gamepad_count;
extern __attribute__((visibility("hidden"))) unsigned var_dir[4],var_jdis[4],var_p[4],var_inputP1[4],var_inputP2[4],var_usingGamepad[4],var_gamepadSlot[4],var_aimDir[4];
extern Value *find_variable(void *, const char *);
extern void *read_save(const char *, unsigned *);
extern void write_save(const char *, const char *, int, void *);
extern void free_save(const void *);
extern void get_instance_variable(const Value *,int,int,Value *,int,int);
extern float axis_value(void *,int);
extern float point_direction(float,float,float,float);
extern void original_pad_update(void *,float *,float *);
extern Value *original_character_input(void *,void *,Value *,int,Value **);
extern Value *refresh_facing(void *,void *,Value *,int,Value **);
static const char filename[]="android4x3-controls-v1.dat";
static Value *getvar(void *instance, unsigned *descriptor) {
    return ((Value *(*)(void *,int))(*(void ***)instance)[2])(instance,descriptor[2]);
}
static double number(const Value *value) {
    if (value->kind == 0 || value->kind == 13) return value->real;
    if (value->kind == 7) return *(const int *)value;
    if (value->kind == 10) return (double)*(const long *)value;
    return 0;
}
static unsigned read_options(void) {
    if (!game_globals) return 0;
    Value *v=find_variable(game_globals,"android4x3_controller_options_v1");
    if (v->kind!=0 || v->real<256 || v->real>259) {
        unsigned count=0, options=0;
        const unsigned *data=read_save(filename,&count);
        if (data) {
            if (count==8 && data[0]==0x31444c48 && data[1]<=3) options=data[1];
            free_save(data);
        }
        *v=(Value){256+options,0,0};
    }
    return (unsigned)v->real & 3;
}
/* Keep the engine's previous-frame arrays intact: its normal update copies the
   previous mapped frame before we map the freshly received physical frame. */
void map_dpad_stick(float *buttons,int button_count,float *axes,int axis_count,float deadzone) {
    if (button_count<16 || axis_count<2 || !buttons || !axes) return;
    float x=axes[0],y=axes[1];
    if (!(deadzone>=0.15f && deadzone<=0.95f)) deadzone=0.25f;
    float dx=(buttons[15]>0.5f)-(buttons[14]>0.5f);
    float dy=(buttons[13]>0.5f)-(buttons[12]>0.5f);
    buttons[12]=y < -deadzone;
    buttons[13]=y > deadzone;
    buttons[14]=x < -deadzone;
    buttons[15]=x > deadzone;
    axes[0]=dx; axes[1]=dy;
}
__attribute__((section(".text.pad_hook"))) void controller_update(void *pad,float *buttons,float *axes) {
    original_pad_update(pad,buttons,axes);
    unsigned options=read_options();
    if (buttons && axes) {
        char *p=pad;
        float *mapped_buttons=*(float **)(p+0x18);
        if ((options&2) && *(int *)(p+4)>6 && *(int *)(p+8)>3) {
            float x=axis_value(pad,2),y=axis_value(pad,3);
            if (x*x+y*y>0.01f) mapped_buttons[6]=1;
        }
        if (options&1) map_dpad_stick(mapped_buttons,*(int *)(p+4),*(float **)(p+0x20),*(int *)(p+8),*(float *)(p+0x54));
    }
}
/* Read the selected player's physical right stick. Apply aim independently of
   movement, and refresh it at shot creation because light weapons use dir. */
static int right_aim(void *self,double *angle) {
    if (!(read_options()&2) || !game_globals) return 0;
    int player=(int)number(getvar(self,var_p));
    if (player<0 || player>1) return 0;
    Value input=*getvar(game_globals,player ? var_inputP2 : var_inputP1);
    Value using_pad={0,0,0},slot={-1,0,0};
    get_instance_variable(&input,var_usingGamepad[2],0x80000000,&using_pad,0,0);
    if (number(&using_pad)!=1) return 0;
    get_instance_variable(&input,var_gamepadSlot[2],0x80000000,&slot,0,0);
    int index=(int)number(&slot);
    if (index<0 || index>=gamepad_count || !gamepads[index]) return 0;
    float x=axis_value(gamepads[index],2),y=axis_value(gamepads[index],3);
    if (x*x+y*y<=0.01f) return 0;
    *angle=point_direction(0,0,x,y);
    return 1;
}
static void set_number(void *self,unsigned *descriptor,double value) {
    Value *v=((Value *(*)(void *,int))(*(void ***)self)[3])(self,descriptor[2]);
    *v=(Value){value,0,0};
}

__attribute__((section(".text.aim_hook"))) Value *character_input(void *self,void *other,Value *out,int count,Value **args) {
    Value *result=original_character_input(self,other,out,count,args);
    double angle;
    if (right_aim(self,&angle)) {
        set_number(self,var_aimDir,angle);
        set_number(self,var_dir,angle);
        Value temporary={0,0,0};
        refresh_facing(self,other,&temporary,0,0);
    }
    return result;
}
extern __attribute__((visibility("hidden"))) unsigned var_dir[4];
extern Value *original_fire_light(void *,void *,Value *,int,Value **);
extern Value *original_fire_rail(void *,void *,Value *,int,Value **);
extern Value *original_fire_blast(void *,void *,Value *,int,Value **);
static void prepare_shot(void *self) {
    double angle;
    if (right_aim(self,&angle)) {
        set_number(self,var_aimDir,angle);
        set_number(self,var_dir,angle);
    }
}
#define FIRE_HOOK(name) \
Value *fire_##name(void *self,void *other,Value *out,int count,Value **args) { \
    prepare_shot(self); \
    return original_fire_##name(self,other,out,count,args); \
}
FIRE_HOOK(light)
FIRE_HOOK(rail)
FIRE_HOOK(blast)
extern __attribute__((visibility("hidden"))) unsigned var_state[4],var_S_CONTROLS[4],var_largeMenuX[4],var_largeMenuY[4],var_largeMenuBGHei[4],var_HView_0[4];
extern __attribute__((visibility("hidden"))) unsigned fn_gui_width[4],fn_gui_height[4],fn_mouse_x[4],fn_mouse_y[4];
extern void original_menu_step(void *,void *);
extern void original_menu_draw(void *,void *);
extern int pad_pressed(void *,int);
extern int pad_down(void *,int);
extern void mouse_pressed(Value *,void *,void *,int,Value *);
extern Value *legacy_call(void *,void *,Value *,int,int,Value **);
extern void create_string(Value *,const char *);
extern void free_value(Value *);
extern Value *font_language(void *,void *,Value *,int,Value **);
extern Value *text_caps(void *,void *,Value *,int,Value **);
extern void draw_rectangle(float,float,float,float,int);
extern void draw_alpha(float);
extern void draw_color(unsigned);
extern void draw_halign(int);
extern void draw_valign(int);
static Value *private_value(void *self,const char *name) {
    Value *v=find_variable(self,name);
    if (v->kind!=0) *v=(Value){0,0,0};
    return v;
}
static int is_controls(void *self) {
    return number(getvar(self,var_state))==number(getvar(self,var_S_CONTROLS));
}
static double canvas_height(void) {
    double h=number(getvar(game_globals,var_HView_0));
    return h==360 ? 360 : 270;
}
static unsigned input_mask(void) {
    unsigned mask=0;
    for (int i=0;i<gamepad_count;i++) {
        char *p=gamepads[i];if (!p) continue;
        for (int b=0;b<16;b++) if (pad_down(p,b)) mask|=1u<<b;
        if (*(int *)(p+8)>1) {
            float x=axis_value(p,0),y=axis_value(p,1);
            if (y<-.5f) mask|=1u<<12;
            if (y>.5f) mask|=1u<<13;
            if (x<-.5f) mask|=1u<<14;
            if (x>.5f) mask|=1u<<15;
        }
    }
    return mask;
}
static double builtin(void *self,void *other,unsigned *fn) {
    Value result={0,0,0},zero={0,0,0};Value *args[]={&zero};
    legacy_call(self,other,&result,1,fn[2],args);
    return number(&result);
}
static int touch(void *self,void *other,double *x,double *y) {
    Value result={0,0,0},args[]={{0,0,0},{1,0,0}};
    mouse_pressed(&result,self,other,2,args);
    if (!number(&result)) return 0;
    double w=builtin(self,other,fn_gui_width),h=builtin(self,other,fn_gui_height);
    if (w<=0 || h<=0) return 0;
    *x=builtin(self,other,fn_mouse_x)*480/w;
    *y=builtin(self,other,fn_mouse_y)*canvas_height()/h;
    return 1;
}
static int save_options(unsigned options) {
    unsigned data[]={0x31444c48,options},count=0;
    write_save(filename,(const char *)data,8,0);
    const unsigned *check=read_save(filename,&count);
    int ok=check && count==8 && check[0]==data[0] && check[1]==options;
    if (check) free_save(check);
    if (ok) *find_variable(game_globals,"android4x3_controller_options_v1")=(Value){256+options,0,0};
    return ok;
}
__attribute__((section(".text.menu_step_hook"))) void menu_step(void *self,void *other) {
    unsigned held=input_mask();
    Value *previous=private_value(self,"android4x3_controls_previous_input");
    unsigned pressed=held & ~(unsigned)previous->real;
    previous->real=held;
    Value *page=private_value(self,"android4x3_controls_page");
    if (!is_controls(self)) { page->real=0;original_menu_step(self,other);return; }
    double x=0,y=0;int tapped=touch(self,other,&x,&y);
    double entry_x=number(getvar(self,var_largeMenuX))+10;
    double entry_y=number(getvar(self,var_largeMenuY))+number(getvar(self,var_largeMenuBGHei))+1;
    if (!page->real) {
        if ((pressed&1) || (tapped && x>=entry_x && x<=entry_x+220 && y>=entry_y-4 && y<=entry_y+20)) {
            page->real=1;return;
        }
        original_menu_step(self,other);return;
    }
    double cy=canvas_height()/2;
    if ((pressed&2) || (tapped && x>=40 && x<=180 && y>=cy+74 && y<=cy+98)) {
        page->real=0;return;
    }
    Value *selection=private_value(self,"android4x3_controls_selection");
    if ((pressed&0x3000)) selection->real=selection->real ? 0 : 1;
    int activate=(pressed&1)||(pressed&0xc000);
    if (tapped && x>=40 && x<=440) {
        if (y>=cy-38 && y<=cy-8) {selection->real=0;activate=1;}
        if (y>=cy+4 && y<=cy+34) {selection->real=1;activate=1;}
    }
    if (activate) {
        int ok=save_options(read_options()^(selection->real ? 2 : 1));
        private_value(self,"android4x3_controls_save_error")->real=!ok;
    }
}
static void label(void *self,void *other,double x,double y,const char *text,unsigned color) {
    Value xx={x,0,0},yy={y,0,0},s={0,0,5},out={0,0,5};
    Value *args[]={&xx,&yy,&s};
    create_string(&s,text);draw_color(color);
    text_caps(self,other,&out,3,args);
    free_value(&s);if (out.kind==1 || out.kind==2 || out.kind==6) free_value(&out);
}
extern __attribute__((visibility("hidden"))) unsigned var_room[4];
extern void get_builtin(void *,int,int,Value *);
extern void draw_sprite(void *,int,float,float,float,float,float,float,int,float);
static void title_extensions(void *self) {
    if (canvas_height()!=360) return;
    Value room={0,0,0};get_builtin(self,var_room[2],0x80000000,&room);
    if (number(&room)!=6) return;
    draw_sprite(self,3630,0,60,0,.75f,.75f,0,0xffffff,1);
    draw_sprite(self,3631,0,60,315,.75f,.75f,0,0xffffff,1);
}
__attribute__((section(".text.menu_draw_hook"))) void menu_draw(void *self,void *other) {
    title_extensions(self);
    original_menu_draw(self,other);
    if (!is_controls(self)) return;
    unsigned color=0xffffff,pink=0xff00ff;
    draw_halign(0);draw_valign(0);draw_alpha(1);
    if (!private_value(self,"android4x3_controls_page")->real) {
        double x=number(getvar(self,var_largeMenuX))+10;
        double y=number(getvar(self,var_largeMenuY))+number(getvar(self,var_largeMenuBGHei))+1;
        label(self,other,x,y,"A  CONTROLLER OPTIONS",color);return;
    }
    double cy=canvas_height()/2;
    draw_color(0);draw_rectangle(24,cy-104,456,cy+106,0);
    draw_color(pink);draw_rectangle(24,cy-104,456,cy+106,1);
    Value out={0,0,5};font_language(self,other,&out,0,0);
    label(self,other,40,cy-86,"CONTROLLER OPTIONS",color);
    unsigned options=read_options();int selected=private_value(self,"android4x3_controls_selection")->real!=0;
    draw_color(0x452645);draw_rectangle(36,cy+(selected ? 4:-38),444,cy+(selected ? 34:-8),0);
    label(self,other,44,cy-29,"SWAP LEFT STICK / D-PAD",color);
    label(self,other,372,cy-29,options&1 ? "ON":"OFF",pink);
    label(self,other,44,cy+13,"AIMING STICK",color);
    label(self,other,328,cy+13,options&2 ? "RIGHT":"LEFT",pink);
    label(self,other,40,cy+52,"A CHANGE    UP/DOWN SELECT",color);
    label(self,other,40,cy+82,"B BACK",color);
    if (private_value(self,"android4x3_controls_save_error")->real) label(self,other,160,cy+82,"SAVE FAILED - RETRY",pink);
    draw_color(color);
}

/* Weapon updates can create shots inline. Scope facing to that update so
   movement and dash direction remain owned by the original input path. */
extern Value *original_weapon_crystalgun(void *,void *,Value *,int,Value **);
Value *weapon_crystalgun(void *self,void *other,Value *out,int count,Value **args) {
    double angle;
    if (!right_aim(self,&angle)) return original_weapon_crystalgun(self,other,out,count,args);
    Value saved=*getvar(self,var_dir);
    set_number(self,var_dir,angle);
    set_number(self,var_aimDir,angle);
    Value *result=original_weapon_crystalgun(self,other,out,count,args);
    Value *direction=((Value *(*)(void *,int))(*(void ***)self)[3])(self,var_dir[2]);
    *direction=saved;
    return result;
}
extern Value *original_weapon_railgunlight(void *,void *,Value *,int,Value **);
Value *weapon_railgunlight(void *self,void *other,Value *out,int count,Value **args) {
    double angle;
    if (!right_aim(self,&angle)) return original_weapon_railgunlight(self,other,out,count,args);
    Value saved=*getvar(self,var_dir);
    set_number(self,var_dir,angle);
    set_number(self,var_aimDir,angle);
    Value *result=original_weapon_railgunlight(self,other,out,count,args);
    Value *direction=((Value *(*)(void *,int))(*(void ***)self)[3])(self,var_dir[2]);
    *direction=saved;
    return result;
}
extern Value *original_weapon_railgunscope(void *,void *,Value *,int,Value **);
Value *weapon_railgunscope(void *self,void *other,Value *out,int count,Value **args) {
    double angle;
    if (!right_aim(self,&angle)) return original_weapon_railgunscope(self,other,out,count,args);
    Value saved=*getvar(self,var_dir);
    set_number(self,var_dir,angle);
    set_number(self,var_aimDir,angle);
    Value *result=original_weapon_railgunscope(self,other,out,count,args);
    Value *direction=((Value *(*)(void *,int))(*(void ***)self)[3])(self,var_dir[2]);
    *direction=saved;
    return result;
}
extern Value *original_weapon_railgunzap(void *,void *,Value *,int,Value **);
Value *weapon_railgunzap(void *self,void *other,Value *out,int count,Value **args) {
    double angle;
    if (!right_aim(self,&angle)) return original_weapon_railgunzap(self,other,out,count,args);
    Value saved=*getvar(self,var_dir);
    set_number(self,var_dir,angle);
    set_number(self,var_aimDir,angle);
    Value *result=original_weapon_railgunzap(self,other,out,count,args);
    Value *direction=((Value *(*)(void *,int))(*(void ***)self)[3])(self,var_dir[2]);
    *direction=saved;
    return result;
}
extern Value *original_weapon_railgunauto(void *,void *,Value *,int,Value **);
Value *weapon_railgunauto(void *self,void *other,Value *out,int count,Value **args) {
    double angle;
    if (!right_aim(self,&angle)) return original_weapon_railgunauto(self,other,out,count,args);
    Value saved=*getvar(self,var_dir);
    set_number(self,var_dir,angle);
    set_number(self,var_aimDir,angle);
    Value *result=original_weapon_railgunauto(self,other,out,count,args);
    Value *direction=((Value *(*)(void *,int))(*(void ***)self)[3])(self,var_dir[2]);
    *direction=saved;
    return result;
}
extern Value *original_weapon_railgun(void *,void *,Value *,int,Value **);
Value *weapon_railgun(void *self,void *other,Value *out,int count,Value **args) {
    double angle;
    if (!right_aim(self,&angle)) return original_weapon_railgun(self,other,out,count,args);
    Value saved=*getvar(self,var_dir);
    set_number(self,var_dir,angle);
    set_number(self,var_aimDir,angle);
    Value *result=original_weapon_railgun(self,other,out,count,args);
    Value *direction=((Value *(*)(void *,int))(*(void ***)self)[3])(self,var_dir[2]);
    *direction=saved;
    return result;
}
extern Value *original_weapon_railgunblast(void *,void *,Value *,int,Value **);
Value *weapon_railgunblast(void *self,void *other,Value *out,int count,Value **args) {
    double angle;
    if (!right_aim(self,&angle)) return original_weapon_railgunblast(self,other,out,count,args);
    Value saved=*getvar(self,var_dir);
    set_number(self,var_dir,angle);
    set_number(self,var_aimDir,angle);
    Value *result=original_weapon_railgunblast(self,other,out,count,args);
    Value *direction=((Value *(*)(void *,int))(*(void ***)self)[3])(self,var_dir[2]);
    *direction=saved;
    return result;
}

/* Weapon updates can create shots inline. Scope facing to that update so
   movement and dash direction remain owned by the original input path. */
extern Value *original_weapon_pistol(void *,void *,Value *,int,Value **);
Value *weapon_pistol(void *self,void *other,Value *out,int count,Value **args) {
    double angle;
    if (!right_aim(self,&angle)) return original_weapon_pistol(self,other,out,count,args);
    Value saved=*getvar(self,var_dir);
    set_number(self,var_dir,angle);
    set_number(self,var_aimDir,angle);
    Value *result=original_weapon_pistol(self,other,out,count,args);
    Value *direction=((Value *(*)(void *,int))(*(void ***)self)[3])(self,var_dir[2]);
    *direction=saved;
    return result;
}
extern Value *original_weapon_pistolzeliska(void *,void *,Value *,int,Value **);
Value *weapon_pistolzeliska(void *self,void *other,Value *out,int count,Value **args) {
    double angle;
    if (!right_aim(self,&angle)) return original_weapon_pistolzeliska(self,other,out,count,args);
    Value saved=*getvar(self,var_dir);
    set_number(self,var_dir,angle);
    set_number(self,var_aimDir,angle);
    Value *result=original_weapon_pistolzeliska(self,other,out,count,args);
    Value *direction=((Value *(*)(void *,int))(*(void ***)self)[3])(self,var_dir[2]);
    *direction=saved;
    return result;
}
extern Value *original_weapon_diamondblunderbuss(void *,void *,Value *,int,Value **);
Value *weapon_diamondblunderbuss(void *self,void *other,Value *out,int count,Value **args) {
    double angle;
    if (!right_aim(self,&angle)) return original_weapon_diamondblunderbuss(self,other,out,count,args);
    Value saved=*getvar(self,var_dir);
    set_number(self,var_dir,angle);
    set_number(self,var_aimDir,angle);
    Value *result=original_weapon_diamondblunderbuss(self,other,out,count,args);
    Value *direction=((Value *(*)(void *,int))(*(void ***)self)[3])(self,var_dir[2]);
    *direction=saved;
    return result;
}
extern Value *original_weapon_diamondshotgun(void *,void *,Value *,int,Value **);
Value *weapon_diamondshotgun(void *self,void *other,Value *out,int count,Value **args) {
    double angle;
    if (!right_aim(self,&angle)) return original_weapon_diamondshotgun(self,other,out,count,args);
    Value saved=*getvar(self,var_dir);
    set_number(self,var_dir,angle);
    set_number(self,var_aimDir,angle);
    Value *result=original_weapon_diamondshotgun(self,other,out,count,args);
    Value *direction=((Value *(*)(void *,int))(*(void ***)self)[3])(self,var_dir[2]);
    *direction=saved;
    return result;
}
extern Value *original_weapon_diamondcharge(void *,void *,Value *,int,Value **);
Value *weapon_diamondcharge(void *self,void *other,Value *out,int count,Value **args) {
    double angle;
    if (!right_aim(self,&angle)) return original_weapon_diamondcharge(self,other,out,count,args);
    Value saved=*getvar(self,var_dir);
    set_number(self,var_dir,angle);
    set_number(self,var_aimDir,angle);
    Value *result=original_weapon_diamondcharge(self,other,out,count,args);
    Value *direction=((Value *(*)(void *,int))(*(void ***)self)[3])(self,var_dir[2]);
    *direction=saved;
    return result;
}
extern Value *original_weapon_scuttlerpistol(void *,void *,Value *,int,Value **);
Value *weapon_scuttlerpistol(void *self,void *other,Value *out,int count,Value **args) {
    double angle;
    if (!right_aim(self,&angle)) return original_weapon_scuttlerpistol(self,other,out,count,args);
    Value saved=*getvar(self,var_dir);
    set_number(self,var_dir,angle);
    set_number(self,var_aimDir,angle);
    Value *result=original_weapon_scuttlerpistol(self,other,out,count,args);
    Value *direction=((Value *(*)(void *,int))(*(void ***)self)[3])(self,var_dir[2]);
    *direction=saved;
    return result;
}
extern Value *original_weapon_tracerpistol(void *,void *,Value *,int,Value **);
Value *weapon_tracerpistol(void *self,void *other,Value *out,int count,Value **args) {
    double angle;
    if (!right_aim(self,&angle)) return original_weapon_tracerpistol(self,other,out,count,args);
    Value saved=*getvar(self,var_dir);
    set_number(self,var_dir,angle);
    set_number(self,var_aimDir,angle);
    Value *result=original_weapon_tracerpistol(self,other,out,count,args);
    Value *direction=((Value *(*)(void *,int))(*(void ***)self)[3])(self,var_dir[2]);
    *direction=saved;
    return result;
}
extern Value *original_weapon_rifle(void *,void *,Value *,int,Value **);
Value *weapon_rifle(void *self,void *other,Value *out,int count,Value **args) {
    double angle;
    if (!right_aim(self,&angle)) return original_weapon_rifle(self,other,out,count,args);
    Value saved=*getvar(self,var_dir);
    set_number(self,var_dir,angle);
    set_number(self,var_aimDir,angle);
    Value *result=original_weapon_rifle(self,other,out,count,args);
    Value *direction=((Value *(*)(void *,int))(*(void ***)self)[3])(self,var_dir[2]);
    *direction=saved;
    return result;
}
extern Value *original_weapon_burstrifle(void *,void *,Value *,int,Value **);
Value *weapon_burstrifle(void *self,void *other,Value *out,int count,Value **args) {
    double angle;
    if (!right_aim(self,&angle)) return original_weapon_burstrifle(self,other,out,count,args);
    Value saved=*getvar(self,var_dir);
    set_number(self,var_dir,angle);
    set_number(self,var_aimDir,angle);
    Value *result=original_weapon_burstrifle(self,other,out,count,args);
    Value *direction=((Value *(*)(void *,int))(*(void ***)self)[3])(self,var_dir[2]);
    *direction=saved;
    return result;
}
extern Value *original_weapon_chargeshot(void *,void *,Value *,int,Value **);
Value *weapon_chargeshot(void *self,void *other,Value *out,int count,Value **args) {
    double angle;
    if (!right_aim(self,&angle)) return original_weapon_chargeshot(self,other,out,count,args);
    Value saved=*getvar(self,var_dir);
    set_number(self,var_dir,angle);
    set_number(self,var_aimDir,angle);
    Value *result=original_weapon_chargeshot(self,other,out,count,args);
    Value *direction=((Value *(*)(void *,int))(*(void ***)self)[3])(self,var_dir[2]);
    *direction=saved;
    return result;
}

/* Only this call site writes the two-frame stop caused by holding aim.
   In right-stick mode, direct that write to an unused owned value, leaving
   stun, cutscene, melee and other movement restrictions untouched. */
Value *aim_movement_lock(void *self,int variable) {
    if (read_options()&2) return find_variable(self,"android4x3_unused_aim_stop");
    return ((Value *(*)(void *,int))(*(void ***)self)[3])(self,variable);
}

extern __attribute__((visibility("hidden"))) unsigned var_gunphase[4];
extern __attribute__((visibility("hidden"))) Value movement_idle;
extern Value *original_basic_movement(void *,void *,Value *,int,Value **);
Value *basic_movement(void *self,void *other,Value *out,int count,Value **args) {
    double angle;
    if (!right_aim(self,&angle)) return original_basic_movement(self,other,out,count,args);
    Value saved=*getvar(self,var_gunphase);
    Value *phase=((Value *(*)(void *,int))(*(void ***)self)[3])(self,var_gunphase[2]);
    *phase=movement_idle;
    Value *result=original_basic_movement(self,other,out,count,args);
    phase=((Value *(*)(void *,int))(*(void ***)self)[3])(self,var_gunphase[2]);
    *phase=saved;
    return result;
}

/* Let the existing locomotion animation selector run while the right stick
   aims and the player is moving. This read does not change the weapon state. */
Value *aim_animation_phase(void *self,int variable) {
    double angle;
    if (right_aim(self,&angle) && number(getvar(self,var_jdis))>0.15)
        return &movement_idle;
    return ((Value *(*)(void *,int))(*(void ***)self)[3])(self,variable);
}
