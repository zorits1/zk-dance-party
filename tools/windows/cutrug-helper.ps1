# Cut The Rug – laptop-segéd a videós tanításhoz (a „Cut The Rug TV” parancsikon indítja, a háttérben fut, rejtve).
# A telefonon / adminban beküldött YouTube-linkeket a laptop (otthoni internet) tölti le – a felhőből a YouTube nem enged –,
# darabokban feltölti a Firebase-be, és onnan a felhő (GitHub) 3D-ben feldolgozza. Napló: %LOCALAPPDATA%\CutTheRug\helper.log
$ErrorActionPreference = 'Continue'
try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch {}
$FB = 'https://zk-dance-party-default-rtdb.europe-west1.firebasedatabase.app'
if ($env:CUTRUG_FB) { $FB = $env:CUTRUG_FB }   # csak teszthez
$D = Join-Path $env:LOCALAPPDATA 'CutTheRug'
New-Item -ItemType Directory -Force -Path $D | Out-Null
$LOG = Join-Path $D 'helper.log'
function Log($m) { try { Add-Content -Path $LOG -Value ((Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' ' + $m) -Encoding UTF8 } catch {} }
$created = $false
$mtx = New-Object System.Threading.Mutex($true, 'Local\CutTheRugHelper', [ref]$created)
if (-not $created) { exit }                      # már fut egy példány
$YT = Join-Path $D 'yt-dlp.exe'
$DENO = Join-Path $D 'deno.exe'

function Cut($s, $n) { $s = [string]$s; if ($s.Length -gt $n) { $s.Substring(0, $n) } else { $s } }
function Put-Json($path, $obj, $method) {
  $json = $obj | ConvertTo-Json -Compress
  Invoke-RestMethod -Method $method -Uri "$FB/$path.json" -Body ([Text.Encoding]::UTF8.GetBytes($json)) -ContentType 'application/json; charset=utf-8' -TimeoutSec 60 | Out-Null
}
function NowMs { [long]([DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()) }

function Ensure-Tools {
  try {
    if (-not (Test-Path $YT)) { Log 'yt-dlp letöltése…'; Invoke-WebRequest -UseBasicParsing 'https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe' -OutFile $YT }
    elseif (((Get-Date) - (Get-Item $YT).LastWriteTime).TotalDays -gt 4) { Log 'yt-dlp frissítése…'; & $YT -U 2>&1 | Out-Null; (Get-Item $YT).LastWriteTime = Get-Date }
  } catch { Log "yt-dlp hiba: $_" }
  try {
    if (-not (Test-Path $DENO) -and -not (Get-Command deno -ErrorAction SilentlyContinue)) {
      Log 'Deno (JavaScript-motor a YouTube-hoz) letöltése…'
      $z = Join-Path $D 'deno.zip'
      Invoke-WebRequest -UseBasicParsing 'https://github.com/denoland/deno/releases/latest/download/deno-x86_64-pc-windows-msvc.zip' -OutFile $z
      Expand-Archive -Force $z $D; Remove-Item $z -ErrorAction SilentlyContinue
    }
  } catch { Log "deno hiba: $_" }
}

function Do-Job($key) {
  $id = $key.Substring(2)
  if ($id -notmatch '^[\w-]{11}$') { return }
  Log "letöltés: $id"
  Put-Json "mocap_idx/$key" @{ bpm = -3; ts = (NowMs) } 'Patch'          # -3: a laptop tölti le
  $out = Join-Path $D "$id.mp4"
  Remove-Item $out -ErrorAction SilentlyContinue
  $a = @('--no-playlist', '--no-progress', '--no-part', '-f', '18/b[height<=480][ext=mp4]/b[ext=mp4]/b', '--max-filesize', '90M',
         '--match-filter', 'duration <= 720', '--remote-components', 'ejs:github', '-o', $out)
  if (Test-Path $DENO) { $a += @('--js-runtimes', "deno:$DENO") }
  $a += "https://www.youtube.com/watch?v=$id"
  $r = (& $YT @a 2>&1 | Out-String)
  if (-not (Test-Path $out)) {
    $last = (($r.Trim() -split "`n") | Where-Object { $_ -match 'ERROR|error' } | Select-Object -Last 1)
    if (-not $last) { $last = 'túl hosszú (max. 12 perc) vagy nem elérhető videó' }
    Log "hiba: $id $last"
    Put-Json "mocap_idx/$key" @{ n = -2; bpm = 0; title = (Cut ('Hiba: a laptop nem tudta letölteni – ' + $last.Trim()) 150); ts = (NowMs) } 'Patch'
    return
  }
  $bytes = [IO.File]::ReadAllBytes($out)
  $cs = 600000; $n = [Math]::Ceiling($bytes.Length / $cs)
  for ($i = 0; $i -lt $n; $i++) {
    $len = [Math]::Min($cs, $bytes.Length - $i * $cs)
    $b64 = [Convert]::ToBase64String($bytes, $i * $cs, $len)
    $ok = $false
    for ($t = 0; $t -lt 3 -and -not $ok; $t++) {
      try { Invoke-RestMethod -Method Put -Uri "$FB/mocap/c_${id}_$i.json" -Body ([Text.Encoding]::ASCII.GetBytes('"' + $b64 + '"')) -ContentType 'application/json' -TimeoutSec 180 | Out-Null; $ok = $true }
      catch { Start-Sleep -Seconds 3 }
    }
    if (-not $ok) { throw "feltöltés megszakadt ($i/$n)" }
  }
  Put-Json "mocap_idx/$key" @{ bpm = -1; ts = (NowMs) } 'Patch'           # -1: feltöltve, a felhő jöhet
  Remove-Item $out -ErrorAction SilentlyContinue
  Log "feltöltve: $id ($n darab, $([Math]::Round($bytes.Length/1MB,1)) MB)"
}

Log 'segéd elindult'
Ensure-Tools
$lastTools = Get-Date
while ($true) {
  try {
    Put-Json 'mocap_idx/h_helper' @{ title = ('laptop-segéd: ' + $env:COMPUTERNAME); ts = (NowMs) } 'Put'   # „él a segéd” jelzés a telefonnak / adminnak
    $idx = Invoke-RestMethod -Uri "$FB/mocap_idx.json" -TimeoutSec 30
    if ($idx) {
      foreach ($p in $idx.PSObject.Properties) {
        $v = $p.Value
        if ($p.Name -like 'q_*' -and $v.n -eq 0 -and ($v.bpm -eq 0 -or ($v.bpm -eq -3 -and ((NowMs) - [long]$v.ts) -gt 1800000))) {
          try { Do-Job $p.Name } catch { Log "hiba: $($p.Name) $_"; try { Put-Json "mocap_idx/$($p.Name)" @{ n = -2; bpm = 0; title = (Cut ("Hiba: $_") 150); ts = (NowMs) } 'Patch' } catch {} }
        }
      }
    }
  } catch { Log "kapcsolat: $_" }
  if (((Get-Date) - $lastTools).TotalHours -gt 12) { Ensure-Tools; $lastTools = Get-Date }
  Start-Sleep -Seconds 15
}
