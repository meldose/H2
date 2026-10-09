#!/bin/bash
# Interaktive Auswahl der tmuxp-Sessions in tmux/ — einfache Terminal-Liste,
# Pfeiltasten zum Navigieren, Enter zum Starten (tmuxp load hängt sich
# automatisch ein, wie beim direkten Aufruf). Fällt auf eine nummerierte
# Abfrage zurück, falls stdin kein echtes Terminal ist (Pfeiltasten
# brauchen ein tty).
#
# Aufruf: ./launch_h2.sh

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$WORKSPACE_DIR"

# Feste Reihenfolge: zuerst die MuJoCo/DDS-Sessions, dann RViz/MoveIt.
# Kurzbeschreibungen — bei Änderungen auch docs/RUNBOOK.md abgleichen.
ORDER=(
    h2_example
    h2_dds_test
    h2_state_viewer_real
    h2_rviz_static
    h2_rviz_live_sim
    h2_rviz_live_real
    h2_moveit_demo
)
declare -A DESCRIPTIONS=(
    [h2_example]="Sim + Ankle-Swing-Steuerung + Monitor"
    [h2_dds_test]="Sim + rohes Python-DDS-Testskript"
    [h2_state_viewer_real]="Zustandsanzeige, echter Roboter (Interface: h2_interface.env)"
    [h2_rviz_static]="RViz + URDF, manuelle Regler"
    [h2_rviz_live_sim]="Sim + RViz mit Live-Daten aus MuJoCo"
    [h2_rviz_live_real]="RViz mit Live-Daten, echter Roboter (Interface: h2_interface.env)"
    [h2_moveit_demo]="MoveIt-Demo (nur simulierte Ausführung)"
)

# Bekannte Sessions in fester Reihenfolge, danach noch nicht gelistete
# tmux/*.tmuxp.yaml-Dateien alphabetisch anhängen.
names=()
for name in "${ORDER[@]}"; do
    [ -e "tmux/${name}.tmuxp.yaml" ] && names+=("$name")
done
for f in tmux/*.tmuxp.yaml; do
    [ -e "$f" ] || continue
    name="$(basename "$f" .tmuxp.yaml)"
    printf '%s\n' "${names[@]}" | grep -qxF "$name" || names+=("$name")
done

if [ ${#names[@]} -eq 0 ]; then
    echo "Keine tmuxp-Session-Dateien in tmux/ gefunden." >&2
    exit 1
fi

label() {
    local name="$1" desc="${DESCRIPTIONS[$1]:-}"
    if [ -n "$desc" ]; then
        printf '%s — %s' "$name" "$desc"
    else
        printf '%s' "$name"
    fi
}

chosen=""

if [ -t 0 ]; then
    n=${#names[@]}
    selected=0

    draw() {
        for i in "${!names[@]}"; do
            if [ "$i" -eq "$selected" ]; then
                printf '\033[7m> %s\033[0m\033[K\n' "$(label "${names[$i]}")"
            else
                printf '  %s\033[K\n' "$(label "${names[$i]}")"
            fi
        done
    }

    echo "Session auswählen (Pfeiltasten + Enter, q zum Abbrechen):"
    echo
    draw
    tput civis
    trap 'tput cnorm' EXIT

    while true; do
        IFS= read -rsn1 key
        if [ "$key" = $'\x1b' ]; then
            read -rsn2 -t 0.05 rest || true
            key+="$rest"
        fi
        case "$key" in
        $'\x1b[A') # hoch
            selected=$(((selected - 1 + n) % n))
            ;;
        $'\x1b[B') # runter
            selected=$(((selected + 1) % n))
            ;;
        $'\x0d' | $'\x0a' | "") # Enter
            break
            ;;
        q | Q)
            tput cnorm
            echo "Abgebrochen."
            exit 0
            ;;
        esac
        tput cuu "$n"
        draw
    done

    tput cnorm
    chosen="${names[$selected]}"
    echo
else
    echo "Session auswählen:"
    display=()
    for name in "${names[@]}"; do
        display+=("$(label "$name")")
    done
    PS3="Nummer eingeben: "
    select opt in "${display[@]}"; do
        if [ -n "${opt:-}" ]; then
            chosen="${names[$((REPLY - 1))]}"
            break
        fi
        echo "Ungültige Auswahl, nochmal versuchen."
    done
fi

file="tmux/${chosen}.tmuxp.yaml"
if [ ! -f "$file" ]; then
    echo "Fehler: $file nicht gefunden." >&2
    exit 1
fi

echo "Starte $file ..."
exec tmuxp load "$file"
