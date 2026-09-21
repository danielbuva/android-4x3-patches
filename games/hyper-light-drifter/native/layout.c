typedef struct { double real; unsigned flags; unsigned kind; } Value;
extern void *assign(void *, const void *);
extern void get_builtin(void *, int, int, Value *);
extern __attribute__((visibility("hidden"))) unsigned total_time_var[4];
__attribute__((section(".text.entry"))) void *camera_height(void *dst, const void *src) {
    void *result = assign(dst, src);
    Value *v = dst;
    if (v->kind == 0 && v->real == 270.0) v->real = 360.0;
    return result;
}
__attribute__((section(".text.startup_hook"))) void startup_room(void *self, int variable, int index, Value *room) {
    get_builtin(self, variable, index, room);
    double number = room->kind == 0 ? room->real : room->kind == 7 ? *(int *)room : -1;
    if (number == 3 || number == 5) {
        void **vtable = *(void ***)self;
        Value *value = ((Value *(*)(void *, int))vtable[3])(self, total_time_var[2]);
        if (value->kind == 0 && value->real == 167.0) value->real = 90.0;
    }
}
extern Value *draw_hologram(void *, void *, Value *, int, Value **);
extern void draw_rectangle(float, float, float, float, int);
extern void draw_alpha(float);
extern void draw_color(unsigned);
extern __attribute__((visibility("hidden"))) unsigned current_color;
extern __attribute__((visibility("hidden"))) unsigned current_alpha;
__attribute__((section(".text.background_hook"))) Value *menu_background(void *self, void *other, Value *result, int count, Value **args) {
    if (count != 6 || args[0]->kind != 0 || args[0]->real != 3277.0 || args[3]->kind != 0 || args[3]->real != 0.0 || args[5]->kind != 0)
        return draw_hologram(self, other, result, count, args);
    unsigned color = current_color, alpha = current_alpha;
    draw_color(0);
    draw_alpha((float)args[5]->real);
    draw_rectangle(0, 0, 480, 45, 0);
    draw_rectangle(0, 315, 480, 360, 0);
    current_color = color;
    current_alpha = alpha;
    Value y = {45,0,0};
    Value *centered[6] = {args[0],args[1],args[2],&y,args[4],args[5]};
    return draw_hologram(self, other, result, 6, centered);
}
