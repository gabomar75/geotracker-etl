import streamlit as st
import pandas as pd
import json
import io
import re

# ==========================================
# CONFIGURAÇÃO DE INTERFACE E TEMA GEOINT
# ==========================================
st.set_page_config(page_title="MDA Integrator - Track ETL", page_icon="🛰️", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #041E42; color: #E0F7FA; }
    h1, h2, h3, h4 { color: #FFB81C !important; font-family: 'Courier New', Courier, monospace; }
    p, label { color: #00E5FF !important; }
    .stButton > button { background-color: #4A148C; color: #00FF33 !important; border: 1px solid #00E5FF; }
    </style>
""", unsafe_allow_html=True)

st.title("🛰️ MDA & Narco-Tracking: Data Integrator")
st.markdown("### Plataforma Automatizada de ETL Espacial")

# ==========================================
# FUNÇÕES DE APOIO (CONVERSÃO)
# ==========================================
def dms_to_dd(dms_str):
    """Converte '6° 54'54.00"N' para Graus Decimais."""
    dms_str = str(dms_str)
    match = re.search(r'(\d+)°\s*(\d+)\'(\d+\.?\d*)"([NSEW])', dms_str)
    if not match: return dms_str
    deg, min, sec, dir = match.groups()
    dd = float(deg) + float(min)/60 + float(sec)/3600
    return round(-dd, 6) if dir in ['S', 'W'] else round(dd, 6)

# ==========================================
# PAINEL DE CONTROLE (INTERFACE COMPLETA)
# ==========================================
col1, col2, col3 = st.columns(3)
with col1:
    fonte_dados = st.selectbox("Origem dos Dados:", ["SPOT", "PREPS", "GFW", "SKYlight", "Outros"])
with col2:
    software_destino = st.radio("Software Destino:", ["ArcGIS Pro", "QGIS"])
with col3:
    formato_saida = st.selectbox("Formato de Exportação:", ["CSV", "GeoJSON", "JSON", "KML", "GPX"])

arquivos_upados = st.file_uploader("Arraste os arquivos aqui", accept_multiple_files=True)

# ==========================================
# PROCESSAMENTO TÁTICO
# ==========================================
if arquivos_upados and st.button("🚀 INICIAR PROCESSAMENTO"):
    lista_dfs = []
    for arquivo in arquivos_upados:
        # Lógica de Leitura
        if fonte_dados == "SPOT":
            df_raw = pd.read_excel(arquivo, header=None)
            mask = df_raw.apply(lambda row: row.astype(str).str.contains('Lat/Lng', case=False, na=False).any(), axis=1)
            idx = df_raw[mask].index[0]
            df = pd.read_excel(arquivo, header=idx)
            # Divisão de Lat/Lng SPOT
            lat_lng_col = next((c for c in df.columns if 'lat' in str(c).lower()), None)
            df[['Latitude', 'Longitude']] = df[lat_lng_col].astype(str).str.split(',', n=1, expand=True)
        else:
            df = pd.read_excel(arquivo) if 'xls' in arquivo.name.lower() else pd.read_csv(arquivo)
            
        # Conversão de DMS para DD (essencial para PREPS)
        for col in ['Latitude', 'Longitude']:
            if col in df.columns:
                df[col] = df[col].apply(dms_to_dd)
        
        lista_dfs.append(df)

    df_final = pd.concat(lista_dfs, ignore_index=True).drop_duplicates()
    
    # Compatibilização de Cabeçalho (ArcGIS)
    if software_destino == "ArcGIS Pro":
        df_final.columns = df_final.columns.str.replace(' ', '_', regex=False).str.replace(r'[^\w\s]', '', regex=True)

    # Exibição e Download
    st.success(f"Processado: {len(df_final)} registros.")
    st.dataframe(df_final.head())
    
    buffer = io.BytesIO()
    df_final.to_csv(buffer, index=False, encoding='utf-8-sig')
    st.download_button("⬇️ BAIXAR ARQUIVO UNIFICADO", buffer.getvalue(), f"TrackData_{fonte_dados}.csv", "text/csv")
