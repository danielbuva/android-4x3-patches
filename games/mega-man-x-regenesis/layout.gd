
# android4x3_regenesis_layout_v2
# Attached to the existing ShaderWarmup autoload; original warmup stays intact.
func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	get_tree().node_added.connect(_a4x3_added)
	_a4x3_walk.call_deferred(get_tree().root)

func _a4x3_added(node: Node) -> void:
	_a4x3_layout.call_deferred(node)

func _a4x3_walk(node: Node) -> void:
	_a4x3_layout(node)
	for child in node.get_children():
		_a4x3_walk(child)

func _a4x3_layout(node: Node) -> void:
	if not is_instance_valid(node) or node.has_meta("android4x3_layout"):
		return
	node.set_meta("android4x3_layout", true)
	var parent = node.get_parent()
	var owner_scene = ""
	if parent != null:
		owner_scene = parent.scene_file_path.get_file()
	if node is CanvasLayer:
		if owner_scene in ["health_bar.tscn", "weapon_bar.tscn", "health_bar_ride_armor.tscn"]:
			node.scale = Vector2(1.25, 1.25)
		elif owner_scene == "health_bar_boss.tscn":
			node.scale = Vector2(1.25, 1.25)
			node.offset = Vector2(-96, 0)
		elif owner_scene == "pause_menu.tscn":
			node.scale = Vector2(1.1, 1.1)
			node.offset = Vector2(-19.2, 25.2)
		elif node.scene_file_path.get_file() in ["dialog.tscn", "warning_label.tscn"]:
			node.offset.y += 36
		elif owner_scene == "speedrun_timer.tscn":
			node.offset.y += 36
	# Standalone menus have no Camera2D: transform their original screen frame.
	if node is Node2D and parent == get_tree().root and node.scene_file_path.get_file() in ["game_save_slots_menu.tscn", "options_menu.tscn", "input_menu.tscn", "achievements_menu.tscn", "touch_remap_menu.tscn"]:
		node.position = Vector2(192, 144) + (node.position - Vector2(192, 108)) * 1.15
		node.scale *= Vector2(1.15, 1.15)
	if node is Node2D and parent == get_tree().root and node.scene_file_path.get_file() == "options_menu.tscn":
		_a4x3_options.call_deferred(node)
	if node is Node2D and node.name == "MenuPlayer" and owner_scene == "main_menu.tscn":
		node.scale *= Vector2(1.2, 1.2)
	if node is Label and parent != null and parent.name == "Text":
		var menu = parent.get_parent()
		if menu != null and menu.scene_file_path.get_file() in ["options_menu.tscn", "input_menu.tscn"]:
			node.pivot_offset = node.size * 0.5
			node.scale *= Vector2(1.12, 1.12)
	# Transition overlays must cover all 288 rows, including while paused.
	if node is ColorRect and parent != null and parent.scene_file_path.get_file() == "transition_screen.tscn":
		node.position = Vector2.ZERO
		node.size = Vector2(384, 288)

# Preserve the original nodes, scripts, selection logic and artwork. Only layout
# changes; text/value columns have an explicit gap and no clipped parent panel.
func _a4x3_options(menu: Node2D) -> void:
	if not is_instance_valid(menu):
		return
	menu.position = Vector2.ZERO
	menu.scale = Vector2.ONE
	var panel = menu.get_node("Text")
	panel.position = Vector2.ZERO
	panel.size = Vector2(384, 288)
	panel.clip_contents = false
	var background = menu.get_node("BlackBackground")
	background.position = Vector2.ZERO
	background.size = Vector2(384, 288)
	var title = menu.get_node("Title")
	title.position = Vector2(192, 26)
	title.scale = Vector2(1.15, 1.15)
	var rows = ["InputConfig", "TouchControls", "Music", "Sfx", "Particles", "Lighting", "Haptic", "Speedrun", "DoubleTapDash", "Weapon", "Language", "Reset", "ResetAch", "Exit"]
	for index in range(rows.size()):
		var label = panel.get_node(rows[index])
		var width = 236.0
		if rows[index] in ["InputConfig", "TouchControls", "ResetAch", "Exit"]:
			width = 340.0
		_a4x3_label(label, Vector2(22, 50 + index * 16.5), width)
	_a4x3_label(panel.get_node("LanguageSet"), Vector2(272, 215), 90.0)
	_a4x3_label(panel.get_node("ResetSlot"), Vector2(272, 231.5), 90.0)
	var checks = {"particles": 4, "lighting": 5, "haptic": 6, "speedrun": 7, "doubleTap": 8, "weapon": 9}
	for prefix in checks:
		for suffix in ["Blue", "Gold", "CheckedBlue", "CheckedGold"]:
			var box = menu.get_node(prefix + "Checkbox" + suffix)
			box.position = Vector2(280, 59 + checks[prefix] * 16.5)
			box.scale = Vector2(1.25, 1.25)
	for bar_name in ["VolumeBlue", "VolumeGold", "VolumeBlue2", "VolumeGold2"]:
		var bar = menu.get_node(bar_name)
		var texture = bar.sprite_frames.get_frame_texture(bar.animation, bar.frame)
		var factor = min(0.625, 90.0 / texture.get_width())
		bar.scale = Vector2(factor, factor)
		var row = 3 if bar_name.ends_with("2") else 2
		bar.position = Vector2(272 + texture.get_width() * factor * 0.5, 59 + row * 16.5)

func _a4x3_label(label: Label, point: Vector2, width: float) -> void:
	label.pivot_offset = Vector2.ZERO
	label.position = point
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_LEFT
	label.clip_text = false
	_a4x3_fit_label(label, width)
	label.minimum_size_changed.connect(_a4x3_fit_label.bind(label, width))

func _a4x3_fit_label(label: Label, width: float) -> void:
	if not is_instance_valid(label):
		return
	var font = label.get_theme_font("font")
	var text_width = font.get_string_size(label.text, HORIZONTAL_ALIGNMENT_LEFT, -1, label.get_theme_font_size("font_size")).x
	var factor = min(1.25, width / max(text_width, 1.0))
	label.scale = Vector2(factor, factor)
	label.size = Vector2(width / factor, 12.0 / factor)
