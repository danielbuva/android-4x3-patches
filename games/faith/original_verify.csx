using System;

EnsureDataLoaded();

void Require(bool condition, string message)
{
    if (!condition)
        throw new InvalidOperationException("FAITH original-state check failed: " + message);
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

Require(Data.GeneralInfo.Name.Content == "FAITH", "unexpected project name");
Require(Data.GeneralInfo.BytecodeVersion == 17, "unexpected bytecode version");
Require(Data.GameObjects.ByName("obj_mobilecontrols") != null,
        "obj_mobilecontrols is missing");
Require(Data.GameObjects.ByName("obj_mobilebuttons") != null,
        "obj_mobilebuttons is missing");

string views = GetDecompiledText("gml_GlobalScript_scr_views");
Require(views.Contains("camera_create_view(-10000, -10000, 1920, 1080",
                       StringComparison.Ordinal),
        "decorative background camera changed");
Require(Occurrences(views,
                    "camera_create_view(0, 0, 1296, 1080, 0, -1, -1, -1, 0, 0)") == 3,
        "game camera definitions changed");
Require(Occurrences(views, "view_xport[1] = 312;") == 2,
        "side-panel ports changed");

RequireCode("gml_Object_obj_configsHANDLER_Create_0",
    "thirteenText = scr_LOC_gimmeUIText(83);\nfourteenText = scr_LOC_gimmeUIText(85);",
    "hintText = \"\";\ncursor_spot = 0;");
RequireCode("gml_Object_obj_configsHANDLER_Step_0",
    "if (cursor_spot > 13)", "if (cursor_spot < 0)",
    "else if (cursor_spot == 13 || cursor_spot == 12)");
RequireCode("gml_Object_obj_configsHANDLER_Draw_0",
    "textDrawY + 600", "textDrawY + 660");

foreach (string name in new[]
{
    "gml_Object_obj_mobilecontrols_Create_0",
    "gml_Object_obj_mobilebuttons_Create_0"
})
{
    string source = GetDecompiledText(name);
    Require(Occurrences(source, "active_key = -1;\nif (file_exists(") == 1,
            name + " initialization changed");
    Require(!source.Contains("UT_CONFIG_TOUCH", StringComparison.Ordinal),
            name + " is partially patched");
}

foreach (string name in new[]
{
    "gml_Object_obj_mobilecontrols_Draw_75",
    "gml_Object_obj_mobilebuttons_Draw_75"
})
{
    Require(Data.Code.ByName(name) != null, "missing code " + name);
    Require(!GetDecompiledText(name).Contains("UT_CONFIG_TOUCH", StringComparison.Ordinal),
            name + " is partially patched");
}

ScriptMessage("FAITH original 4:3 targets recognized.");
