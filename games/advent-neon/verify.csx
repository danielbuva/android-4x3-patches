using System;
using System.Linq;

// One verification ID for every patch.csx mutation. Tests require exact parity.
// VERIFIED-MUTATION: game-system.true-res
// VERIFIED-MUTATION: game-system.gui-size
// VERIFIED-MUTATION: game-system.label-y
// VERIFIED-MUTATION: mobile.gui-size
// VERIFIED-MUTATION: mobile.hide-overlay
// VERIFIED-MUTATION: camera-create.view-height
// VERIFIED-MUTATION: camera-step.viewport-height
// VERIFIED-MUTATION: camera-step.view-height
// VERIFIED-MUTATION: convert-gui-y.range
// VERIFIED-MUTATION: freeze.capture-height
// VERIFIED-MUTATION: freeze.camera-height
// VERIFIED-MUTATION: video.window-height
// VERIFIED-MUTATION: video.window-size
// VERIFIED-MUTATION: compositor.threshold
// VERIFIED-MUTATION: compositor.width
// VERIFIED-MUTATION: compositor.height
// VERIFIED-MUTATION: splash.center-y
// VERIFIED-MUTATION: cutscene.backdrop
// VERIFIED-MUTATION: cutscene.shadow-y
// VERIFIED-MUTATION: cutscene.splash-y
// VERIFIED-MUTATION: cutscene.skip-y
// VERIFIED-MUTATION: level-intro.bottom-y
// VERIFIED-MUTATION: fade.height
// VERIFIED-MUTATION: flash.width
// VERIFIED-MUTATION: flash.height
// VERIFIED-MUTATION: flash.rectangle
// VERIFIED-MUTATION: transitions.height
// VERIFIED-MUTATION: controller.right-x
// VERIFIED-MUTATION: controller.bottom-y
// VERIFIED-MUTATION: objective.panel
// VERIFIED-MUTATION: objective.body-y
// VERIFIED-MUTATION: objective.name-shadow-y
// VERIFIED-MUTATION: objective.name-y
// VERIFIED-MUTATION: dialogue.portrait-y
// VERIFIED-MUTATION: dialogue.panel
// VERIFIED-MUTATION: dialogue.body-y
// VERIFIED-MUTATION: dialogue.name-shadow-y
// VERIFIED-MUTATION: dialogue.name-y
// VERIFIED-MUTATION: dialogue.skip-y
// VERIFIED-MUTATION: boss.title-y
// VERIFIED-MUTATION: boss.danger-y
// VERIFIED-MUTATION: boss.overlays
// VERIFIED-MUTATION: boss.upper-lines
// VERIFIED-MUTATION: boss.lower-lines
// VERIFIED-MUTATION: boss.bottom-bar
// VERIFIED-MUTATION: boss.zig-y
// VERIFIED-MUTATION: boss.portrait-y
// VERIFIED-MUTATION: speed.vertical-span
// VERIFIED-MUTATION: speed.horizontal-bands
// VERIFIED-MUTATION: player.wind-range
// VERIFIED-MUTATION: player.wind-span
// VERIFIED-MUTATION: training.extents
// VERIFIED-MUTATION: training.preview-y
// VERIFIED-MUTATION: level-stats.heights
// VERIFIED-MUTATION: stage-clear-1.height
// VERIFIED-MUTATION: stage-clear-2-3.heights
// VERIFIED-MUTATION: warning.foreground-center
// VERIFIED-MUTATION: warning.top-text-center
// VERIFIED-MUTATION: warning.bottom-text-center

EnsureDataLoaded();

void Require(bool condition, string message)
{
    if (!condition)
        throw new InvalidOperationException("Advent Neon 4:3 verification failed: " + message);
}

int Occurrences(string value, string needle)
{
    int count = 0;
    int offset = 0;
    while ((offset = value.IndexOf(needle, offset, StringComparison.Ordinal)) >= 0)
    {
        count++;
        offset += needle.Length;
    }
    return count;
}

void RequireCode(string name, string fragment, int expected = 1)
{
    Require(Data.Code.ByName(name) != null, "missing code " + name);
    Require(Occurrences(GetDecompiledText(name), fragment) == expected,
            name + " does not contain " + expected + " expected patched anchor(s)");
}

Require(Data.GeneralInfo.Name.Content == "AdventNEON", "unexpected project name");
Require(Data.GeneralInfo.BytecodeVersion == 17, "unexpected bytecode version");
Require(Data.GeneralInfo.DefaultWindowWidth == 1280 &&
        Data.GeneralInfo.DefaultWindowHeight == 960,
        "4:3 default runner surface missing");

var controlsRoom = Data.Rooms.ByName("controls");
Require(controlsRoom != null, "missing controls title room");
foreach (var expected in new[]
{
    new { Id = 100013u, Y = 744, Code = "gml_RoomCC_controls_0_Create" },
    new { Id = 100014u, Y = 152, Code = "gml_RoomCC_controls_1_Create" },
    new { Id = 100015u, Y = 264, Code = "gml_RoomCC_controls_2_Create" },
})
    Require(controlsRoom.GameObjects.Count(instance =>
        instance.InstanceID == expected.Id &&
        instance.ObjectDefinition != null &&
        instance.ObjectDefinition.Name.Content == "oText" &&
        instance.CreationCode != null &&
        instance.CreationCode.Name.Content == expected.Code &&
        instance.X == 640 && instance.Y == expected.Y) == 1,
        "controls guide 4:3 placement changed");

var startRoom = Data.Rooms.ByName("start");
Require(startRoom != null, "missing start title room");
var startLayout = new[]
{
    new { Id = 100023u, Name = "oPlayer", X = 96, Y = 348 },
    new { Id = 100027u, Name = "oWind", X = 640, Y = 380 },
    new { Id = 100024u, Name = "oText", X = 320, Y = 220 },
    new { Id = 100026u, Name = "fxSpeedLines", X = 320, Y = 284 },
    new { Id = 100018u, Name = "oEnemyLogo", X = 320, Y = 156 },
    new { Id = 100019u, Name = "oEnemyPressStart", X = 320, Y = 268 },
    new { Id = 100020u, Name = "oEnemyCopyright", X = 32, Y = 412 },
};
foreach (var expected in startLayout)
    Require(startRoom.GameObjects.Count(instance =>
        instance.InstanceID == expected.Id &&
        instance.ObjectDefinition != null &&
        instance.ObjectDefinition.Name.Content == expected.Name &&
        instance.X == expected.X && instance.Y == expected.Y) == 1,
        "title-scene 4:3 placement changed");
foreach (var expected in new[]
{
    new { Id = 100028u, Name = "o_wall", X = 1056, Y = 448 },
    new { Id = 100029u, Name = "o_wall", X = 992, Y = 0 },
    new { Id = 100025u, Name = "oCamera", X = 320, Y = 180 },
    new { Id = 100017u, Name = "oStartSplash", X = 608, Y = 352 },
})
    Require(startRoom.GameObjects.Count(instance =>
        instance.InstanceID == expected.Id &&
        instance.ObjectDefinition != null &&
        instance.ObjectDefinition.Name.Content == expected.Name &&
        instance.X == expected.X && instance.Y == expected.Y) == 1,
        "fixed title-scene 4:3 layout changed");

int enabledViews = 0;
foreach (var room in Data.Rooms)
{
    for (int index = 0; index < room.Views.Count; index++)
    {
        var view = room.Views[index];
        if (!view.Enabled)
            continue;
        enabledViews++;
        Require(view.ViewX == 0 && view.ViewY == -120 &&
                view.ViewWidth == 1280 && view.ViewHeight == 960 &&
                view.PortX == 0 && view.PortY == 0 &&
                view.PortWidth == 1280 && view.PortHeight == 960,
                "enabled 4:3 view changed in " + room.Name.Content);
    }
}
Require(enabledViews == 66, "unexpected enabled-view count");

RequireCode("gml_Object_game_system_Create_0", "trueResH = 960;");
RequireCode("gml_Object_game_system_Create_0", "display_set_gui_size(1280, 960);");
RequireCode("gml_Object_game_system_Create_0", "y = 928;");
RequireCode("gml_Object_obj_mobilecontrols_Create_0",
            "display_set_gui_size(1280, 960);");
RequireCode("gml_Object_obj_mobilecontrols_Draw_64", "exit;");
Require(Occurrences(GetDecompiledText("gml_Object_obj_mobilecontrols_Draw_64"),
                    "draw_sprite_ext(") == 0,
        "touch-control overlay draw calls remain");
RequireCode("gml_Object_oCamera_Create_0", "viewHeight = 960;");
RequireCode("gml_Object_oCamera_Step_0",
            "room_set_viewport(room, 0, true, 0, 0, 1280, 960);");
RequireCode("gml_Object_oCamera_Step_0", "viewHeight = 960;");
RequireCode("gml_GlobalScript_ConvertToGUI_Y",
            "var nY = lerp(0, 960, (yy - viewY) / viewH);");

foreach (string name in new[]
{
    "gml_GlobalScript_timeFreeze", "gml_GlobalScript_pauseGame"
})
{
    RequireCode(name,
        "sprite_create_from_surface(application_surface, 0, 0, 1280, 960, false, false, 0, 0)");
    RequireCode(name,
        "camera_set_view_size(oCamera.cam, 1280 * camZoom, 960 * camZoom);");
}

RequireCode("gml_GlobalScript_changeVolume", "global.window_h = 960;");
RequireCode("gml_GlobalScript_changeVolume", "window_set_size(1280, 960);");
RequireCode("gml_Object_game_system_Draw_77",
            "if (aspec >= (4/3))");
RequireCode("gml_Object_game_system_Draw_77",
            "wid = hei * (4/3);");
RequireCode("gml_Object_game_system_Draw_77", "hei = wid * 0.75;");

foreach (string name in new[]
{
    "gml_Object_oMenu_Create_0", "gml_Object_oMenuPaged_Create_0"
})
{
    RequireCode(name, "gui_width = display_get_gui_width();");
    RequireCode(name, "gui_height = display_get_gui_height();");
    RequireCode(name, "menu_y = gui_height - gui_margin;");
}

RequireCode("gml_Object_oStartSplash_Draw_64", "var yy = 480;");
RequireCode("gml_Object_oTakeABreak_Draw_64", "y = 480;");
RequireCode("gml_Object_oTakeABreak_Draw_64", "bgFlavorTopY + 120", 2);
RequireCode("gml_Object_oTakeABreak_Draw_64", "bgFlavorBotY + 120", 2);
RequireCode("gml_Object_game_cutscene_Draw_64",
            "draw_rectangle_color(0, 0, 1280, 960, c, c, c, c, false);");
RequireCode("gml_Object_game_cutscene_Draw_64",
            "draw_sprite_ext(splashSprite, 0, 640, 500");
RequireCode("gml_Object_game_cutscene_Draw_64",
            "draw_sprite_ext(splashSprite, 0, 640, 480");
RequireCode("gml_Object_game_cutscene_Draw_64", "var oY = 944;");
RequireCode("gml_Object_oLevelIntro_Draw_64", "var botTY = 960 - vertBuffer;");

RequireCode("gml_Object_fxScreenFade_Draw_64",
            "draw_sprite_ext_alpha(794, 0, 0, 0, 1280, 960");
RequireCode("gml_Object_fxScreenFlash_Draw_64",
            "var wid = display_get_gui_width();");
RequireCode("gml_Object_fxScreenFlash_Draw_64",
            "var hei = display_get_gui_height();");
RequireCode("gml_Object_fxScreenFlash_Draw_64",
            "draw_rectangle_color(0, 0, wid, hei,");
foreach (string name in new[]
{
    "gml_Object_oTrans_Draw_64", "gml_Object_oTransFake_Draw_64"
})
    RequireCode(name,
        "draw_rectangle_color(0, 0, 1280, 960, c, c, c, c, false);", 2);

RequireCode("gml_Object_oControllerGuide_Draw_64",
            "x = display_get_gui_width() - (((sprite_get_width(sprite_index) / 2) * scale) + 32);");
RequireCode("gml_Object_oControllerGuide_Draw_64",
            "y = display_get_gui_height() - (((sprite_get_height(sprite_index) / 2) * scale) + 32);");
RequireCode("gml_Object_oObjective_Draw_64",
            "draw_rectangle(1280, 960, 1280 - ((1280 - boxEdge) * animProgress), 864, false);");
RequireCode("gml_Object_oObjective_Draw_64",
            "draw_text(boxEdge + textBuffer, 896, currentText);");
RequireCode("gml_Object_oObjective_Draw_64",
            "draw_text(boxEdge + textBuffer, (864 - font_get_size(fMenu2)) + 5, charName);");
RequireCode("gml_Object_oObjective_Draw_64",
            "draw_text(boxEdge + textBuffer, 864 - font_get_size(fMenu2), charName);");
RequireCode("gml_Object_oDialogue_Draw_64",
            "sprite_get_width(charSprite) * 0.5)), 864, 0.82,");
RequireCode("gml_Object_oDialogue_Draw_64",
            "draw_rectangle(1280, 960, 1280 - ((1280 - boxEdge) * animProgress), 864, false);");
RequireCode("gml_Object_oDialogue_Draw_64",
            "draw_text(boxEdge + textBuffer, 896, currentText);");
RequireCode("gml_Object_oDialogue_Draw_64",
            "draw_text(boxEdge + textBuffer, (864 - font_get_size(fMenu2)) + 5, charName);");
RequireCode("gml_Object_oDialogue_Draw_64",
            "draw_text(boxEdge + textBuffer, 864 - font_get_size(fMenu2), charName);");
RequireCode("gml_Object_oDialogue_Draw_64", "draw_text(1248, 874.56, \"[hold] SKIP\");");

RequireCode("gml_Object_oBossIntro_Create_0", "bgTitleY = 816;");
RequireCode("gml_Object_oBossIntro_Create_0", "bgDangerY = 480;");
RequireCode("gml_Object_oBossIntro_Draw_64",
            "draw_rectangle_color(0, 0, 1280, 960, c, c, c, c, false);", 2);
RequireCode("gml_Object_oBossIntro_Draw_64", "irandom_range(1, 15)");
RequireCode("gml_Object_oBossIntro_Draw_64",
            "draw_rectangle_color(0, 960, 1280, 960 - barWidth");
RequireCode("gml_Object_oBossIntro_Draw_64", "irandom_range(16, 30)");
RequireCode("gml_Object_oBossIntro_Draw_64", "bgZigXBot, 960 - barWidth,");
RequireCode("gml_Object_oBossIntro_Draw_64", "bgPortraitSprite, 0, 640, 960,");

RequireCode("gml_Object_fxSpeedLines_Draw_64",
            ", 0, 960, irandom_range(1, 4), 270,");
RequireCode("gml_Object_fxSpeedLines_Draw_64",
            "choose(irandom_range(0, 288), irandom_range(672, 960))");
RequireCode("gml_Object_oPlayer_Draw_64", "irandom_range(0, 960)");
RequireCode("gml_Object_oPlayer_Draw_64",
            ", 0, 960, irandom_range(1, 4), 270,");
RequireCode("gml_GlobalScript_drawMenuTraining", "960", 4);
RequireCode("gml_GlobalScript_drawMenuTraining", "var yy = 480;");
RequireCode("gml_GlobalScript_drawLevelStats", "var rectHeight = 960;", 6);
RequireCode("gml_GlobalScript_drawStageClear1",
            "draw_rectangle_color(0, 0, 1280, 960");
RequireCode("gml_GlobalScript_drawStageClear2", "960", 2);
RequireCode("gml_GlobalScript_drawStageClear3", "960", 3);

ScriptMessage("Advent Neon experimental 4:3 targets verified.");
