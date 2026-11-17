import os
import requests
import pandas as pd
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

FILE_STAZIONI = "data/stazioni.csv"
FILE_PORTATE = "data/portate.csv"

# Endpoint ufficiale OGC WaterOneFlow di ISPRA HIS Central
ISPRA_WOF_ENDPOINT = "http://hiscentral.isprambiente.gov.it/hiscentral/webservices/hiscentral.asmx/GetValuesObject"

# Coefficienti scala di deflusso Q = a * (max(0.05, h - h0))^b
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

def scarica_da_ispra_wof(site_code, variable_code, start_date, end_date):
    """Interroga il web service standard WaterOneFlow di ISPRA."""
    params = {
        "location": site_code,
        "variable": variable_code,
        "startDate": start_date,
        "endDate": end_date,
        "authToken": ""
    }
    resp = requests.get(ISPRA_WOF_ENDPOINT, params=params, timeout=30)
    resp.raise_for_status()
    
    root = ET.fromstring(resp.content)
    valori = []
    # Parsing standard WaterML 1.1 (<value dateTime="...">valore</value>)
    for elem in root.iter():
        if elem.tag.endswith("value") and elem.text is not None:
            dt = elem.attrib.get("dateTime", "")[:10]
            try:
                val = float(elem.text.strip())
                if val > -9000 and dt:
                    valori.append((dt, val))
            except ValueError:
                continue
    return valori

def aggiorna():
    stazioni = pd.read_csv(FILE_STAZIONI)
    
    if os.path.exists(FILE_PORTATE):
        df_storico = pd.read_csv(FILE_PORTATE)
        df_storico = df_storico[df_storico["id_stazione"].isin(stazioni["id_stazione"])]
    else:
        df_storico = pd.DataFrame(columns=["id_stazione", "data", "portata_m3s"])

    oggi = datetime.now(timezone.utc).date()
    start_str = (oggi - timedelta(days=10)).strftime("%Y-%m-%d")
    end_str = oggi.strftime("%Y-%m-%d")

    righe_nuove = []

    for _, row in stazioni.iterrows():
        id_staz = row["id_stazione"]
        # Usa il codice rete ISPRA se presente in stazioni.csv (es. "BNHS:1234" o "FVG:VENZ")
        cod_ispra = str(row.get("codice_ispra", "")).strip()
        var_ispra = str(row.get("variabile_ispra", "BNHS:PORTATA")).strip()
        
        if not cod_ispra or cod_ispra == "nan":
            continue

        try:
            serie = scarica_da_ispra_wof(cod_ispra, var_ispra, start_str, end_str)
            for dt, val in serie:
                righe_nuove.append({
                    "id_stazione": id_staz,
                    "data": dt,
                    "portata_m3s": round(val, 2)
                })
            print(f"[{id_staz}] Acquisiti {len(serie)} valori da ISPRA.")
        except Exception as e:
            print(f"[{id_staz}] Errore chiamata ISPRA ({cod_ispra}): {e}")

    df_nuovi = pd.DataFrame(righe_nuove, columns=["id_stazione", "data", "portata_m3s"])
    df_finale = pd.concat([df_storico, df_nuovi], ignore_index=True)

    if not df_finale.empty:
        df_finale["data"] = pd.to_datetime(df_finale["data"]).dt.strftime("%Y-%m-%d")
        df_finale = df_finale.drop_duplicates(subset=["id_stazione", "data"], keep="last")
        df_finale = df_finale.sort_values(by=["data", "id_stazione"])

    df_finale.to_csv(FILE_PORTATE, index=False)
    print(f"Database aggiornato: {len(df_finale)} righe totali in {FILE_PORTATE}.")

if __name__ == "__main__":
    aggiorna()
