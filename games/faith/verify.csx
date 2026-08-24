using System;

EnsureDataLoaded();

void Require(bool condition, string message)
{
    if (!condition)
        throw new InvalidOperationException("FAITH 4:3 verification failed: " + message);
}

Require(Data.GeneralInfo.Name.Content == "FAITH", "unexpected project name");
Require(Data.GeneralInfo.BytecodeVersion == 17, "unexpected bytecode version");

string views = GetDecompiledText("gml_GlobalScript_scr_views");
Require(views.Contains("camera_create_view(-72, 0, 1440, 1080",
                       StringComparison.Ordinal), "centered camera missing");
Require(views.Contains("port_height = floor(port_width * 0.75)",
                       StringComparison.Ordinal), "4:3 output calculation missing");
Require(!views.Contains("view_xport[1] = 312", StringComparison.Ordinal) &&
        !views.Contains("camera_create_view(-10000, -10000, 1920, 1080",
                        StringComparison.Ordinal), "decorative compositor remains");

string create = GetDecompiledText("gml_Object_obj_configsHANDLER_Create_0");
Require(create.Contains("TOUCH CONTROLS", StringComparison.Ordinal) &&
        create.Contains("touchvisibility_v2.ini", StringComparison.Ordinal) &&
        create.Contains("touchControls = 0", StringComparison.Ordinal) &&
        create.Contains("fifteenText", StringComparison.Ordinal),
        "Options visibility preference incomplete");

string step = GetDecompiledText("gml_Object_obj_configsHANDLER_Step_0");
Require(step.Contains("cursor_spot > 14", StringComparison.Ordinal) &&
        step.Contains("touchControls = !touchControls", StringComparison.Ordinal) &&
        step.Contains("ini_write_real(\"CONFIG\", \"visible\", touchControls)",
                      StringComparison.Ordinal), "Options persistence incomplete");

string optionsDraw = GetDecompiledText("gml_Object_obj_configsHANDLER_Draw_0");
Require(optionsDraw.Contains("textDrawY + 720", StringComparison.Ordinal) &&
        optionsDraw.Contains("touchTextVal", StringComparison.Ordinal),
        "Options touch row missing");

foreach (string name in new[]
{
    "gml_Object_obj_mobilecontrols_Create_0",
    "gml_Object_obj_mobilebuttons_Create_0"
})
{
    string source = GetDecompiledText(name);
    Require(source.Contains("touchvisibility_v2.ini", StringComparison.Ordinal) &&
            source.Contains("global.UT_CONFIG_TOUCH = 0", StringComparison.Ordinal) &&
            source.Contains("ini_read_real(\"CONFIG\", \"visible\", 0)",
                            StringComparison.Ordinal), name + " visibility state missing");
}

string mobileCreate = GetDecompiledText("gml_Object_obj_mobilecontrols_Create_0");
Require(mobileCreate.Contains("zx > 1200", StringComparison.Ordinal) &&
        mobileCreate.Contains("zx -= 480", StringComparison.Ordinal) &&
        mobileCreate.Contains("cx -= 480", StringComparison.Ordinal),
        "right-side coordinate migration missing");

foreach (string name in new[]
{
    "gml_Object_obj_mobilecontrols_Draw_75",
    "gml_Object_obj_mobilebuttons_Draw_75"
})
{
    Require(GetDecompiledText(name).StartsWith("if (global.UT_CONFIG_TOUCH == 0)",
                                               StringComparison.Ordinal),
            name + " visibility guard missing");
}

ScriptMessage("FAITH 4:3 targets verified.");
