
# android4x3_regenesis_layout_v1
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
