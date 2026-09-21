.text
.global original_options_update
original_options_update:
 stp d9,d8,[sp,#-0x40]!
 b options_update_resume
.global original_visual_select
original_visual_select:
 stp x20,x19,[sp,#-0x20]!
 b visual_select_resume
