import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Idrologia FVG - Serie Storiche", layout="wide")
st.title("Monitoraggio Idrografico FVG (1984 – Oggi)")

@st.cache_data(ttl=3600)
def carica_dati():
    stazioni = pd.read_csv("data/stazioni.csv")
    storico = pd.read_parquet("data/storico_fvg.parquet")
    storico["data"] = pd.to_datetime(storico["data"])
    return stazioni, storico

try:
    stazioni, storico = carica_dati()
except Exception as e:
    st.warning("In attesa del primo popolamento del database (`data/storico_fvg.parquet`). Avvia il workflow su GitHub Actions!")
    st.stop()

# --- SIDEBAR: Controlli ---
st.sidebar.header("Parametri di Visualizzazione")

parametro_label = st.sidebar.radio(
    "Grandezza da visualizzare",
    ["Portata (m³/s)", "Livello idrometrico (m)"]
)
col_valore = "portata_m3s" if "Portata" in parametro_label else "livello_m"

bacini = ["Tutti i bacini FVG"] + sorted(stazioni["bacino"].unique().tolist())
bacino_scelto = st.sidebar.selectbox("Bacino Idrografico", bacini)

if bacino_scelto != "Tutti i bacini FVG":
    stazioni_filtrate = stazioni[stazioni["bacino"] == bacino_scelto]
else:
    stazioni_filtrate = stazioni

data_min = storico["data"].min().date()
data_max = storico["data"].max().date()

data_selezionata = st.sidebar.date_input(
    "Data sulla mappa",
    value=data_max,
    min_value=data_min,
    max_value=data_max
)

# --- DATI DEL GIORNO SELEZIONATO ---
df_giorno = storico[storico["data"].dt.date == data_selezionata]
df_mappa = pd.merge(stazioni_filtrate, df_giorno, on="id_stazione", how="inner")

col1, col2 = st.columns([3, 2])

with col1:
    st.subheader(f"{parametro_label} – {data_selezionata.strftime('%d/%m/%Y')}")
    fig_mappa = px.scatter_map(
        df_mappa,
        lat="lat",
        lon="lon",
        size="portata_m3s",
        color=col_valore,
        hover_name="nome",
        hover_data={
            "fiume": True,
            "bacino": True,
            "portata_m3s": ":.2f",
            "livello_m": ":.2f",
            "lat": False,
            "lon": False
        },
        color_continuous_scale=px.colors.sequential.Blues,
        size_max=28,
        zoom=7.8,
        center={"lat": 46.12, "lon": 13.05},
        map_style="carto-positron",
        labels={
            "portata_m3s": "Portata (m³/s)",
            "livello_m": "Livello (m)"
        }
    )
    fig_mappa.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0}, height=580)
    st.plotly_chart(fig_mappa, use_container_width=True)

with col2:
    st.subheader("Analisi Serie Storica")
    stazione_scelta = st.selectbox("Seleziona stazione", stazioni_filtrate["nome"].unique())
    id_sel = stazioni_filtrate[stazioni_filtrate["nome"] == stazione_scelta]["id_stazione"].values[0]

    df_serie = storico[storico["id_stazione"] == id_sel].sort_values("data")

    # Filtro rapido per intervallo anni
    anni_disp = sorted(df_serie["data"].dt.year.unique())
    anno_inizio, anno_fine = st.select_slider(
        "Intervallo anni nel grafico",
        options=anni_disp,
        value=(max(anni_disp[0], anni_disp[-1] - 5), anni_disp[-1])
    )
    df_serie_filtrata = df_serie[
        (df_serie["data"].dt.year >= anno_inizio) & (df_serie["data"].dt.year <= anno_fine)
    ]

    # Metriche sintetiche sul periodo selezionato
    m1, m2, m3 = st.columns(3)
    val_oggi = df_serie[df_serie["data"].dt.date == data_selezionata][col_valore]
    m1.metric("Giorno scelto", f"{val_oggi.values[0]:.2f}" if not val_oggi.empty else "N/D")
    m2.metric("Media periodo", f"{df_serie_filtrata[col_valore].mean():.2f}")
    m3.metric("Massimo periodo", f"{df_serie_filtrata[col_valore].max():.2f}")

    fig_serie = px.line(
        df_serie_filtrata,
        x="data",
        y=col_valore,
        title=f"{stazione_scelta} ({anno_inizio}–{anno_fine})",
        labels={"data": "Data", col_valore: parametro_label}
    )
    if anno_inizio <= data_selezionata.year <= anno_fine:
        fig_serie.add_vline(x=pd.to_datetime(data_selezionata), line_dash="dash", line_color="red")
    st.plotly_chart(fig_serie, use_container_width=True)
