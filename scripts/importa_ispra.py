import os
import requests
import pandas as pd
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

FILE_STAZIONI = "data/stazioni.csv"
FILE_PORTATE = "data/portate.csv"

# Endpoint standard WaterOneFlow di ISPRA HIS Central (Rete Nazionale / BNHS)
ISPRA_WOF_URL = "http://hiscentral.isprambiente.gov.it/hiscentral/webservices/hiscentral.asmx"

def scarica_dato_stazione(id_stazione, codice_rete_ispra, data_inizio, data_fine):
    """
    Interroga un endpoint CSV/API e restituisce un DataFrame [id_stazione, data, portata_m3s].
    Adatta l'URL alla fonte specifica (es. servizio SOS ISPRA o CSV Open Data regionale).
    """
    # Esempio di chiamata REST/CSV standard (sostituisci con l'URL specifico della tua stazione/regione)
    # Qui simuliamo il parsing di una risposta tabellare; vedi nota sotto per i parametri ISPRA/ARPA.
    nuove_righe = []
    
    # --- ESEMPIO CON CHIAMATA HTTP GENERICA A UN SERVIZIO CSV ---
    # url = f"https://esempio-portale-idro.it/api/dati?stazione={codice_rete_ispra}&dal={data_inizio}&al={data_fine}"
    # resp = requests.get(url, timeout=30)
    # resp.raise_for_status()
    # ... parsing della risposta ...
    
    return pd.DataFrame(nuove_righe, columns=["id_stazione", "data", "portata_m3s"])

def aggiorna():
    stazioni = pd.read_csv(FILE_STAZIONI)
    
    # Carica lo storico esistente se presente
    if os.path.exists(FILE_PORTATE):
        df_storico = pd.read_csv(FILE_PORTATE)
    else:
        df_storico = pd.DataFrame(columns=["id_stazione", "data", "portata_m3s"])

    # Scarica gli ultimi 7 giorni per recuperare eventuali ritardi di trasmissione
    oggi = datetime.utcnow().date()
    data_inizio = (oggi - timedelta(days=7)).strftime("%Y-%m-%d")
    data_fine = oggi.strftime("%Y-%m-%d")

    lista_nuovi = [df_storico]

    for _, row in stazioni.iterrows():
        id_staz = row["id_stazione"]
        # Se in stazioni.csv aggiungi una colonna 'codice_esterno', puoi usarla qui
        codice_ext = row.get("codice_esterno", id_staz)
        
        try:
            df_nuovo = scarica_dato_stazione(id_staz, codice_ext, data_inizio, data_fine)
            if not df_nuovo.empty:
                lista_nuovi.append(df_nuovo)
                print(f"[{id_staz}] Scaricate {len(df_nuovo)} righe.")
        except Exception as e:
            print(f"[{id_staz}] Errore durante lo scaricamento: {e}")

    # Unisce vecchio e nuovo, rimuovendo duplicati (mantiene il dato più recente)
    df_finale = pd.concat(lista_nuovi, ignore_index=True)
    df_finale["data"] = pd.to_datetime(df_finale["data"]).dt.strftime("%Y-%m-%d")
    df_finale = df_finale.drop_duplicates(subset=["id_stazione", "data"], keep="last")
    df_finale = df_finale.sort_values(by=["data", "id_stazione"])

    df_finale.to_csv(FILE_PORTATE, index=False)
    print(f"Aggiornamento completato: {len(df_finale)} righe totali salvate.")

if __name__ == "__main__":
    aggiorna()
