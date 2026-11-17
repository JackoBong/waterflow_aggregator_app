import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Monitoraggio Portate Fluviali", layout="wide")
st.title("Monitoraggio Interattivo delle Portate Fluviali")

@st.cache_data(ttl=600)
def carica_dati():
    stazioni = pd.read_csv("data/stazioni.csv")
    portate = pd.read_csv("data/portate.csv")
    portate["data"] = pd.to_datetime(portate["data"])
    return stazioni, portate

stazioni, portate = carica_dati()

# --- SIDEBAR: Filtri e Slider Temporale ---
st.sidebar.header("Filtri")
bacini = ["Tutti"] + sorted(stazioni["bacino"].unique().tolist())
bacino_scelto = st.sidebar.selectbox("Distretto / Bacino", bacini)

if bacino_scelto != "Tutti":
    stazioni = stazioni[stazioni["bacino"] == bacino_scelto]

date_disponibili = sorted(portate["data"].dt.date.unique())
data_selezionata = st.sidebar.select_slider(
    "Seleziona la data",
    options=date_disponibili,
    value=date_disponibili[-1]
)

# --- MAPPA E GRAFICO ---
df_giorno = portate[portate["data"].dt.date == data_selezionata]
df_mappa = pd.merge(stazioni, df_giorno, on="id_stazione", how="inner")

col1, col2 = st.columns([3, 2])

with col1:
    st.subheader(f"Portate registrate il {data_selezionata}")
    fig_mappa = px.scatter_map(
        df_mappa,
        lat="lat",
        lon="lon",
        size="portata_m3s",
        color="portata_m3s",
        hover_name="nome",
        hover_data={"fiume": True, "portata_m3s": ":.2f", "lat": False, "lon": False},
        color_continuous_scale=px.colors.sequential.Blues,
        size_max=30,
        zoom=5,
        center={"lat": 42.5, "lon": 12.5},
        map_style="carto-positron",
        labels={"portata_m3s": "Portata (m³/s)"}
    )
    fig_mappa.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0}, height=550)
    st.plotly_chart(fig_mappa, use_container_width=True)

with col2:
    st.subheader("Serie storica della stazione")
    stazione_scelta = st.selectbox("Seleziona stazione", stazioni["nome"].unique())
    id_sel = stazioni[stazioni["nome"] == stazione_scelta]["id_stazione"].values[0]

    df_serie = portate[portate["id_stazione"] == id_sel].sort_values("data")

    fig_serie = px.line(
        df_serie,
        x="data",
        y="portata_m3s",
        markers=True,
        title=f"Andamento portate - {stazione_scelta}",
        labels={"data": "Data", "portata_m3s": "Portata (m³/s)"}
    )
    fig_serie.add_vline(x=pd.to_datetime(data_selezionata), line_dash="dash", line_color="red")
    st.plotly_chart(fig_serie, use_container_width=True)
