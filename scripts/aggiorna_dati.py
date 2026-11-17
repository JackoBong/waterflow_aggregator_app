import os
import time
import requests
import pandas as pd
from datetime import datetime, timezone

FILE_STAZIONI = "data/stazioni.csv"
FILE_STORICO = "data/storico_fvg.parquet"
FLOOD_API_URL = "https://flood-api.open-meteo.com/v1/flood"

def calcola_livello_m(portata, a, h0, b):
    """Stima il livello idrometrico (m) dalla portata tramite scala di deflusso inversa."""
    if portata is None or pd.isna(portata) or portata <= 0:
        return round(float(h0), 2)
    livello = float(h0) + ((float(portata) / float(a)) ** (1.0 / float(b)))
    return round(livello, 2)

def scarica_serie_stazione(row, start_date, end_date):
    params = {
        "latitude": row["lat"],
        "longitude": row["lon"],
        "daily": "river_discharge",
        "start_date": start_date,
        "end_date": end_date
    }
    resp = requests.get(FLOOD_API_URL, params=params, timeout=45)
    resp.raise_for_status()
    data_json = resp.json()

    daily = data_json.get("daily", {})
    date_list = daily.get("time", [])
    discharge_list = daily.get("river_discharge", [])

    righe = []
    for dt, val in zip(date_list, discharge_list):
        if val is not None:
            q = round(float(val), 2)
            h = calcola_livello_m(q, row["a"], row["h0"], row["b"])
            righe.append({
                "id_stazione": row["id_stazione"],
                "data": dt,
                "portata_m3s": q,
                "livello_m": h
            })
    return pd.DataFrame(righe)

def aggiorna():
    stazioni = pd.read_csv(FILE_STAZIONI)
    oggi_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if os.path.exists(FILE_STORICO):
        df_storico = pd.read_parquet(FILE_STORICO)
        df_storico = df_storico[df_storico["id_stazione"].isin(stazioni["id_stazione"])]
    else:
        df_storico = pd.DataFrame(columns=["id_stazione", "data", "portata_m3s", "livello_m"])

    stazioni_gia_presenti = set(df_storico["id_stazione"].unique())
    lista_nuovi = [df_storico]

    for _, row in stazioni.iterrows():
        id_staz = row["id_stazione"]
        # Se la stazione non ha ancora lo storico, scarica dal 1984-01-01 ad oggi;
        # altrimenti scarica solo gli ultimi 30 giorni per l'aggiornamento quotidiano.
        if id_staz not in stazioni_gia_presenti:
            start_date = "1984-01-01"
            modo = "STORICO COMPLETO (1984-oggi)"
        else:
            start_date = (pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=30)).strftime("%Y-%m-%d")
            modo = "AGGIORNAMENTO (ultimi 30 gg)"

        try:
            df_staz = scarica_serie_stazione(row, start_date, oggi_str)
            if not df_staz.empty:
                lista_nuovi.append(df_staz)
                print(f"[{id_staz} - {row['nome']}] {modo}: {len(df_staz)} giorni scaricati.")
            time.sleep(0.4)  # Pausa cortesia verso l'API
        except Exception as e:
            print(f"[{id_staz}] Errore: {e}")

    df_finale = pd.concat(lista_nuovi, ignore_index=True)
    if not df_finale.empty:
        df_finale["data"] = pd.to_datetime(df_finale["data"]).dt.strftime("%Y-%m-%d")
        df_finale = df_finale.drop_duplicates(subset=["id_stazione", "data"], keep="last")
        df_finale = df_finale.sort_values(by=["id_stazione", "data"])

    df_finale.to_parquet(FILE_STORICO, index=False, compression="snappy")
    print(f"Database Parquet salvato: {len(df_finale):,} righe totali in {FILE_STORICO}.")

if __name__ == "__main__":
    aggiorna()
