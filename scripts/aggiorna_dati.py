import os
import requests
import pandas as pd
from datetime import datetime, timezone

FILE_STAZIONI = "data/stazioni.csv"
FILE_PORTATE = "data/portate.csv"

# Endpoint pubblico GeoJSON/JSON delle stazioni idrometriche Protezione Civile FVG
URL_FVG_IDRO = "https://monitor.protezionecivile.fvg.it/api/stations/hydro"

# Coefficienti indicativi della scala di deflusso Q = a * (max(0, h - h0))^b
# per convertire il livello idrometrico (m) in portata stimata (m3/s) dove non fornita direttamente.
SCALE_DEFLUSSO = {
    "TAG_VEN": {"a": 145.0, "h0": 0.10, "b": 1.85},
    "TAG_DIG": {"a": 160.0, "h0": 0.15, "b": 1.80},
    "TAG_LAT": {"a": 120.0, "h0": 0.50, "b": 1.75},
    "FEL_MOG": {"a": 85.0,  "h0": 0.10, "b": 1.80},
    "ISO_GOR": {"a": 110.0, "h0": 0.20, "b": 1.75},
    "ISO_GRA": {"a": 130.0, "h0": 0.25, "b": 1.75},
    "NAT_CIV": {"a": 45.0,  "h0": 0.10, "b": 1.70},
    "LIV_SAC": {"a": 55.0,  "h0": 0.30, "b": 1.65},
    "MED_POR": {"a": 40.0,  "h0": 0.20, "b": 1.65},
    "STE_PAL": {"a": 25.0,  "h0": 0.20, "b": 1.55},
}

def livello_a_portata(id_stazione, livello_m):
    if livello_m is None or pd.isna(livello_m):
        return None
    params = SCALE_DEFLUSSO.get(id_stazione, {"a": 50.0, "h0": 0.0, "b": 1.7})
    h_eff = max(0.05, float(livello_m) - params["h0"])
    return round(params["a"] * (h_eff ** params["b"]), 2)

def scarica_dati_fvg(stazioni_df):
    headers = {"User-Agent": "WaterflowAggregatorApp/1.0 (OpenData Hydro Monitor)"}
    righe_estratte = []
    oggi_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    try:
        resp = requests.get(URL_FVG_IDRO, headers=headers, timeout=30)
        resp.raise_for_status()
        payload = resp.json()
        
        # Gestisce sia formato GeoJSON ("features") sia lista JSON diretta
        records = payload.get("features", payload) if isinstance(payload, dict) else payload
        
        # Mappa per codice o nome stazione
        mappa_codici = dict(zip(stazioni_df["codice_fvg"].str.upper(), stazioni_df["id_stazione"]))
        
        for item in records:
            props = item.get("properties", item)
            cod = str(props.get("code", props.get("id", ""))).upper()
            
            if cod in mappa_codici:
                id_staz = mappa_codici[cod]
                # Cerca prima la portata diretta, altrimenti converte il livello idrometrico
                portata = props.get("discharge", props.get("portata"))
                if portata is None:
                    livello = props.get("value", props.get("level", props.get("livello")))
                    portata = livello_a_portata(id_staz, livello)
                
                if portata is not None and float(portata) >= 0:
                    data_misura = str(props.get("timestamp", oggi_str))[:10]
                    righe_estratte.append({
                        "id_stazione": id_staz,
                        "data": data_misura,
                        "portata_m3s": round(float(portata), 2)
                    })
    except Exception as e:
        print(f"Avviso connessione API FVG: {e}")

    return pd.DataFrame(righe_estratte, columns=["id_stazione", "data", "portata_m3s"])

def aggiorna():
    stazioni = pd.read_csv(FILE_STAZIONI)
    
    if os.path.exists(FILE_PORTATE):
        df_storico = pd.read_csv(FILE_PORTATE)
        # Rimuove eventuali vecchi ID di test (ST01..ST04) se non più in stazioni.csv
        df_storico = df_storico[df_storico["id_stazione"].isin(stazioni["id_stazione"])]
    else:
        df_storico = pd.DataFrame(columns=["id_stazione", "data", "portata_m3s"])

    df_nuovi = scarica_dati_fvg(stazioni)
    print(f"Nuove misurazioni FVG acquisite: {len(df_nuovi)}")

    df_finale = pd.concat([df_storico, df_nuovi], ignore_index=True)
    if not df_finale.empty:
        df_finale["data"] = pd.to_datetime(df_finale["data"]).dt.strftime("%Y-%m-%d")
        df_finale = df_finale.drop_duplicates(subset=["id_stazione", "data"], keep="last")
        df_finale = df_finale.sort_values(by=["data", "id_stazione"])

    df_finale.to_csv(FILE_PORTATE, index=False)
    print(f"Database aggiornato: {len(df_finale)} righe totali in {FILE_PORTATE}.")

if __name__ == "__main__":
    aggiorna()
