using System;
using System.Linq;

EnsureDataLoaded();

void Require(bool condition, string message)
{
    if (!condition)
        throw new InvalidOperationException("Hotline Miami original-state check failed: " + message);
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

void RequireCode(string name, params string[] fragments)
{
    Require(Data.Code.ByName(name) != null, "missing code " + name);
    string source = GetDecompiledText(name);
    foreach (string fragment in fragments)
        Require(Occurrences(source, fragment) == 1,
                name + " does not contain one expected source fragment");
}

Require(Data.GeneralInfo.Name.Content == "HotlineMiami1", "unexpected project name");
Require(Data.GeneralInfo.BytecodeVersion == 17, "unexpected bytecode version");
Require(Data.GeneralInfo.DefaultWindowWidth == 1920 &&
        Data.GeneralInfo.DefaultWindowHeight == 1080,
        "runner surface is changed or already patched");
Require(Data.Rooms.Count > 0, "archive has no rooms");
Require(Data.Rooms.Count(room => room.Name.Content == "rmBikeEnding") == 1,
        "special ending room missing or duplicated");
Require(Data.Rooms.Count(room => room.Name.Content == "rmDennatonSplash") == 1,
        "developer splash room missing or duplicated");

foreach (var room in Data.Rooms)
    Require(room.Views.Count >= 1, "room has no view slot: " + room.Name.Content);

var bike = Data.Rooms.First(room => room.Name.Content == "rmBikeEnding");
Require(bike.Views.Count >= 2 && bike.Views[0].Enabled && bike.Views[1].Enabled &&
        bike.Views[0].ViewWidth == 480 && bike.Views[0].ViewHeight == 139 &&
        bike.Views[1].ViewWidth == 480 && bike.Views[1].ViewHeight == 131,
        "split ending source geometry changed");

string setPort = GetDecompiledText("gml_GlobalScript_scrSetPort");
Require(setPort.Contains("width < 1200", StringComparison.Ordinal) &&
        setPort.Contains("900, 576", StringComparison.Ordinal) &&
        !setPort.Contains("port_height = floor(port_width * 0.75)",
                          StringComparison.Ordinal), "scrSetPort source changed");

foreach (string name in new[]
{
    "gml_Object_obj_mobile_stick_Draw_64",
    "gml_Object_obj_mobile_stick_Draw_74",
    "gml_Object_obj_mobile_buttons_Draw_64",
    "gml_Object_obj_mobile_buttons_Draw_74",
    "gml_Object_obj_customize_control_Draw_64"
})
    RequireCode(name, "display_set_gui_size(341.5, 192);");

RequireCode("gml_Object_objLightingEngine_Create_0", "surface_create(500, 272)");
RequireCode("gml_Object_objLightingEngine_Step_0",
    "surface_create(room_width, room_height + 64)",
    "global.myy[i] += 288", "global.myy[i] > 272", "global.myy[i] -= 288");
RequireCode("gml_Object_objTutorialLight_Create_0",
    "surface_create(500, 288)", "my_y[i] = random(256);");
RequireCode("gml_Object_objTutorialLight_Step_0",
    "surface_create(500, 288)",
    "my_y[i] += 288", "my_y[i] > 272", "my_y[i] -= 288");
RequireCode("gml_Object_objSequence12Light_Create_0", "surface_create(500, 288)");
RequireCode("gml_Object_objSequence12Light_Draw_0", "surface_create(500, 288)");
RequireCode("gml_Object_objSequence12Light_Step_0",
    "global.myy[i] += 288", "global.myy[i] > 272", "global.myy[i] -= 288");

ScriptMessage("Hotline Miami original 4:3 targets recognized.");
