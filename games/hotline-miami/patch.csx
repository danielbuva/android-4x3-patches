using System;
using System.Linq;
using UndertaleModLib.Compiler;

// Structural Hotline Miami patch. Compatibility is established from the
// project format and the exact rooms, code entries, and source fragments
// changed below. Third-party promo cleanup is optional.

EnsureDataLoaded();

void Require(bool condition, string message)
{
    if (!condition)
        throw new InvalidOperationException("Hotline Miami 4:3 guard failed: " + message);
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

int CenteredStart(int oldStart, int oldSize, int newSize)
    => (int)Math.Round(oldStart + ((oldSize - newSize) / 2.0));

Require(Data.GeneralInfo.Name.Content == "HotlineMiami1", "unexpected project name");
Require(Data.GeneralInfo.BytecodeVersion == 17, "unexpected bytecode version");
Require(Data.GeneralInfo.DefaultWindowWidth == 1920 &&
        Data.GeneralInfo.DefaultWindowHeight == 1080,
        "unexpected default runner surface");
Require(Data.Rooms.Count > 0, "archive has no rooms");
Require(Data.Rooms.Count(room => room.Name.Content == "rmBikeEnding") == 1,
        "special ending room missing or duplicated");
Require(Data.Rooms.Count(room => room.Name.Content == "rmDennatonSplash") == 1,
        "developer splash room missing or duplicated");

// Android creates the runner surface before any GML can call scrSetPort. Set
// the archive's default presentation to 4:3 so the patched cameras use the
// whole physical display instead of a centered 16:9 strip.
Data.GeneralInfo.DefaultWindowWidth = 1440;

CodeImportGroup importGroup = new(Data);

// Some third-party builds add two port-promotion objects. They are unrelated
// to 4:3 compatibility: remove one only when its object, sprite, draw event,
// click event, and URL all form the unique known signature.
void NeutralizePromoIfRecognized(string objectName, string spriteName, string url)
{
    var candidates = Data.GameObjects
        .Where(item => item.Name?.Content == objectName &&
                       item.Sprite?.Name?.Content == spriteName)
        .ToList();
    if (candidates.Count != 1)
        return;

    string drawName = "gml_Object_" + objectName + "_Draw_0";
    string clickName = "gml_Object_" + objectName + "_Mouse_4";
    if (Data.Code.ByName(drawName) == null || Data.Code.ByName(clickName) == null)
        return;

    string draw = GetDecompiledText(drawName);
    string click = GetDecompiledText(clickName);
    if (!draw.Contains("draw_self", StringComparison.Ordinal) ||
        !click.Contains(url, StringComparison.Ordinal))
        return;

    var promo = candidates[0];
    foreach (var room in Data.Rooms)
    {
        for (int index = room.GameObjects.Count - 1; index >= 0; index--)
        {
            if (room.GameObjects[index].ObjectDefinition == promo)
                room.GameObjects.RemoveAt(index);
        }
    }
    importGroup.QueueReplace(drawName, "exit;");
    importGroup.QueueReplace(clickName, "exit;");
}

NeutralizePromoIfRecognized("object851", "sprite1427", "https://t.me/glesign");
NeutralizePromoIfRecognized("object852", "sprite1428", "https://t.me/dalmac_ports");

// Patch room cameras structurally. Normal rooms keep the center of their
// original camera while changing the logical span to 400x300. The developer
// splash keeps its existing 2x zoom, changing 240x135 to 200x150. The ending's
// two stacked cameras together form one 400x300 canvas.
foreach (var room in Data.Rooms)
{
    Require(room.Views.Count >= 1, "room has no view slots: " + room.Name.Content);

    if (room.Name.Content == "rmBikeEnding")
    {
        Require(room.Views.Count >= 2 && room.Views[0].Enabled && room.Views[1].Enabled,
                "rmBikeEnding split views changed");
        var top = room.Views[0];
        var bottom = room.Views[1];
        Require(top.ViewWidth == 480 && top.ViewHeight == 139 &&
                bottom.ViewWidth == 480 && bottom.ViewHeight == 131,
                "rmBikeEnding source geometry changed");

        top.ViewX = CenteredStart(top.ViewX, top.ViewWidth, 400);
        top.ViewY = -15;
        top.ViewWidth = 400;
        top.ViewHeight = 154;
        top.PortX = 0;
        top.PortY = 0;
        top.PortWidth = 1280;
        top.PortHeight = 493;

        bottom.ViewX = CenteredStart(bottom.ViewX, bottom.ViewWidth, 400);
        bottom.ViewY = 139;
        bottom.ViewWidth = 400;
        bottom.ViewHeight = 146;
        bottom.PortX = 0;
        bottom.PortY = 493;
        bottom.PortWidth = 1280;
        bottom.PortHeight = 467;
        continue;
    }

    var view = room.Views[0];
    int targetWidth = room.Name.Content == "rmDennatonSplash" ? 200 : 400;
    int targetHeight = room.Name.Content == "rmDennatonSplash" ? 150 : 300;

    view.ViewX = CenteredStart(view.ViewX, view.ViewWidth, targetWidth);
    view.ViewY = CenteredStart(view.ViewY, view.ViewHeight, targetHeight);
    view.ViewWidth = targetWidth;
    view.ViewHeight = targetHeight;
    view.PortX = 0;
    view.PortY = 0;
    view.PortWidth = 1280;
    view.PortHeight = 960;
    view.Enabled = true;
}

// Replace the width-only fallback with a runtime 4:3 viewport calculation.
// On the target 1280x960 display this is the full output. Other displays get
// the largest centered 4:3 viewport that fits without geometric stretching.
string originalSetPort = GetDecompiledText("gml_GlobalScript_scrSetPort");
Require(originalSetPort.Contains("width < 1200", StringComparison.Ordinal) &&
        originalSetPort.Contains("900, 576", StringComparison.Ordinal),
        "scrSetPort is not the expected port implementation");

importGroup.QueueReplace("gml_GlobalScript_scrSetPort", @"
function scrSetPort()
{
    var display_width = display_get_width();
    var display_height = display_get_height();
    var port_width = display_width;
    var port_height = floor(port_width * 0.75);

    if (port_height > display_height)
    {
        port_height = display_height;
        port_width = floor(port_height * (4 / 3));
    }

    var port_x = floor((display_width - port_width) * 0.5);
    var port_y = floor((display_height - port_height) * 0.5);
    var bike_top_height = floor(port_height * (154 / 300));
    var i = 0;

    repeat (300)
    {
        if (room_exists(i))
        {
            if (i == rmBikeEnding)
            {
                room_set_viewport(i, 0, 1, port_x, port_y, port_width, bike_top_height);
                room_set_viewport(i, 1, 1, port_x, port_y + bike_top_height,
                                  port_width, port_height - bike_top_height);
            }
            else
            {
                room_set_viewport(i, 0, 1, port_x, port_y, port_width, port_height);
            }
        }
        i += 1;
    }
}
");

// Mobile touch input and rendering temporarily switch to a quarter-HD GUI.
// Keep its 341.5-unit horizontal coordinate system and expand only its height
// to the corresponding 4:3 value. Existing custom horizontal positions remain
// valid; vertical repositioning is deliberately left for device testing.
string oldGui = "display_set_gui_size(341.5, 192);";
string newGui = "display_set_gui_size(341.5, 256.125);";
foreach (string codeName in new[]
{
    "gml_Object_obj_mobile_stick_Draw_64",
    "gml_Object_obj_mobile_stick_Draw_74",
    "gml_Object_obj_mobile_buttons_Draw_64",
    "gml_Object_obj_mobile_buttons_Draw_74",
    "gml_Object_obj_customize_control_Draw_64"
})
{
    string source = GetDecompiledText(codeName);
    Require(Occurrences(source, oldGui) == 1,
            codeName + " no longer has exactly one expected GUI-size call");
    importGroup.QueueReplace(codeName, source.Replace(oldGui, newGui));
}

// The stock darkness/light compositors were sized for the original 400x256
// gameplay camera. Expanding the room view without expanding these surfaces
// leaves the new lower strip unshaded. Allocate against the active view and
// retain the original 16-pixel guard on every edge.
// Use the accepted 400x300 gameplay geometry directly. Imported Create events
// run before the compiler-emitted e__VW enum exists, so resolving view size
// through that enum would crash the first tutorial/gameplay room.
string dynamicLightSurface = "surface_create(432, 332)";

string ReplaceLightOnce(string source, string oldText, string newText, string label)
{
    Require(Occurrences(source, oldText) == 1,
            label + " no longer has exactly one expected lighting fragment");
    return source.Replace(oldText, newText);
}

string lightingEngineCreateName = "gml_Object_objLightingEngine_Create_0";
string lightingEngineCreate = GetDecompiledText(lightingEngineCreateName);
lightingEngineCreate = ReplaceLightOnce(lightingEngineCreate,
    "surface_create(500, 272)", dynamicLightSurface, lightingEngineCreateName);
importGroup.QueueReplace(lightingEngineCreateName, lightingEngineCreate);

string lightingEngineStepName = "gml_Object_objLightingEngine_Step_0";
string lightingEngineStep = GetDecompiledText(lightingEngineStepName);
lightingEngineStep = ReplaceLightOnce(lightingEngineStep,
    "surface_create(room_width, room_height + 64)", dynamicLightSurface,
    lightingEngineStepName + " recovery allocation");
lightingEngineStep = ReplaceLightOnce(lightingEngineStep,
    "global.myy[i] += 288;", "global.myy[i] += 332;",
    lightingEngineStepName + " lower particle wrap");
lightingEngineStep = ReplaceLightOnce(lightingEngineStep,
    "global.myy[i] > 272", "global.myy[i] > 316",
    lightingEngineStepName + " wrap limit");
lightingEngineStep = ReplaceLightOnce(lightingEngineStep,
    "global.myy[i] -= 288;", "global.myy[i] -= 332;",
    lightingEngineStepName + " upper particle wrap");
importGroup.QueueReplace(lightingEngineStepName, lightingEngineStep);

string tutorialCreateName = "gml_Object_objTutorialLight_Create_0";
string tutorialCreate = GetDecompiledText(tutorialCreateName);
tutorialCreate = ReplaceLightOnce(tutorialCreate, "surface_create(500, 288)",
                                  dynamicLightSurface, tutorialCreateName);
tutorialCreate = ReplaceLightOnce(tutorialCreate, "my_y[i] = random(256);",
    "my_y[i] = random(300);",
    tutorialCreateName + " particle initialization");
importGroup.QueueReplace(tutorialCreateName, tutorialCreate);

string tutorialStepName = "gml_Object_objTutorialLight_Step_0";
string tutorialStep = GetDecompiledText(tutorialStepName);
tutorialStep = ReplaceLightOnce(tutorialStep, "surface_create(500, 288)",
                                dynamicLightSurface, tutorialStepName);
tutorialStep = ReplaceLightOnce(tutorialStep,
    "my_y[i] += 288;", "my_y[i] += 332;",
    tutorialStepName + " lower particle wrap");
tutorialStep = ReplaceLightOnce(tutorialStep,
    "my_y[i] > 272", "my_y[i] > 316",
    tutorialStepName + " wrap limit");
tutorialStep = ReplaceLightOnce(tutorialStep,
    "my_y[i] -= 288;", "my_y[i] -= 332;",
    tutorialStepName + " upper particle wrap");
importGroup.QueueReplace(tutorialStepName, tutorialStep);

string sequenceCreateName = "gml_Object_objSequence12Light_Create_0";
string sequenceCreate = GetDecompiledText(sequenceCreateName);
sequenceCreate = ReplaceLightOnce(sequenceCreate, "surface_create(500, 288)",
                                  dynamicLightSurface, sequenceCreateName);
importGroup.QueueReplace(sequenceCreateName, sequenceCreate);

string sequenceDrawName = "gml_Object_objSequence12Light_Draw_0";
string sequenceDraw = GetDecompiledText(sequenceDrawName);
sequenceDraw = ReplaceLightOnce(sequenceDraw, "surface_create(500, 288)",
                                dynamicLightSurface, sequenceDrawName);
importGroup.QueueReplace(sequenceDrawName, sequenceDraw);

string sequenceStepName = "gml_Object_objSequence12Light_Step_0";
string sequenceStep = GetDecompiledText(sequenceStepName);
sequenceStep = ReplaceLightOnce(sequenceStep,
    "global.myy[i] += 288;", "global.myy[i] += 332;",
    sequenceStepName + " lower particle wrap");
sequenceStep = ReplaceLightOnce(sequenceStep,
    "global.myy[i] > 272", "global.myy[i] > 316",
    sequenceStepName + " wrap limit");
sequenceStep = ReplaceLightOnce(sequenceStep,
    "global.myy[i] -= 288;", "global.myy[i] -= 332;",
    sequenceStepName + " upper particle wrap");
importGroup.QueueReplace(sequenceStepName, sequenceStep);

importGroup.Import();

ScriptMessage("Applied Hotline Miami 4:3 cameras, presentation, GUI, and lighting.");
