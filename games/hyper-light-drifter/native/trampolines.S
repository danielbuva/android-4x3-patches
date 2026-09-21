.text
.global original_pad_update
original_pad_update:
 stp x29, x30, [sp, #-0x30]!
 b pad_update_continue
.global original_character_input
original_character_input:
 stp d11, d10, [sp, #-0x80]!
 b character_input_continue
.global original_menu_draw
original_menu_draw:
 stp d13, d12, [sp, #-0x90]!
 b menu_draw_continue
.global original_menu_step
original_menu_step:
 str d10, [sp, #-0x80]!
 b menu_step_continue

.global original_fire_light
original_fire_light:
 str d12, [sp, #-0x90]!
 b fire_light_continue
.global original_fire_rail
original_fire_rail:
 str d12, [sp, #-0x90]!
 b fire_rail_continue
.global original_fire_blast
original_fire_blast:
 stp d11, d10, [sp, #-0x80]!
 b fire_blast_continue

.global original_weapon_crystalgun
original_weapon_crystalgun:
 stp d9, d8, [sp, #-0x70]!
 b weapon_crystalgun_continue

.global original_weapon_railgunlight
original_weapon_railgunlight:
 sub sp, sp, #0x60
 b weapon_railgunlight_continue

.global original_weapon_railgunscope
original_weapon_railgunscope:
 stp d13, d12, [sp, #-0x90]!
 b weapon_railgunscope_continue

.global original_weapon_railgunzap
original_weapon_railgunzap:
 stp d13, d12, [sp, #-0x90]!
 b weapon_railgunzap_continue

.global original_weapon_railgunauto
original_weapon_railgunauto:
 stp d13, d12, [sp, #-0x90]!
 b weapon_railgunauto_continue

.global original_weapon_railgun
original_weapon_railgun:
 str d12, [sp, #-0x90]!
 b weapon_railgun_continue

.global original_weapon_railgunblast
original_weapon_railgunblast:
 str d12, [sp, #-0x90]!
 b weapon_railgunblast_continue

.global original_weapon_pistol
original_weapon_pistol:
 stp d11, d10, [sp, #-0x80]!
 b weapon_pistol_continue

.global original_weapon_pistolzeliska
original_weapon_pistolzeliska:
 stp d11, d10, [sp, #-0x80]!
 b weapon_pistolzeliska_continue

.global original_weapon_diamondblunderbuss
original_weapon_diamondblunderbuss:
 str d8, [sp, #-0x70]!
 b weapon_diamondblunderbuss_continue

.global original_weapon_diamondshotgun
original_weapon_diamondshotgun:
 stp d9, d8, [sp, #-0x70]!
 b weapon_diamondshotgun_continue

.global original_weapon_diamondcharge
original_weapon_diamondcharge:
 stp d9, d8, [sp, #-0x70]!
 b weapon_diamondcharge_continue

.global original_weapon_scuttlerpistol
original_weapon_scuttlerpistol:
 stp d11, d10, [sp, #-0x80]!
 b weapon_scuttlerpistol_continue

.global original_weapon_tracerpistol
original_weapon_tracerpistol:
 stp d11, d10, [sp, #-0x80]!
 b weapon_tracerpistol_continue

.global original_weapon_rifle
original_weapon_rifle:
 sub sp, sp, #0x60
 b weapon_rifle_continue

.global original_weapon_burstrifle
original_weapon_burstrifle:
 sub sp, sp, #0x1b0
 b weapon_burstrifle_continue

.global original_weapon_chargeshot
original_weapon_chargeshot:
 sub sp, sp, #0x60
 b weapon_chargeshot_continue

.global original_basic_movement
original_basic_movement:
 str d12, [sp, #-0x90]!
 b basic_movement_continue
