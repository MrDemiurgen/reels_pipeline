Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")

scriptDir = FSO.GetParentFolderName(WScript.ScriptFullName)
pythonw = """" & scriptDir & "\.venv\Scripts\pythonw.exe"""
app = """" & scriptDir & "\ui_app.py"""

WshShell.CurrentDirectory = scriptDir
WshShell.Run pythonw & " " & app, 0, False