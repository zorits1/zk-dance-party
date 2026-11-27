@echo off
rem Cut The Rug TV - Edge kulon ablakban, automatikus hangos lejatszassal (nem kell kattintani a TV-n),
rem es a hatterben a videos tanitas laptop-segedje (a telefonon bekuldott YouTube-linkeket ez tolti le).
rem Kulon Edge-profilt hasznal, igy a sajat Edge-edet nem erinti.
set "D=%LOCALAPPDATA%\CutTheRug"
if not exist "%D%" mkdir "%D%"
powershell -NoProfile -ExecutionPolicy Bypass -Command "try{[Net.ServicePointManager]::SecurityProtocol='Tls12';Invoke-WebRequest -UseBasicParsing 'https://zorits1.github.io/zk-dance-party/tools/windows/cutrug-helper.ps1' -OutFile '%D%\cutrug-helper.ps1'}catch{}"
if exist "%D%\cutrug-helper.ps1" start "" /min powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%D%\cutrug-helper.ps1"
start "" msedge --user-data-dir="%LOCALAPPDATA%\CutTheRugTV" --autoplay-policy=no-user-gesture-required --no-first-run --start-fullscreen "https://zorits1.github.io/zk-dance-party/"
