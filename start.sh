#!/bin/bash

if [ "$1" = "--rotate" ]; then
    wlr-randr --output HDMI-A-1 --transform 270
fi
# Vai nella directory dello script
cd "$(dirname "$0")"

ENV_NAME="ron311"

#echo "--- Aggiornamento Ron OS ---"
#git pull
#echo "--- Aggiornamento completato ---"

# Inizializza conda nel contesto dello script
source "$(conda info --base)/etc/profile.d/conda.sh"

# Crea ambiente conda se non esiste
if ! conda env list | awk '{print $1}' | grep -qx "$ENV_NAME"; then
    echo "--- Creazione ambiente conda ($ENV_NAME) con Python 3.11 ---"
    conda create -y -n "$ENV_NAME" python=3.11
fi

# Attiva ambiente
conda activate "$ENV_NAME"

# Installa/Aggiorna dipendenze
echo "--- Verifica dipendenze... ---"
python -m pip install --quiet --upgrade pip setuptools wheel
python -m pip install --quiet -r requirements.txt

# Funzione per pulire i processi all'uscita (CTRL+C)
cleanup() {
    echo -e "\n--- Spegnimento Ron OS e PWA in corso... ---"
    pkill -f "python ron.py" -9
    if [ -n "$PWA_PID" ]; then
        kill -9 $PWA_PID 2>/dev/null
    fi
    pkill -f "vite" -9
    echo "--- Sistemi spenti. ---"
    exit
}

# Cattura il segnale CTRL+C
trap cleanup SIGINT

export DISPLAY=:0

echo "--- Aggiornamento Database... ---"
python db.py
echo "--- Database aggiornato. ---"

echo "--- Avvio PWA WebApp... ---"
cd pwa
npm run dev > /dev/null 2>&1 &
PWA_PID=$!
cd ..

echo "--- Avvio Ron OS... ---"
python ron.py "$1" "$2" "$3" "$4" "$5" "$6" &
RON_PID=$!

echo "--- Premi CTRL+C per terminare. ---"

# Attende la fine del processo
wait $RON_PID
