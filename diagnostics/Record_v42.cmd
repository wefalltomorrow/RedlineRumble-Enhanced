@echo off
setlocal
python -B "%~dp0record_session.py" --quick --build v42
echo.
echo Recording command finished. Read the result above.
pause
endlocal
