using System;
using System.Linq;

EnsureDataLoaded();

void Require(bool condition, string message)
{
    if (!condition)
        throw new InvalidOperationException("Advent Neon original-state check failed: " + message);
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
            name + " does not contain " + expected + " expected source anchor(s)");
}

Require(Data.GeneralInfo.Name.Content == "AdventNEON", "unexpected project name");
Require(Data.GeneralInfo.BytecodeVersion == 17, "unexpected bytecode version");
Require(Data.GeneralInfo.DefaultWindowWidth == 1280 &&
        Data.GeneralInfo.DefaultWindowHeight == 720,
        "unexpected default runner surface");
Require(Data.Rooms.Count == 86, "unexpected room count");

int enabledViews = 0;
foreach (var room in Data.Rooms)
{
    for (int index = 0; index < room.Views.Count; index++)
    {
        var view = room.Views[index];
        if (!view.Enabled)
            continue;
        enabledViews++;
        Require(view.ViewX == 0 && view.ViewY == 0 &&
                view.ViewWidth == 1280 && view.ViewHeight == 720 &&
                view.PortX == 0 && view.PortY == 0 &&
                view.PortWidth == 1280 && view.PortHeight == 720,
                "enabled view geometry changed in " + room.Name.Content);
    }
}
Require(enabledViews == 66, "unexpected enabled-view count");

foreach (string name in new[]
{
    "game_system", "oCamera", "oMenu", "oMenuPaged", "oStartSplash",
    "game_cutscene", "oLevelIntro", "obj_mobilecontrols", "oTrans",
    "oTransFake", "oBossIntro"
})
    Require(Data.GameObjects.ByName(name) != null, "missing object " + name);

RequireCode("gml_Object_game_system_Create_0", "trueResH = 720;");
RequireCode("gml_Object_game_system_Create_0", "display_set_gui_size(1280, 720);");
RequireCode("gml_Object_game_system_Create_0", "y = 688;");
RequireCode("gml_Object_obj_mobilecontrols_Create_0",
            "display_set_gui_size(1280, 720);");
RequireCode("gml_Object_oCamera_Create_0", "viewHeight = 720;");
RequireCode("gml_Object_oCamera_Step_0",
            "room_set_viewport(room, 0, true, 0, 0, 1280, 720);");
RequireCode("gml_Object_oCamera_Step_0", "viewHeight = 720;");
RequireCode("gml_GlobalScript_ConvertToGUI_Y",
            "var nY = lerp(0, 720, (yy - viewY) / viewH);");

foreach (string name in new[]
{
    "gml_GlobalScript_timeFreeze", "gml_GlobalScript_pauseGame"
})
{
    RequireCode(name,
        "sprite_create_from_surface(application_surface, 0, 0, 1280, 720, false, false, 0, 0)");
    RequireCode(name,
        "camera_set_view_size(oCamera.cam, 1280 * camZoom, 720 * camZoom);");
}

RequireCode("gml_GlobalScript_changeVolume", "global.window_h = 720;");
RequireCode("gml_GlobalScript_changeVolume", "window_set_size(1280, 720);");
RequireCode("gml_Object_game_system_Draw_77",
            "if (aspec >= 1.7777777777777777)");
RequireCode("gml_Object_game_system_Draw_77",
            "wid = hei * 1.7777777777777777;");
RequireCode("gml_Object_game_system_Draw_77", "hei = wid * 0.5625;");

// The menus already follow the live GUI size; guard that semantic behavior.
foreach (string name in new[]
{
    "gml_Object_oMenu_Create_0", "gml_Object_oMenuPaged_Create_0"
})
{
    RequireCode(name, "gui_width = display_get_gui_width();");
    RequireCode(name, "gui_height = display_get_gui_height();");
    RequireCode(name, "menu_y = gui_height - gui_margin;");
}

RequireCode("gml_Object_oStartSplash_Draw_64", "var yy = 360;");
RequireCode("gml_Object_game_cutscene_Draw_64",
            "draw_rectangle_color(0, 0, 1280, 720, c, c, c, c, false);");
RequireCode("gml_Object_game_cutscene_Draw_64",
            "draw_sprite_ext(splashSprite, 0, 640, 360");
RequireCode("gml_Object_game_cutscene_Draw_64", "var oY = 704;");
RequireCode("gml_Object_oLevelIntro_Draw_64", "var botTY = 720 - vertBuffer;");

RequireCode("gml_Object_fxScreenFade_Draw_64",
            "draw_sprite_ext_alpha(794, 0, 0, 0, 1280, 720");
RequireCode("gml_Object_fxScreenFlash_Draw_64", "var wid = 857.6;");
RequireCode("gml_Object_fxScreenFlash_Draw_64",
            "draw_rectangle_color(640 - wid, 360 - hei, 640 + wid, 360 + hei");
foreach (string name in new[]
{
    "gml_Object_oTrans_Draw_64", "gml_Object_oTransFake_Draw_64"
})
    RequireCode(name,
        "draw_rectangle_color(0, 0, 1280, 720, c, c, c, c, false);", 2);

RequireCode("gml_Object_oControllerGuide_Draw_64",
            "y = 720 - (((sprite_get_height(sprite_index) / 2) * scale) + 32);");
RequireCode("gml_Object_oObjective_Draw_64",
            "draw_rectangle(1280, 720, 1280 - ((1280 - boxEdge) * animProgress), 624, false);");
RequireCode("gml_Object_oDialogue_Draw_64",
            "draw_rectangle(1280, 720, 1280 - ((1280 - boxEdge) * animProgress), 624, false);");

RequireCode("gml_Object_oBossIntro_Create_0", "bgTitleY = 576;");
RequireCode("gml_Object_oBossIntro_Create_0", "bgDangerY = 360;");
RequireCode("gml_Object_oBossIntro_Draw_64",
            "draw_rectangle_color(0, 0, 1280, 720, c, c, c, c, false);", 2);
RequireCode("gml_Object_oBossIntro_Draw_64",
            "draw_rectangle_color(0, 720, 1280, 720 - barWidth");

RequireCode("gml_GlobalScript_drawMenuTraining", "720", 4);
RequireCode("gml_GlobalScript_drawMenuTraining", "var yy = 360;");
RequireCode("gml_GlobalScript_drawLevelStats", "var rectHeight = 720;", 6);
RequireCode("gml_GlobalScript_drawStageClear1",
            "draw_rectangle_color(0, 0, 1280, 720");
RequireCode("gml_GlobalScript_drawStageClear2", "720", 2);
RequireCode("gml_GlobalScript_drawStageClear3", "720", 3);

ScriptMessage("Advent Neon original 4:3 targets recognized.");
