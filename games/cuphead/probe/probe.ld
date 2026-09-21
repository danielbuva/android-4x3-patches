ENTRY(camera_probe)
original_rect = 0xa0fc48;
get_camera = 0xa0f83c;
get_bounds = 0xa0f8dc;
get_rect = 0x17cb100;
set_rect = 0x17cb1a0;
reset_projection = 0x17cb784;
get_projection = 0x17cb550;
set_projection = 0x17cb614;
get_size = 0x17cad28;
get_orthographic = 0x17cae08;
screen_width = 0x178c34c;
screen_height = 0x178c3a8;
frame_count = 0x1792204;
string_new = 0x1b62c38;
debug_log = 0x17bee38;
access = 0x7e8e30;
sprintf = 0x7e9810;
SECTIONS {
 . = 0x2740000;
 .probe : { *(.text*) *(.rodata*) }
 /DISCARD/ : { *(.comment) *(.note*) *(.eh_frame*) }
}
