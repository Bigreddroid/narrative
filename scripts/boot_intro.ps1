# ============================================================
#  The Narrative - boot intro (Windows / PowerShell + cmd VT)
#  Glitch "hacker uplink" theatre that greets: hello mithra
#  Hacker-movie aesthetic only - no third-party brand names.
#  Fast (~2-3s) and skippable: press any key to jump to the end.
# ============================================================

$ESC = [char]27
$GRN = "$ESC[38;5;46m"   # bright green
$CYN = "$ESC[38;5;51m"   # cyan
$DIM = "$ESC[38;5;28m"   # dim green
$RED = "$ESC[38;5;196m"  # alert red
$RST = "$ESC[0m"
$CLR = "$ESC[2J$ESC[H"   # clear + home

# Try to enable ANSI/VT on legacy conhost; harmless if already on.
try { $null = [Console]::OutputEncoding } catch {}

function Skip {
  # KeyAvailable throws when there is no real console (e.g. redirected
  # input). Treat that as "no key pressed" so the intro still plays.
  try { return [Console]::KeyAvailable } catch { return $false }
}
function Nap($ms) { if (-not (Skip)) { Start-Sleep -Milliseconds $ms } }

Write-Host $CLR -NoNewline

# --- glitch flicker before the logo locks in ---
$glitch = @('#@%&*!?01', '01<>/\|[]', '__--==~~^', '01101001x')
if (-not (Skip)) {
  for ($i = 0; $i -lt 5; $i++) {
    $line = -join (1..46 | ForEach-Object { $glitch[$i % $glitch.Length][(Get-Random -Max 8)] })
    Write-Host "$DIM$line$RST"
    Nap 40
    if (Skip) { break }
  }
}

$banner = @(
 '            oooooooooooooooooooooooooooooooooooooooooooooo',
 '   ooo$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$ooo',
 '  $$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$',
 ' o$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$o',
 ' $$$$$   $$$"    "$$$$$"    "$     $     $  "$  $$$$$"    "$  "$  $$$',
 ' $$$$"   "$$  $$oo$$$$$  $$oo$  $$$$  $$$$   "  $$$$$  $$  $   "  $$$',
 'o$$$$  $  $$o    "$$$$$o    "$    $$     $      $$$$$  $$  $      $$$o',
 '$$$$   o   $""$$  $$$$$""$$  $  $$$$  $$$$  o   $$$$$  $$  $  o   $$$$',
 '$$$$  $$$  $o    o$$$$$o    o$     $     $  $o  $$$$$o    o$  $o  $$$$',
 '$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$',
 '$$$$""""""""""""""""""""""""""""""""""""""$$$$$$$$$$$$""""""""""""$$$$',
 '$$$$                                      "$$$$$$$$$$"           o$$$$',
 '$$$$                                       "$$$$$$$$"           o$$$$$',
 '$$$$                                        $$$$$$$$            $$$$$$',
 '$$$$$$$$$$$$$           $$$$$$$$$            $$$$$$            $$$$$$$',
 '$$$$$$$$$$$$$           $$$$$$$$$$            $$$$            $$$$$$$$',
 '$$$$$$$$$$$$$           $$$$$$$$$$$           "$$"           $$$$$$$$$',
 '$$$$$$$$$$$$$           $$$$$$$$$$$o           ""           o$$$$$$$$$',
 '$$$$$$$$$$$$$           $$$$$$$$$$$$o                      o$$$$$$$$$$',
 '$$$$$$$$$$$$$           $$$$$$$$$$$$$o                    o$$$$$$$$$$$',
 '$$$$$$$$$$$$$           $$$$$$$$$$$$$$o                  o$$$$$$$$$$$$',
 '"$$$$$$$$$$$$           $$$$$$$$$$$$$$$                  $$$$$$$$$$$$"',
 ' $$$$$$$$$$$$           $$$$$$$$$$$$$$$$                $$$$$$$$$$$$$',
 ' $$$$$$$$$$$$           $$$$$$$$$$$$$$$$$              $$$$$$$$$$$$$$',
 ' "$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$"',
 '  $$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$',
 '   """$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$"""',
 '            """"""""""""""""""""""""""""""""""""""""""""""'
)
Write-Host ""
foreach ($row in $banner) {
  Write-Host "$CYN$row$RST"
  Nap 18
}
Write-Host "$DIM        t h e   n a r r a t i v e   b e t a$RST"
Write-Host ""
Nap 120

# --- "hello mithra" graffiti wordmark (figlet 'graffiti' font; quote-free art) ---
$hi = @(
 '      .__           .__  .__',
 '      |  |__   ____ |  | |  |   ____',
 '      |  |  \_/ __ \|  | |  |  /  _ \',
 '      |   Y  \  ___/|  |_|  |_(  <_> )',
 '      |___|  /\___  >____/____/\____/',
 '           \/     \/',
 '         _____  ._________________ _____________    _____',
 '        /     \ |   \__    ___/   |   \______   \  /  _  \',
 '       /  \ /  \|   | |    | /    ~    \       _/ /  /_\  \',
 '      /    Y    \   | |    | \    Y    /    |   \/    |    \',
 '      \____|__  /___| |____|  \___|_  /|____|_  /\____|__  /',
 '              \/                    \/        \/         \/'
)
foreach ($row in $hi) { Write-Host "$CYN$row$RST"; Nap 28 }
Write-Host ""
Nap 100

# --- typewriter boot log ---
$lines = @(
  @("$GRN> ", "hello mithra", "$CYN"),
  @("$GRN> ", "establishing secure uplink...", "$GRN"),
  @("$GRN> ", "decrypting world feed...", "$GRN"),
  @("$GRN> ", "syncing consequence graph...", "$GRN")
)
foreach ($l in $lines) {
  Write-Host $l[0] -NoNewline
  $txt = $l[1]; $col = $l[2]
  if (Skip) {
    Write-Host "$col$txt$RST"
  } else {
    foreach ($ch in $txt.ToCharArray()) {
      Write-Host "$col$ch$RST" -NoNewline
      Nap 12
    }
    Write-Host ""
  }
  Nap 90
}

# --- progress bar ---
Write-Host ""
$bar = ""
for ($p = 0; $p -le 100; $p += 5) {
  $filled = [int]($p / 5)
  $bar = ('#' * $filled) + ('.' * (20 - $filled))
  Write-Host "`r$GRN> [$CYN$bar$GRN] $p%  $RST" -NoNewline
  Nap 25
}
Write-Host ""
Write-Host ""
Nap 100

# --- street art: spray the wall while it boots ---
$tag = @(
 '            **********',
 '        ****          ****',
 '      ** **   *  **       **',
 '    ********  **  **   *    **',
 '  **  *********** **      ******',
 ' **    *********         ********',
 '**     ********          ****   **',
 '**      ***** *            *    **',
 '**       ***              ***** **',
 '**         **            *********',
 '**           **          *********',
 '**          ******        ********',
 ' **         ********        *****',
 '  **        *******           **',
 '    **       ******         **',
 '      **      ****        **',
 '        ****  **      ****',
 '            **********'
)
foreach ($row in $tag) { Write-Host "$GRN$row$RST"; Nap 12 }
Write-Host ""
# Art with mixed ' " \ chars: a single-quoted here-string keeps every byte literal.
$street = (@'
                   ;;\\/;;;;;;;;
                   ;;;;;;;;;;;;;;;;;
                ;;;;;;;;;;;;     ;;;;;
               ;;;;;    ;;;         \;;
              ;;;;;      ;;          |;
             ;;;;         ;          |
             ;;;                     |
              ;;                     )
               \    ~~~~ ~~~~~~~    /
                \    ~~~~~~~  ~~   /
              |\ \                / /|
               \\| %%%%%    %%%%% |//
              [[====================]]
               | |  ^          ^  |
               | | :@: |/  \| :@: | |
                \______/\  /\______/
                 |     (@\/@)     |
                /                  \
               /  ;-----\  ______;  \
               \         \/         /
                )                  (
               /                    \
               \__                  /
                \_                _/
                 \______/\/\______/
                  _|    /--\    |_
                 /%%\  /"'"'\  /%%\
  ______________/%%%%\/\'"'"/\/%%%%\______________
 / :  :  :  /  .\%%%%%%%\"'/%%%%%%%/.  \  :  :  : \
)  :  :  :  \.  .\%%%%%%/'"\%%%%%%/.  ./  :  :  :  (
'@) -split '\r?\n'
foreach ($row in $street) { Write-Host "$GRN$row$RST"; Nap 12 }
Write-Host ""

Write-Host "$GRN  +----------------------------------------+$RST"
Write-Host "$GRN  |    $CYN ACCESS GRANTED $GRN                      |$RST"
Write-Host "$GRN  +----------------------------------------+$RST"
Nap 250

# drain any skip keypress so it doesn't leak into the launcher
try { while ([Console]::KeyAvailable) { [void][Console]::ReadKey($true) } } catch {}
Write-Host $RST -NoNewline
