assign = 0x19b5e50;
get_builtin = 0x19b6610;
total_time_var = 0x1aa1778;
draw_hologram = 0x19b8e50;
draw_rectangle = 0xaf2b84;
draw_alpha = 0xaf2080;
draw_color = 0xaf2060;
current_color = 0x1ade870;
current_alpha = 0x1ade874;
INCLUDE symbols.ld
SECTIONS { . = 0x1e10000; .text : { *(.text.entry) *(.text.startup_hook) *(.text.background_hook) *(.text*) *(.rodata*) } .data : { *(.data*) *(.got*) } .bss : { *(.bss*) *(COMMON) } ASSERT(SIZEOF(.data) == 0, "RX payload cannot contain writable data") ASSERT(SIZEOF(.bss) == 0, "RX payload cannot contain writable counters") /DISCARD/ : { *(.comment*) *(.eh_frame*) *(.note*) } }
