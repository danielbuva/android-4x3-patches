using System;
using System.Linq;
using UndertaleModLib.Compiler;

// Experimental structural 4:3 pass for Advent Neon. Only narrowly guarded
// source anchors are retained here; no complete game routine is embedded.
//
// This manifest has one unique ID for every ReplaceOnce/ReplaceCount call.
// verify.csx carries the same IDs, and a repository regression test enforces
// parity so a new mutation cannot ship without a corresponding postcondition.
// PATCH-MUTATION: game-system.true-res
// PATCH-MUTATION: game-system.gui-size
// PATCH-MUTATION: game-system.label-y
// PATCH-MUTATION: mobile.gui-size
// PATCH-MUTATION: mobile.hide-overlay
// PATCH-MUTATION: camera-create.view-height
// PATCH-MUTATION: camera-step.viewport-height
// PATCH-MUTATION: camera-step.view-height
// PATCH-MUTATION: convert-gui-y.range
// PATCH-MUTATION: freeze.capture-height
// PATCH-MUTATION: freeze.camera-height
// PATCH-MUTATION: video.window-height
// PATCH-MUTATION: video.window-size
// PATCH-MUTATION: compositor.threshold
// PATCH-MUTATION: compositor.width
// PATCH-MUTATION: compositor.height
// PATCH-MUTATION: splash.center-y
// PATCH-MUTATION: cutscene.backdrop
// PATCH-MUTATION: cutscene.shadow-y
// PATCH-MUTATION: cutscene.splash-y
// PATCH-MUTATION: cutscene.skip-y
// PATCH-MUTATION: level-intro.bottom-y
// PATCH-MUTATION: fade.height
// PATCH-MUTATION: flash.width
// PATCH-MUTATION: flash.height
// PATCH-MUTATION: flash.rectangle
// PATCH-MUTATION: transitions.height
// PATCH-MUTATION: controller.right-x
// PATCH-MUTATION: controller.bottom-y
// PATCH-MUTATION: objective.panel
// PATCH-MUTATION: objective.body-y
// PATCH-MUTATION: objective.name-shadow-y
// PATCH-MUTATION: objective.name-y
// PATCH-MUTATION: dialogue.portrait-y
// PATCH-MUTATION: dialogue.panel
// PATCH-MUTATION: dialogue.body-y
// PATCH-MUTATION: dialogue.name-shadow-y
// PATCH-MUTATION: dialogue.name-y
// PATCH-MUTATION: dialogue.skip-y
// PATCH-MUTATION: boss.title-y
// PATCH-MUTATION: boss.danger-y
// PATCH-MUTATION: boss.overlays
// PATCH-MUTATION: boss.upper-lines
// PATCH-MUTATION: boss.lower-lines
// PATCH-MUTATION: boss.bottom-bar
// PATCH-MUTATION: boss.zig-y
// PATCH-MUTATION: boss.portrait-y
// PATCH-MUTATION: speed.vertical-span
// PATCH-MUTATION: speed.horizontal-bands
// PATCH-MUTATION: player.wind-range
// PATCH-MUTATION: player.wind-span
// PATCH-MUTATION: training.extents
// PATCH-MUTATION: training.preview-y
// PATCH-MUTATION: level-stats.heights
// PATCH-MUTATION: stage-clear-1.height
// PATCH-MUTATION: stage-clear-2-3.heights
// PATCH-MUTATION: warning.foreground-center
// PATCH-MUTATION: warning.top-text-center
// PATCH-MUTATION: warning.bottom-text-center

EnsureDataLoaded();

void Require(bool condition, string message)
{
    if (!condition)
        throw new InvalidOperationException("Advent Neon 4:3 guard failed: " + message);
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

string ReplaceCount(string source, string oldText, string newText,
                    int expected, string label)
{
    Require(Occurrences(source, oldText) == expected,
            label + " expected " + expected + " unique source anchor(s)");
    return source.Replace(oldText, newText);
}

string ReplaceOnce(string source, string oldText, string newText, string label)
    => ReplaceCount(source, oldText, newText, 1, label);

Require(Data.GeneralInfo.Name.Content == "AdventNEON", "unexpected project name");
Require(Data.GeneralInfo.BytecodeVersion == 17, "unexpected bytecode version");
Require(Data.GeneralInfo.DefaultWindowWidth == 1280 &&
        Data.GeneralInfo.DefaultWindowHeight == 720,
        "unexpected default runner surface");
Require(Data.Rooms.Count == 86, "unexpected room count");

// The controls guide was authored against a 1280x720 GUI. Move its three
// independently guarded text objects together so the guide remains centered
// on the taller canvas.
var controlsRoom = Data.Rooms.ByName("controls");
Require(controlsRoom != null, "missing controls title room");
foreach (var expected in new[]
{
    new { Id = 100013u, Y = 624, Code = "gml_RoomCC_controls_0_Create" },
    new { Id = 100014u, Y = 32, Code = "gml_RoomCC_controls_1_Create" },
    new { Id = 100015u, Y = 144, Code = "gml_RoomCC_controls_2_Create" },
})
{
    var matches = controlsRoom.GameObjects.Where(instance =>
        instance.InstanceID == expected.Id &&
        instance.ObjectDefinition != null &&
        instance.ObjectDefinition.Name.Content == "oText" &&
        instance.CreationCode != null &&
        instance.CreationCode.Name.Content == expected.Code &&
        instance.X == 640 && instance.Y == expected.Y).ToList();
    Require(matches.Count == 1, "controls guide instance is missing or ambiguous");
    matches[0].Y += 120;
}

// The title scene uses a half-resolution 640x360 playfield. Its camera and
// layered background already expose the new vertical area, but every authored
// foreground instance remained centered in the old upper 360-line region.
// Move only the visual ensemble down by 60 logical pixels; keep the collision
// walls, camera, and GUI-drawn splash object at their original guarded values.
var startRoom = Data.Rooms.ByName("start");
Require(startRoom != null, "missing start title room");
var startLayout = new[]
{
    new { Id = 100023u, Name = "oPlayer", X = 96, Y = 288 },
    new { Id = 100027u, Name = "oWind", X = 640, Y = 320 },
    new { Id = 100024u, Name = "oText", X = 320, Y = 160 },
    new { Id = 100026u, Name = "fxSpeedLines", X = 320, Y = 224 },
    new { Id = 100018u, Name = "oEnemyLogo", X = 320, Y = 96 },
    new { Id = 100019u, Name = "oEnemyPressStart", X = 320, Y = 208 },
    new { Id = 100020u, Name = "oEnemyCopyright", X = 32, Y = 352 },
};
foreach (var expected in startLayout)
{
    var matches = startRoom.GameObjects.Where(instance =>
        instance.InstanceID == expected.Id &&
        instance.ObjectDefinition != null &&
        instance.ObjectDefinition.Name.Content == expected.Name &&
        instance.X == expected.X && instance.Y == expected.Y).ToList();
    Require(matches.Count == 1, "title-scene instance is missing or ambiguous");
    matches[0].Y += 60;
}
var fixedTitleLayout = new[]
{
    new { Id = 100028u, Name = "o_wall", X = 1056, Y = 448 },
    new { Id = 100029u, Name = "o_wall", X = 992, Y = 0 },
    new { Id = 100025u, Name = "oCamera", X = 320, Y = 180 },
    new { Id = 100017u, Name = "oStartSplash", X = 608, Y = 352 },
};
foreach (var expected in fixedTitleLayout)
    Require(startRoom.GameObjects.Count(instance =>
        instance.InstanceID == expected.Id &&
        instance.ObjectDefinition != null &&
        instance.ObjectDefinition.Name.Content == expected.Name &&
        instance.X == expected.X && instance.Y == expected.Y) == 1,
        "fixed title-scene layout changed unexpectedly");

Data.GeneralInfo.DefaultWindowHeight = 960;

// Preserve the center of every enabled 1280x720 view while expanding its
// vertical span and presentation port to 1280x960.
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
        view.ViewY = -120;
        view.ViewHeight = 960;
        view.PortHeight = 960;
    }
}
Require(enabledViews == 66, "unexpected enabled-view count");

CodeImportGroup imports = new(Data);

string gameSystemCreateName = "gml_Object_game_system_Create_0";
string gameSystemCreate = GetDecompiledText(gameSystemCreateName);
gameSystemCreate = ReplaceOnce(gameSystemCreate, "trueResH = 720;",
    "trueResH = 960;", gameSystemCreateName + " true resolution");
gameSystemCreate = ReplaceOnce(gameSystemCreate,
    "display_set_gui_size(1280, 720);", "display_set_gui_size(1280, 960);",
    gameSystemCreateName + " GUI size");
gameSystemCreate = ReplaceOnce(gameSystemCreate, "y = 688;", "y = 928;",
    gameSystemCreateName + " build label bottom anchor");
imports.QueueReplace(gameSystemCreateName, gameSystemCreate);

string mobileName = "gml_Object_obj_mobilecontrols_Create_0";
string mobile = GetDecompiledText(mobileName);
mobile = ReplaceOnce(mobile, "display_set_gui_size(1280, 720);",
    "display_set_gui_size(1280, 960);", mobileName + " GUI size");
imports.QueueReplace(mobileName, mobile);

string mobileDrawName = "gml_Object_obj_mobilecontrols_Draw_64";
string mobileDraw = GetDecompiledText(mobileDrawName);
Require(Occurrences(mobileDraw, "draw_sprite_ext(spr_z_button") == 1,
        mobileDrawName + " missing Z-button overlay anchor");
Require(Occurrences(mobileDraw, "draw_sprite_ext(spr_joybase") == 1,
        mobileDrawName + " missing stick overlay anchor");
mobileDraw = ReplaceOnce(mobileDraw, mobileDraw, "exit;",
    mobileDrawName + " hide touch-control overlay");
imports.QueueReplace(mobileDrawName, mobileDraw);

string cameraCreateName = "gml_Object_oCamera_Create_0";
string cameraCreate = GetDecompiledText(cameraCreateName);
cameraCreate = ReplaceOnce(cameraCreate, "viewHeight = 720;",
    "viewHeight = 960;", cameraCreateName + " logical height");
imports.QueueReplace(cameraCreateName, cameraCreate);

string cameraStepName = "gml_Object_oCamera_Step_0";
string cameraStep = GetDecompiledText(cameraStepName);
cameraStep = ReplaceOnce(cameraStep,
    "room_set_viewport(room, 0, true, 0, 0, 1280, 720);",
    "room_set_viewport(room, 0, true, 0, 0, 1280, 960);",
    cameraStepName + " output port");
cameraStep = ReplaceOnce(cameraStep, "viewHeight = 720;", "viewHeight = 960;",
    cameraStepName + " debug reset height");
imports.QueueReplace(cameraStepName, cameraStep);

string convertYName = "gml_GlobalScript_ConvertToGUI_Y";
string convertY = GetDecompiledText(convertYName);
convertY = ReplaceOnce(convertY,
    "var nY = lerp(0, 720, (yy - viewY) / viewH);",
    "var nY = lerp(0, 960, (yy - viewY) / viewH);",
    convertYName + " logical GUI mapping");
imports.QueueReplace(convertYName, convertY);

foreach (string name in new[]
{
    "gml_GlobalScript_timeFreeze", "gml_GlobalScript_pauseGame"
})
{
    string source = GetDecompiledText(name);
    source = ReplaceOnce(source,
        "sprite_create_from_surface(application_surface, 0, 0, 1280, 720, false, false, 0, 0)",
        "sprite_create_from_surface(application_surface, 0, 0, 1280, 960, false, false, 0, 0)",
        name + " frozen-frame capture");
    source = ReplaceOnce(source,
        "camera_set_view_size(oCamera.cam, 1280 * camZoom, 720 * camZoom);",
        "camera_set_view_size(oCamera.cam, 1280 * camZoom, 960 * camZoom);",
        name + " frozen camera height");
    imports.QueueReplace(name, source);
}

string videoName = "gml_GlobalScript_changeVolume";
string video = GetDecompiledText(videoName);
video = ReplaceOnce(video, "global.window_h = 720;", "global.window_h = 960;",
    videoName + " reset height");
video = ReplaceOnce(video, "window_set_size(1280, 720);",
    "window_set_size(1280, 960);", videoName + " reset window");
imports.QueueReplace(videoName, video);

// The shader compositor otherwise fits the new application surface back into
// a centered 16:9 rectangle. Preserve aspect with a 4:3 fit instead.
string compositorName = "gml_Object_game_system_Draw_77";
string compositor = GetDecompiledText(compositorName);
compositor = ReplaceOnce(compositor, "if (aspec >= 1.7777777777777777)",
    "if (aspec >= 1.3333333333333333)", compositorName + " aspect threshold");
compositor = ReplaceOnce(compositor, "wid = hei * 1.7777777777777777;",
    "wid = hei * 1.3333333333333333;", compositorName + " fitted width");
compositor = ReplaceOnce(compositor, "hei = wid * 0.5625;",
    "hei = wid * 0.75;", compositorName + " fitted height");
imports.QueueReplace(compositorName, compositor);

string startSplashName = "gml_Object_oStartSplash_Draw_64";
string startSplash = GetDecompiledText(startSplashName);
startSplash = ReplaceOnce(startSplash, "var yy = 360;", "var yy = 480;",
    startSplashName + " vertical center");
imports.QueueReplace(startSplashName, startSplash);

// This foreground is drawn in GUI coordinates over a separately tiled room
// background. Shift only the foreground sprite and both text lines; the tiled
// background is already centered across the full 960-line frame.
string warningName = "gml_Object_oTakeABreak_Draw_64";
string warning = GetDecompiledText(warningName);
warning = ReplaceOnce(warning, "y = 360;", "y = 480;",
    warningName + " foreground center");
warning = ReplaceCount(warning, "bgFlavorTopY", "(bgFlavorTopY + 120)", 2,
    warningName + " top text center");
warning = ReplaceCount(warning, "bgFlavorBotY", "(bgFlavorBotY + 120)", 2,
    warningName + " bottom text center");
imports.QueueReplace(warningName, warning);

string cutsceneName = "gml_Object_game_cutscene_Draw_64";
string cutscene = GetDecompiledText(cutsceneName);
cutscene = ReplaceOnce(cutscene,
    "draw_rectangle_color(0, 0, 1280, 720, c, c, c, c, false);",
    "draw_rectangle_color(0, 0, 1280, 960, c, c, c, c, false);",
    cutsceneName + " splash backdrop");
cutscene = ReplaceOnce(cutscene,
    "draw_sprite_ext(splashSprite, 0, 640, 380,",
    "draw_sprite_ext(splashSprite, 0, 640, 500,",
    cutsceneName + " mini splash shadow");
cutscene = ReplaceOnce(cutscene,
    "draw_sprite_ext(splashSprite, 0, 640, 360,",
    "draw_sprite_ext(splashSprite, 0, 640, 480,",
    cutsceneName + " splash center");
cutscene = ReplaceOnce(cutscene, "var oY = 704;", "var oY = 944;",
    cutsceneName + " skip prompt bottom anchor");
imports.QueueReplace(cutsceneName, cutscene);

string introName = "gml_Object_oLevelIntro_Draw_64";
string intro = GetDecompiledText(introName);
intro = ReplaceOnce(intro, "var botTY = 720 - vertBuffer;",
    "var botTY = 960 - vertBuffer;", introName + " lower text edge");
imports.QueueReplace(introName, intro);

string fadeName = "gml_Object_fxScreenFade_Draw_64";
string fade = GetDecompiledText(fadeName);
fade = ReplaceOnce(fade,
    "draw_sprite_ext_alpha(794, 0, 0, 0, 1280, 720,",
    "draw_sprite_ext_alpha(794, 0, 0, 0, 1280, 960,",
    fadeName + " full-screen coverage");
imports.QueueReplace(fadeName, fade);

string flashName = "gml_Object_fxScreenFlash_Draw_64";
string flash = GetDecompiledText(flashName);
flash = ReplaceOnce(flash, "var wid = 857.6;",
    "var wid = display_get_gui_width();", flashName + " width");
flash = ReplaceOnce(flash, "var hei = 482.40000000000003;",
    "var hei = display_get_gui_height();", flashName + " height");
flash = ReplaceOnce(flash,
    "draw_rectangle_color(640 - wid, 360 - hei, 640 + wid, 360 + hei,",
    "draw_rectangle_color(0, 0, wid, hei,", flashName + " rectangle");
imports.QueueReplace(flashName, flash);

foreach (string name in new[]
{
    "gml_Object_oTrans_Draw_64", "gml_Object_oTransFake_Draw_64"
})
{
    string source = GetDecompiledText(name);
    source = ReplaceCount(source,
        "draw_rectangle_color(0, 0, 1280, 720, c, c, c, c, false);",
        "draw_rectangle_color(0, 0, 1280, 960, c, c, c, c, false);",
        2, name + " fade coverage");
    imports.QueueReplace(name, source);
}

string controllerName = "gml_Object_oControllerGuide_Draw_64";
string controller = GetDecompiledText(controllerName);
controller = ReplaceOnce(controller,
    "x = 1280 - (((sprite_get_width(sprite_index) / 2) * scale) + 32);",
    "x = display_get_gui_width() - (((sprite_get_width(sprite_index) / 2) * scale) + 32);",
    controllerName + " right anchor");
controller = ReplaceOnce(controller,
    "y = 720 - (((sprite_get_height(sprite_index) / 2) * scale) + 32);",
    "y = display_get_gui_height() - (((sprite_get_height(sprite_index) / 2) * scale) + 32);",
    controllerName + " bottom anchor");
imports.QueueReplace(controllerName, controller);

string objectiveName = "gml_Object_oObjective_Draw_64";
string objective = GetDecompiledText(objectiveName);
objective = ReplaceOnce(objective,
    "draw_rectangle(1280, 720, 1280 - ((1280 - boxEdge) * animProgress), 624, false);",
    "draw_rectangle(1280, 960, 1280 - ((1280 - boxEdge) * animProgress), 864, false);",
    objectiveName + " panel");
objective = ReplaceOnce(objective, "draw_text(boxEdge + textBuffer, 656, currentText);",
    "draw_text(boxEdge + textBuffer, 896, currentText);", objectiveName + " body");
objective = ReplaceOnce(objective,
    "draw_text(boxEdge + textBuffer, (624 - font_get_size(fMenu2)) + 5, charName);",
    "draw_text(boxEdge + textBuffer, (864 - font_get_size(fMenu2)) + 5, charName);",
    objectiveName + " name shadow");
objective = ReplaceOnce(objective,
    "draw_text(boxEdge + textBuffer, 624 - font_get_size(fMenu2), charName);",
    "draw_text(boxEdge + textBuffer, 864 - font_get_size(fMenu2), charName);",
    objectiveName + " name");
imports.QueueReplace(objectiveName, objective);

string dialogueName = "gml_Object_oDialogue_Draw_64";
string dialogue = GetDecompiledText(dialogueName);
dialogue = ReplaceOnce(dialogue,
    "sprite_get_width(charSprite) * 0.5)), 624, 0.82,",
    "sprite_get_width(charSprite) * 0.5)), 864, 0.82,",
    dialogueName + " portrait");
dialogue = ReplaceOnce(dialogue,
    "draw_rectangle(1280, 720, 1280 - ((1280 - boxEdge) * animProgress), 624, false);",
    "draw_rectangle(1280, 960, 1280 - ((1280 - boxEdge) * animProgress), 864, false);",
    dialogueName + " panel");
dialogue = ReplaceOnce(dialogue, "draw_text(boxEdge + textBuffer, 656, currentText);",
    "draw_text(boxEdge + textBuffer, 896, currentText);", dialogueName + " body");
dialogue = ReplaceOnce(dialogue,
    "draw_text(boxEdge + textBuffer, (624 - font_get_size(fMenu2)) + 5, charName);",
    "draw_text(boxEdge + textBuffer, (864 - font_get_size(fMenu2)) + 5, charName);",
    dialogueName + " name shadow");
dialogue = ReplaceOnce(dialogue,
    "draw_text(boxEdge + textBuffer, 624 - font_get_size(fMenu2), charName);",
    "draw_text(boxEdge + textBuffer, 864 - font_get_size(fMenu2), charName);",
    dialogueName + " name");
dialogue = ReplaceOnce(dialogue, "draw_text(1248, 634.56, \"[hold] SKIP\");",
    "draw_text(1248, 874.56, \"[hold] SKIP\");", dialogueName + " skip prompt");
imports.QueueReplace(dialogueName, dialogue);

string bossCreateName = "gml_Object_oBossIntro_Create_0";
string bossCreate = GetDecompiledText(bossCreateName);
bossCreate = ReplaceOnce(bossCreate, "bgTitleY = 576;", "bgTitleY = 816;",
    bossCreateName + " title anchor");
bossCreate = ReplaceOnce(bossCreate, "bgDangerY = 360;", "bgDangerY = 480;",
    bossCreateName + " warning center");
imports.QueueReplace(bossCreateName, bossCreate);

string bossDrawName = "gml_Object_oBossIntro_Draw_64";
string bossDraw = GetDecompiledText(bossDrawName);
bossDraw = ReplaceCount(bossDraw,
    "draw_rectangle_color(0, 0, 1280, 720, c, c, c, c, false);",
    "draw_rectangle_color(0, 0, 1280, 960, c, c, c, c, false);",
    2, bossDrawName + " overlays");
bossDraw = ReplaceOnce(bossDraw, "irandom_range(1, 11)", "irandom_range(1, 15)",
    bossDrawName + " upper speed lines");
bossDraw = ReplaceOnce(bossDraw, "irandom_range(12, 22)", "irandom_range(16, 30)",
    bossDrawName + " lower speed lines");
bossDraw = ReplaceOnce(bossDraw,
    "draw_rectangle_color(0, 720, 1280, 720 - barWidth,",
    "draw_rectangle_color(0, 960, 1280, 960 - barWidth,",
    bossDrawName + " lower black bar");
bossDraw = ReplaceOnce(bossDraw, "bgZigXBot, 720 - barWidth,",
    "bgZigXBot, 960 - barWidth,", bossDrawName + " lower zig edge");
bossDraw = ReplaceOnce(bossDraw, "bgPortraitSprite, 0, 640, 720,",
    "bgPortraitSprite, 0, 640, 960,", bossDrawName + " portrait edge");
imports.QueueReplace(bossDrawName, bossDraw);

string speedName = "gml_Object_fxSpeedLines_Draw_64";
string speed = GetDecompiledText(speedName);
speed = ReplaceOnce(speed, ", 0, 720, irandom_range(1, 4), 270,",
    ", 0, 960, irandom_range(1, 4), 270,", speedName + " vertical span");
speed = ReplaceOnce(speed,
    "choose(irandom_range(0, 216), irandom_range(503.99999999999994, 720))",
    "choose(irandom_range(0, 288), irandom_range(672, 960))",
    speedName + " horizontal bands");
imports.QueueReplace(speedName, speed);

string playerDrawName = "gml_Object_oPlayer_Draw_64";
string playerDraw = GetDecompiledText(playerDrawName);
playerDraw = ReplaceOnce(playerDraw, "irandom_range(0, 720)",
    "irandom_range(0, 960)", playerDrawName + " horizontal wind range");
playerDraw = ReplaceOnce(playerDraw, ", 0, 720, irandom_range(1, 4), 270,",
    ", 0, 960, irandom_range(1, 4), 270,", playerDrawName + " vertical wind span");
imports.QueueReplace(playerDrawName, playerDraw);

string trainingName = "gml_GlobalScript_drawMenuTraining";
string training = GetDecompiledText(trainingName);
training = ReplaceCount(training, "720", "960", 4,
    trainingName + " vertical menu extents");
training = ReplaceOnce(training, "var yy = 360;", "var yy = 480;",
    trainingName + " preview center");
imports.QueueReplace(trainingName, training);

string statsName = "gml_GlobalScript_drawLevelStats";
string stats = GetDecompiledText(statsName);
stats = ReplaceCount(stats, "var rectHeight = 720;", "var rectHeight = 960;", 6,
    statsName + " panel heights");
imports.QueueReplace(statsName, stats);

string stage1Name = "gml_GlobalScript_drawStageClear1";
string stage1 = GetDecompiledText(stage1Name);
stage1 = ReplaceOnce(stage1, "draw_rectangle_color(0, 0, 1280, 720,",
    "draw_rectangle_color(0, 0, 1280, 960,", stage1Name + " overlay");
imports.QueueReplace(stage1Name, stage1);

foreach (var item in new[]
{
    new { Name = "gml_GlobalScript_drawStageClear2", Count = 2 },
    new { Name = "gml_GlobalScript_drawStageClear3", Count = 3 }
})
{
    string source = GetDecompiledText(item.Name);
    source = ReplaceCount(source, "720", "960", item.Count,
        item.Name + " vertical extents");
    imports.QueueReplace(item.Name, source);
}

imports.Import();

ScriptMessage("Applied experimental Advent Neon 1280x960 cameras, compositor, menus, and intro/UI anchors.");
