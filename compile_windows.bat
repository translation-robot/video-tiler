@ECHO OFF


SET PATH=C:\Python311;C:\Python311\bin;%PATH%


pyinstaller video-tiler.py  --icon=.\img\app.ico --noconfirm 
REM --windowed


PAUSE
