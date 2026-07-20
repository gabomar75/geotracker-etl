import streamlit as st
import pandas as pd
import json
import io
import re

# [CSS e CONFIGURAÇÃO DE INTERFACE MANTIDOS]
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

# Funções de Conversão Geodésica
def dms_to_dd(dms_str):
    """Converte formato '6° 54'54.00"N' para Graus Decimais."""
    dms_str = str(dms_str)
    match = re.search(r'(\d+)°\s*(\d+)\'(\d+\.?\d*)"([NSEW])', dms_str)
    if not match:
        return dms_str # Retorna original se não for DMS
    
    deg, min, sec, dir = match.groups()
    dd = float(deg) + float(min)/60 + float(sec)/3600
    if dir in ['S', 'W']: dd *= -1
    return round(dd, 6)

# [MOTOR DE PROCESSAMENTO ATUALIZADO]
@st.cache_data(show_spinner=False)
def processar_arquivos(arquivos, fonte):
    lista_dfs = []
    for arquivo in arquivos:
        df = pd.read_excel(arquivo) if 'xls' in arquivo.name.lower() else pd.read_csv(arquivo)
        
        # Correção de Coordenadas PREPS/SPOT
        for col in ['Latitude', 'Longitude']:
            if col in df.columns:
                df[col] = df[col].apply(dms_to_dd)
        
        # Lógica de extração SPOT (Lat/Lng concat)
        lat_lng_col = next((c for c in df.columns if 'lat' in str(c).lower() and 'lng' in str(c).lower()), None)
        if lat_lng_col:
            df[['Latitude', 'Longitude']] = df[lat_lng_col].astype(str).str.split(',', n=1, expand=True)
            df['Latitude'] = pd.to_numeric(df['Latitude'].apply(dms_to_dd), errors='coerce')
            df['Longitude'] = pd.to_numeric(df['Longitude'].apply(dms_to_dd), errors='coerce')
            
        lista_dfs.append(df)
        
    df_final = pd.concat(lista_dfs, ignore_index=True)
    return df_final.drop_duplicates()

# [INTERFACE DE EXECUÇÃO]
arquivos_upados = st.file_uploader("Carregue os arquivos", accept_multiple_files=True)
if arquivos_upados and st.button("🚀 PROCESSAR PARA ARCGIS/QGIS"):
    df_final = processar_arquivos(arquivos_upados, "PREPS/SPOT")
    csv = df_final.to_csv(index=False, encoding='utf-8-sig').encode('utf-8')
    st.download_button("⬇️ BAIXAR CSV NORMALIZADO", csv, "TrackData_WGS84_Decimal.csv", "text/csv")
