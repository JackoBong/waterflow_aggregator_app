import pandas as pd
import glob
import os

# Supponiamo che tu abbia messo i CSV scaricati da ISPRA in una cartella "raw_ispra/"
# rinominandoli con l'ID della stazione, es: "ST01.csv", "ST02.csv"

lista_df = []

for file_path in glob.glob("raw_ispra/*.csv"):
    id_stazione = os.path.splitext(os.path.basename(file_path))[0]
    
    # ISPRA usa spesso il punto e virgola (;) e righe di intestazione iniziali.
    # Adatta 'skiprows' in base a quante righe di metadati ha il tuo file ISPRA
    df = pd.read_csv(file_path, sep=";", comment="#")
    
    # Rinomina le prime due colonne (Data e Valore)
    df = df.iloc[:, :2]
    df.columns = ["data", "portata_m3s"]
    
    # Pulizia dati: converte date, sostituisce eventuali virgole decimali con il punto, rimuove valori nulli (-9999)
    df["data"] = pd.to_datetime(df["data"]).dt.strftime("%Y-%m-%d")
    df["portata_m3s"] = pd.to_numeric(df["portata_m3s"].astype(str).str.replace(",", "."), errors="coerce")
    df = df[df["portata_m3s"] >= 0]
    
    df["id_stazione"] = id_stazione
    lista_df.append(df[["id_stazione", "data", "portata_m3s"]])

# Unisce tutto e salva nel file usato dall'app Streamlit
df_finale = pd.concat(lista_df, ignore_index=True)
df_finale.to_csv("data/portate.csv", index=False)
print(f"Fatto! Esportate {len(df_finale)} righe in data/portate.csv")
