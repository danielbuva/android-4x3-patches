using System;
using UndertaleModLib.Compiler;

// Structural FAITH mobile patch. Guards use named resources and narrowly
// scoped source anchors; no complete game routine is embedded here.

EnsureDataLoaded();

void Require(bool condition, string message)
{
    if (!condition)
        throw new InvalidOperationException("FAITH 4:3 guard failed: " + message);
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

string InsertBeforeOnce(string source, string anchor, string insertion,
                        string label)
    => ReplaceOnce(source, anchor, insertion + anchor, label);

string RemoveStatementContainingOnce(string source, string needle, string label)
{
    Require(Occurrences(source, needle) == 1, label + " is missing or ambiguous");
    int position = source.IndexOf(needle, StringComparison.Ordinal);
    int start = source.LastIndexOf('\n', position);
    start = start < 0 ? 0 : start + 1;
    int semicolon = source.IndexOf(';', position);
    Require(semicolon >= 0, label + " has no statement terminator");
    int end = source.IndexOf('\n', semicolon);
    end = end < 0 ? source.Length : end + 1;
    return source.Remove(start, end - start);
}

string InsertBeforeFinalBrace(string source, string insertion, string label)
{
    int close = source.LastIndexOf('}');
    Require(close >= 0 && source.Substring(close + 1).Trim().Length == 0,
            label + " has no unique final function brace");
    return source.Insert(close, insertion);
}

string RewriteBlinkSection(string source, string startAnchor,
                           string endAnchor, string oldRow, string newRow,
                           string oldVariable, string newVariable,
                           string label)
{
    Require(Occurrences(source, startAnchor) == 1,
            label + " start is missing or ambiguous");
    int start = source.IndexOf(startAnchor, StringComparison.Ordinal);
    int end = endAnchor == null
        ? source.Length
        : source.IndexOf(endAnchor, start + startAnchor.Length,
                         StringComparison.Ordinal);
    Require(end >= start, label + " end is missing");
    string section = source.Substring(start, end - start);
    Require(Occurrences(section, oldRow) == 1,
            label + " row anchor changed");
    Require(Occurrences(section, oldVariable) == 5,
            label + " text-variable anchors changed");
    section = section.Replace(oldRow, newRow)
                     .Replace(oldVariable, newVariable);
    return source.Substring(0, start) + section + source.Substring(end);
}

Require(Data.GeneralInfo.Name.Content == "FAITH", "unexpected project name");
Require(Data.GeneralInfo.BytecodeVersion == 17, "unexpected bytecode version");
Require(Data.GameObjects.ByName("obj_mobilecontrols") != null,
        "obj_mobilecontrols is missing");
Require(Data.GameObjects.ByName("obj_mobilebuttons") != null,
        "obj_mobilebuttons is missing");

CodeImportGroup importGroup = new(Data);

// Expand each logical game camera and append one adaptive 4:3 output setup.
string viewsName = "gml_GlobalScript_scr_views";
string views = GetDecompiledText(viewsName);
views = RemoveStatementContainingOnce(views,
    "camera_create_view(-10000, -10000, 1920, 1080",
    viewsName + " decorative camera");
views = ReplaceCount(views,
    "camera_create_view(0, 0, 1296, 1080, 0, -1, -1, -1, 0, 0)",
    "camera_create_view(-72, 0, 1440, 1080, 0, -1, -1, -1, 0, 0)",
    3, viewsName + " game cameras");
views = ReplaceCount(views, "view_xport[1] = 312;", "view_xport[1] = 0;",
                     2, viewsName + " legacy side offsets");
views = InsertBeforeFinalBrace(views, @"
    view_visible[0] = false;
    var output_width = display_get_width();
    var output_height = display_get_height();
    var port_width = output_width;
    var port_height = floor(port_width * 0.75);
    if (port_height > output_height)
    {
        port_height = output_height;
        port_width = floor(port_height * (4 / 3));
    }
    view_xport[1] = floor((output_width - port_width) * 0.5);
    view_yport[1] = floor((output_height - port_height) * 0.5);
    view_wport[1] = port_width;
    view_hport[1] = port_height;
    if (window_get_fullscreen())
        window_set_size(output_width, output_height);
", viewsName);
importGroup.QueueReplace(viewsName, views);

// Add a persistent touch-overlay preference without changing existing config
// storage or virtual input behavior.
string optionsCreateName = "gml_Object_obj_configsHANDLER_Create_0";
string optionsCreate = GetDecompiledText(optionsCreateName);
optionsCreate = ReplaceOnce(optionsCreate,
    "thirteenText = scr_LOC_gimmeUIText(83);\nfourteenText = scr_LOC_gimmeUIText(85);",
    "thirteenText = \"TOUCH CONTROLS\";\n" +
    "fourteenText = scr_LOC_gimmeUIText(83);\n" +
    "fifteenText = scr_LOC_gimmeUIText(85);",
    optionsCreateName + " labels");
optionsCreate = ReplaceOnce(optionsCreate, "hintText = \"\";\ncursor_spot = 0;",
    "touchControls = 0;\n" +
    "if (!file_exists(\"touchvisibility_v2.ini\"))\n" +
    "{\n" +
    "    ini_open(\"touchvisibility.ini\");\n" +
    "    ini_write_real(\"CONFIG\", \"visible\", 0);\n" +
    "    ini_close();\n" +
    "    ini_open(\"touchvisibility_v2.ini\");\n" +
    "    ini_write_real(\"CONFIG\", \"migrated\", 1);\n" +
    "    ini_close();\n" +
    "}\n" +
    "else if (file_exists(\"touchvisibility.ini\"))\n" +
    "{\n" +
    "    ini_open(\"touchvisibility.ini\");\n" +
    "    touchControls = ini_read_real(\"CONFIG\", \"visible\", 0);\n" +
    "    ini_close();\n" +
    "}\n" +
    "global.UT_CONFIG_TOUCH = touchControls;\n" +
    "touchTextVal = touchControls ? \"ON\" : \"OFF\";\n" +
    "hintText = \"\";\n" +
    "cursor_spot = 0;",
    optionsCreateName + " touch preference");
importGroup.QueueReplace(optionsCreateName, optionsCreate);

string optionsStepName = "gml_Object_obj_configsHANDLER_Step_0";
string optionsStep = GetDecompiledText(optionsStepName);
optionsStep = ReplaceOnce(optionsStep, "if (cursor_spot > 13)",
                          "if (cursor_spot > 14)",
                          optionsStepName + " lower wrap");
optionsStep = ReplaceOnce(optionsStep,
    "if (cursor_spot < 0)\n    {\n        cursor_spot = 13;",
    "if (cursor_spot < 0)\n    {\n        cursor_spot = 14;",
    optionsStepName + " upper wrap");
optionsStep = ReplaceCount(optionsStep,
    "if (cursor_spot > 0 && cursor_spot < 12)",
    "if (cursor_spot > 0 && cursor_spot < 13)", 2,
    optionsStepName + " cursor sounds");

string touchToggle = @"    else if (cursor_spot == 12)
    {
        touchControls = !touchControls;
        touchTextVal = touchControls ? ""ON"" : ""OFF"";
        inputCooldown = 5;
    }
";
optionsStep = InsertBeforeOnce(optionsStep,
    "}\nelse if (cursor_left && inputCooldown == 0)", touchToggle,
    optionsStepName + " right touch toggle");
optionsStep = InsertBeforeOnce(optionsStep, "}\nelse if (cursor_sel)",
    touchToggle, optionsStepName + " left touch toggle");

optionsStep = ReplaceOnce(optionsStep,
    "else if (cursor_spot == 13 || cursor_spot == 12)",
    "else if (cursor_spot == 14 || cursor_spot == 13)",
    optionsStepName + " action rows");
optionsStep = ReplaceOnce(optionsStep,
    "if (cursor_spot == 13)\n            {\n                global.UT_CONFIG_MASTERVOL",
    "if (cursor_spot == 14)\n            {\n                global.UT_CONFIG_MASTERVOL",
    optionsStepName + " apply row");
optionsStep = ReplaceOnce(optionsStep,
    "global.UT_CONFIG_DEMONS = gimmeDemons;\n                scr_UT_writeConfigs();",
    "global.UT_CONFIG_DEMONS = gimmeDemons;\n" +
    "                global.UT_CONFIG_TOUCH = touchControls;\n" +
    "                ini_open(\"touchvisibility.ini\");\n" +
    "                ini_write_real(\"CONFIG\", \"visible\", touchControls);\n" +
    "                ini_close();\n" +
    "                scr_UT_writeConfigs();",
    optionsStepName + " apply visibility");
optionsStep = ReplaceOnce(optionsStep,
    "if (cursor_spot == 12)\n            {\n                scr_UT_setDefaultConfigs();",
    "if (cursor_spot == 13)\n            {\n" +
    "                global.UT_CONFIG_TOUCH = 0;\n" +
    "                touchControls = 0;\n" +
    "                touchTextVal = \"OFF\";\n" +
    "                ini_open(\"touchvisibility.ini\");\n" +
    "                ini_write_real(\"CONFIG\", \"visible\", 0);\n" +
    "                ini_close();\n" +
    "                scr_UT_setDefaultConfigs();",
    optionsStepName + " reset visibility");
optionsStep = ReplaceOnce(optionsStep,
    "else if (cursor_spot == 12)\n{\n    hintText = scr_LOC_gimmeUIText(84);",
    "else if (cursor_spot == 13)\n{\n    hintText = scr_LOC_gimmeUIText(84);",
    optionsStepName + " reset hint");

string applyBlink =
    "if (cursor_spot == 13)\n{\n    if (confirmCheck)\n    {\n        if (fourteenText";
string resetBlink =
    "if (cursor_spot == 12)\n{\n    if (confirmCheck)\n    {\n        if (thirteenText";
optionsStep = RewriteBlinkSection(optionsStep, applyBlink, resetBlink,
    "cursor_spot == 13", "cursor_spot == 14", "fourteenText", "fifteenText",
    optionsStepName + " apply blink");
optionsStep = RewriteBlinkSection(optionsStep, resetBlink, null,
    "cursor_spot == 12", "cursor_spot == 13", "thirteenText", "fourteenText",
    optionsStepName + " reset blink");
importGroup.QueueReplace(optionsStepName, optionsStep);

string optionsDrawName = "gml_Object_obj_configsHANDLER_Draw_0";
string optionsDraw = GetDecompiledText(optionsDrawName);
string applyLabel =
    "draw_text(room_width * 0.125, textDrawY + 660, string_hash_to_newline(fourteenText));";
optionsDraw = ReplaceOnce(optionsDraw, applyLabel,
    applyLabel + "\n" +
    "    draw_text(room_width * 0.125, textDrawY + 720, " +
    "string_hash_to_newline(fifteenText));",
    optionsDrawName + " touch label");
string touchValueAnchor =
    "draw_text(room_width * 0.125 * 7, textDrawY + 540, " +
    "string_hash_to_newline(twelveTextVal));";
optionsDraw = ReplaceOnce(optionsDraw, touchValueAnchor,
    touchValueAnchor + "\n" +
    "    draw_set_color(c_blue);\n" +
    "    draw_text(room_width * 0.125 * 7, textDrawY + 600, " +
    "string_hash_to_newline(touchTextVal));",
    optionsDrawName + " touch value");
importGroup.QueueReplace(optionsDrawName, optionsDraw);

foreach (string createName in new[]
{
    "gml_Object_obj_mobilecontrols_Create_0",
    "gml_Object_obj_mobilebuttons_Create_0"
})
{
    string source = GetDecompiledText(createName);
    source = ReplaceOnce(source, "active_key = -1;\nif (file_exists(",
        "active_key = -1;\n" +
        "global.UT_CONFIG_TOUCH = 0;\n" +
        "if (!file_exists(\"touchvisibility_v2.ini\"))\n" +
        "{\n" +
        "    ini_open(\"touchvisibility.ini\");\n" +
        "    ini_write_real(\"CONFIG\", \"visible\", 0);\n" +
        "    ini_close();\n" +
        "    ini_open(\"touchvisibility_v2.ini\");\n" +
        "    ini_write_real(\"CONFIG\", \"migrated\", 1);\n" +
        "    ini_close();\n" +
        "}\n" +
        "else if (file_exists(\"touchvisibility.ini\"))\n" +
        "{\n" +
        "    ini_open(\"touchvisibility.ini\");\n" +
        "    global.UT_CONFIG_TOUCH = ini_read_real(\"CONFIG\", \"visible\", 0);\n" +
        "    ini_close();\n" +
        "}\n" +
        "if (file_exists(", createName + " visibility initialization");

    if (createName == "gml_Object_obj_mobilecontrols_Create_0")
    {
        source += @"
if (zx > 1200) zx -= 480;
if (xx > 1200) xx -= 480;
if (cx > 1200) cx -= 480;
";
    }
    importGroup.QueueReplace(createName, source);
}

foreach (string drawName in new[]
{
    "gml_Object_obj_mobilecontrols_Draw_75",
    "gml_Object_obj_mobilebuttons_Draw_75"
})
{
    string source = GetDecompiledText(drawName);
    Require(!source.Contains("UT_CONFIG_TOUCH", StringComparison.Ordinal),
            drawName + " already contains a visibility patch");
    importGroup.QueueReplace(drawName,
        "if (global.UT_CONFIG_TOUCH == 0) exit;\n" + source);
}

importGroup.Import();
ScriptMessage("Applied FAITH 4:3 camera and touch-overlay option.");
