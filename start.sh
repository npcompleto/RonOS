#!/bin/bash

# Vai nella directory dello script
cd "$(dirname "$0")"

echo "--- Aggiornamento Ron OS ---"
#git pull
echo "--- Aggiornamento completato ---"

# Crea l'ambiente virtuale se non esiste
if [ ! -d "venv" ]; then
    echo "--- Creazione ambiente virtuale... ---"
    python3 -m venv venv
fi

# Attiva l'ambiente virtuale
source venv/bin/activate

# Installa/Aggiorna le dipendenze
echo "--- Verifica dipendenze... ---"
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt



# Funzione per pulire i processi all'uscita (CTRL+C)
cleanup() {
    echo -e "\n--- Spegnimento Ron OS in corso... ---"
    kill $FACE_PID $RON_PID 2>/dev/null
    wait $FACE_PID $RON_PID 2>/dev/null
    echo "--- Sistemi spenti. ---"
    exit
}

# Cattura il segnale CTRL+C (SIGINT)
trap cleanup SIGINT

export DISPLAY=:0

echo "--- Avvio Ron OS... ---"
python ron.py $1 $2 $3
RON_PID=$!
echo "--- Ron OS è attivo. Premi CTRL+C per terminare. ---"
# Attende la fine dei processi
wait $RON_PID
