@echo off
rem Cut The Rug TV - Edge kulon ablakban, automatikus hangos lejatszassal (nem kell kattintani a TV-n)
rem Kulon Edge-profilt hasznal, igy a sajat Edge-edet nem erinti.
start "" msedge --user-data-dir="%LOCALAPPDATA%\CutTheRugTV" --autoplay-policy=no-user-gesture-required --no-first-run --start-fullscreen "https://zorits1.github.io/zk-dance-party/"
