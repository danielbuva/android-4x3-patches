using System;
using System.Linq;

EnsureDataLoaded();

void Require(bool condition, string message)
{
    if (!condition)
        throw new InvalidOperationException("Hotline Miami 4:3 verification failed: " + message);
}

Require(Data.GeneralInfo.Name.Content == "HotlineMiami1", "unexpected project name");
Require(Data.GeneralInfo.BytecodeVersion == 17, "unexpected bytecode version");
Require(Data.GeneralInfo.DefaultWindowWidth == 1440 &&
        Data.GeneralInfo.DefaultWindowHeight == 1080,
        "Android runner surface is not 4:3");
Require(Data.Rooms.Count > 0, "archive has no rooms");
Require(Data.Rooms.Count(room => room.Name.Content == "rmBikeEnding") == 1,
        "special ending room missing or duplicated");
Require(Data.Rooms.Count(room => room.Name.Content == "rmDennatonSplash") == 1,
        "developer splash room missing or duplicated");

foreach (var room in Data.Rooms)
{
    if (room.Name.Content == "rmBikeEnding")
    {
        Require(room.Views.Count >= 2 &&
                room.Views[0].ViewWidth == 400 && room.Views[0].ViewHeight == 154 &&
                room.Views[1].ViewWidth == 400 && room.Views[1].ViewHeight == 146,
                "split ending geometry changed");
    }
    else if (room.Name.Content == "rmDennatonSplash")
    {
        Require(room.Views.Count >= 1 && room.Views[0].ViewWidth == 200 &&
                room.Views[0].ViewHeight == 150,
                "developer splash geometry changed");
    }
    else
    {
        Require(room.Views.Count >= 1 && room.Views[0].Enabled &&
                room.Views[0].ViewWidth == 400 && room.Views[0].ViewHeight == 300,
                "normal room is not 4:3: " + room.Name.Content);
    }
}

string setPort = GetDecompiledText("gml_GlobalScript_scrSetPort");
Require(setPort.Contains("port_height = floor(port_width * 0.75)",
                         StringComparison.Ordinal) &&
        setPort.Contains("display_get_height", StringComparison.Ordinal) &&
        !setPort.Contains("width < 1200", StringComparison.Ordinal),
        "adaptive 4:3 viewport missing");

foreach (string name in new[]
{
    "gml_Object_obj_mobile_stick_Draw_64",
    "gml_Object_obj_mobile_stick_Draw_74",
    "gml_Object_obj_mobile_buttons_Draw_64",
    "gml_Object_obj_mobile_buttons_Draw_74",
    "gml_Object_obj_customize_control_Draw_64"
})
    Require(GetDecompiledText(name).Contains("display_set_gui_size(341.5, 256.125)",
                                             StringComparison.Ordinal),
            "4:3 GUI height missing in " + name);

foreach (string name in new[]
{
    "gml_Object_objLightingEngine_Create_0",
    "gml_Object_objLightingEngine_Step_0",
    "gml_Object_objTutorialLight_Create_0",
    "gml_Object_objTutorialLight_Step_0",
    "gml_Object_objSequence12Light_Create_0",
    "gml_Object_objSequence12Light_Draw_0"
})
{
    string source = GetDecompiledText(name);
    Require(source.Contains("surface_create(432, 332)", StringComparison.Ordinal),
            "4:3 light surface missing in " + name);
    Require(!source.Contains("e__VW", StringComparison.Ordinal) ||
            !name.EndsWith("Create_0", StringComparison.Ordinal),
            "early Create event reads unavailable view enum in " + name);
}

foreach (string name in new[]
{
    "gml_Object_objLightingEngine_Step_0",
    "gml_Object_objTutorialLight_Step_0",
    "gml_Object_objSequence12Light_Step_0"
})
{
    string source = GetDecompiledText(name);
    Require(source.Contains("+= 332", StringComparison.Ordinal) &&
            source.Contains("> 316", StringComparison.Ordinal) &&
            source.Contains("-= 332", StringComparison.Ordinal),
            "4:3 particle wrapping missing in " + name);
}

Require(GetDecompiledText("gml_Object_objTutorialLight_Create_0")
            .Contains("my_y[i] = random(300)", StringComparison.Ordinal),
        "tutorial particles do not cover the 300-pixel view");

ScriptMessage("Hotline Miami 4:3 targets verified.");
