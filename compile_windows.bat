@ECHO OFF


SET PATH=C:\Python311;C:\Python311\bin;%PATH%


pyinstaller --clean src\video-tiler.py  --icon=tiler.ico --noconfirm 
REM --windowed


PAUSE
