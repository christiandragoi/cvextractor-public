' Launch CV Extractor.vbs
' Double-click this file (or pin shortcut to taskbar) to launch the app
' with NO black terminal window visible.

Dim appDir
appDir = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)

Dim shell
Set shell = CreateObject("WScript.Shell")
shell.Run "cmd /c """ & appDir & "\cv_extractor.bat""", 0, False
