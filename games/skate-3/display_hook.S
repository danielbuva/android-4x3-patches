/* Own ARM64 trampoline. Original live registers are retained across the classifier.
 * display-hook.json links only the labeled external branch/data references. */
.text
.global display_hook
display_hook:
 cbnz x26, classify
 cbz w8, normal
 b classify
cover:
 str q2, [sp, #-16]!
 fmov s2, #1.0
 fdiv s2, s2, s1
 add x9, sp, #0x910
 ldr q0, [x9, #0x60]
 fmul v0.4s, v0.4s, v2.s[0]
 str q0, [x9, #0x60]
 ldr q2, [sp], #16
ea_return:
 b .
overlay:
 cbz w8, normal
classify:
 sub sp, sp, #672
 stp x0, x1, [sp, #0]
 stp x2, x3, [sp, #16]
 stp x4, x5, [sp, #32]
 stp x6, x7, [sp, #48]
 stp x8, x9, [sp, #64]
 stp x10, x11, [sp, #80]
 stp x12, x13, [sp, #96]
 stp x14, x15, [sp, #112]
 stp x16, x17, [sp, #128]
 stp x18, x30, [sp, #144]
 stp q0, q1, [sp, #160]
 stp q2, q3, [sp, #192]
 stp q4, q5, [sp, #224]
 stp q6, q7, [sp, #256]
 stp q8, q9, [sp, #288]
 stp q10, q11, [sp, #320]
 stp q12, q13, [sp, #352]
 stp q14, q15, [sp, #384]
 stp q16, q17, [sp, #416]
 stp q18, q19, [sp, #448]
 stp q20, q21, [sp, #480]
 stp q22, q23, [sp, #512]
 stp q24, q25, [sp, #544]
 stp q26, q27, [sp, #576]
 stp q28, q29, [sp, #608]
 stp q30, q31, [sp, #640]
 mov x0, x22
class_title_page:
 adrp x9, 0
class_title_load:
 ldrh w1, [x9, #0]
class_screen_page:
 adrp x9, 0
class_screen_load:
 ldr w2, [x9, #0]
class_warmup_page:
 adrp x9, 0
class_warmup_load:
 ldrb w3, [x9, #0]
class_menu_page:
 adrp x9, 0
class_menu_load:
 ldrb w4, [x9, #0]
 cmp x26, #0
 cset w5, ne
scene_begin_load:
 ldr x6, [sp, #0]
scene_end_load:
 ldr x7, [sp, #0]
classifier_call:
 bl .
 str w0, [sp, #72]
 ldp x0, x1, [sp, #0]
 ldp x2, x3, [sp, #16]
 ldp x4, x5, [sp, #32]
 ldp x6, x7, [sp, #48]
 ldp x8, x9, [sp, #64]
 ldp x10, x11, [sp, #80]
 ldp x12, x13, [sp, #96]
 ldp x14, x15, [sp, #112]
 ldp x16, x17, [sp, #128]
 ldp x18, x30, [sp, #144]
 ldp q0, q1, [sp, #160]
 ldp q2, q3, [sp, #192]
 ldp q4, q5, [sp, #224]
 ldp q6, q7, [sp, #256]
 ldp q8, q9, [sp, #288]
 ldp q10, q11, [sp, #320]
 ldp q12, q13, [sp, #352]
 ldp q14, q15, [sp, #384]
 ldp q16, q17, [sp, #416]
 ldp q18, q19, [sp, #448]
 ldp q20, q21, [sp, #480]
 ldp q22, q23, [sp, #512]
 ldp q24, q25, [sp, #544]
 ldp q26, q27, [sp, #576]
 ldp q28, q29, [sp, #608]
 ldp q30, q31, [sp, #640]
 add sp, sp, #672
 cmp w9, #1
 b.eq overlay_return
 cmp w9, #2
 b.eq cover
 cmp w9, #3
 b.eq title_top
 cmp w9, #4
 b.eq loading_bottom
 cmp w9, #5
 b.eq startup_dialog
normal:
 add x9, sp, #0x900
 ldr q0, [x9, #0x70]
 fmul v0.4s, v0.4s, v1.s[0]
 str q0, [x9, #0x70]
normal_return:
 b .
overlay_return:
 b .
title_top:
 add x9, sp, #0x900
 ldr q0, [x9, #0x70]
 fmul v0.4s, v0.4s, v1.s[0]
 str q0, [x9, #0x70]
 str q2, [sp, #-16]!
 fmov s2, #0.25
 ldr s0, [x9, #0x7c]
 fadd s0, s0, s2
 str s0, [x9, #0x7c]
 ldr q2, [sp], #16
 b overlay_return
loading_bottom:
 add x9, sp, #0x900
 ldr q0, [x9, #0x70]
 fmul v0.4s, v0.4s, v1.s[0]
 str q0, [x9, #0x70]
 str q2, [sp, #-16]!
 fmov s2, #0.25
 ldr s0, [x9, #0x7c]
 fsub s0, s0, s2
 str s0, [x9, #0x7c]
 ldr q2, [sp], #16
 b overlay_return

startup_dialog:
 add x9, sp, #0x900
 str q2, [sp, #-16]!
 fmov s2, #1.5
 ldr q0, [x9, #0x60]
 fmul v0.4s, v0.4s, v2.s[0]
 str q0, [x9, #0x60]
 ldr q0, [x9, #0x70]
 fmul v0.4s, v0.4s, v1.s[0]
 fmul v0.4s, v0.4s, v2.s[0]
 str q0, [x9, #0x70]
 ldr q2, [sp], #16
 b overlay_return
