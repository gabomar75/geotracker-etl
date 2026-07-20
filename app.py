import streamlit as st
import pandas as pd
import json
import io

# ==========================================
# CONFIGURAÇÃO DE INTERFACE E TEMA GEOINT
# ==========================================
st.set_page_config(
    page_title="MDA Integrator - Track ETL", 
    page_icon="🛰️", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# Customização CSS de alta performance visual
st.markdown("""
    <style>
    /* Fundo principal - Azul Marinho Profundo */
    .stApp {
        background-color: #041E42; 
        color: #E0F7FA; 
    }
    
    h1, h2, h3, h4 {
        color: #FFB81C !important; 
        font-family: 'Courier New', Courier, monospace;
    }
    
    p, label, .stRadio > label {
        color: #00E5FF !important; 
    }
    
    .stButton > button {
        background-color: #4A148C; 
        color: #00FF33 !important; 
        border: 1px solid #00E5FF;
        border-radius: 4px;
        font-weight: bold;
        transition: all 0.3s ease;
    }
    
    .stButton > button:hover {
        background-color: #00FF33;
        color: #4A148C !important;
        border: 1px solid #FFB81C;
        box-shadow: 0 0 10px #00FF33;
    }
    
    div[data-baseweb="select"] > div {
        background-color: #0A2F60;
        color: #00E5FF;
        border-color: #00E5FF;
    }
    
    div[data-testid="stFileUploadDropzone"] {
        background-color: #0A2F60;
        border: 2px dashed #00E5FF;
    }
    </style>
""", unsafe_allow_html=True)

st.title("🛰️ MDA & Narco-Tracking: Data Integrator")
st.markdown("### Plataforma Automatizada de ETL Espacial (WGS84)")
st.markdown("---")

# ==========================================
# PAINEL DE CONTROLE
# ==========================================
col1, col2, col3 = st.columns(3)

with col1:
    fonte_dados = st.selectbox(
        "1. Origem dos Dados Brutos:",
        ["SPOT", "PREPS", "Global Fishing Watch (GFW)", "SKYlight", "Genérico"]
    )

with col2:
    software_destino = st.radio(
        "2. Otimizar Cabeçalhos e Estrutura para:",
        ["ArcGIS Pro (3.5.0+)", "QGIS"]
    )
    
with col3:
    formato_saida = st.selectbox(
        "3. Formato de Exportação:",
        ["CSV (XY Table to Point)", "GeoJSON", "JSON", "KML", "GPX"]
    )

st.markdown("<br>", unsafe_allow_html=True)
arquivos_upados = st.file_uploader("Arraste e solte os arquivos aqui (.xls, .xlsx, .csv)", accept_multiple_files=True)

# ==========================================
# MOTOR DE PROCESSAMENTO (ETL)
# ==========================================
@st.cache_data(show_spinner=False)
def processar_arquivos(arquivos, fonte):
    lista_dfs = []
    
    for arquivo in arquivos:
        nome_arquivo = arquivo.name.lower()
        
        try:
            # 1. LEITURA INTELIGENTE E LOCALIZAÇÃO DE CABEÇALHO
            if fonte == "SPOT" and ("xls" in nome_arquivo):
                # O SPOT exporta metadados no topo. Lemos tudo primeiro para achar a tabela real.
                df_raw = pd.read_excel(arquivo, header=None, sheet_name=0)
                
                # Procura dinamicamente a linha que contém "Lat/Lng" ou "Date" ou "Events"
                mask = df_raw.apply(lambda row: row.astype(str).str.contains('Lat/Lng|Latitude|Events|Date', case=False, na=False).any(), axis=1)
                header_idx = df_raw[mask].index
                
                if not header_idx.empty:
                    # Usa a linha encontrada como cabeçalho definitivo
                    df = pd.read_excel(arquivo, header=header_idx[0], sheet_name=0)
                else:
                    df = pd.read_excel(arquivo, skiprows=5, sheet_name=0) # Fallback padrão
                    
                df = df.dropna(how='all', axis=1)
                
            elif fonte == "Global Fishing Watch (GFW)" and ("csv" in nome_arquivo):
                df = pd.read_csv(arquivo)
                
            elif "csv" in nome_arquivo:
                df = pd.read_csv(arquivo)
                
            else:
                df = pd.read_excel(arquivo)
                
            # 2. QUEBRA DE COORDENADAS CONCATENADAS (Típico do SPOT)
            # Verifica se existe uma coluna unificada chamada 'Lat/Lng'
            lat_lng_col = next((col for col in df.columns if 'lat/lng' in str(col).lower() or 'lat / lng' in str(col).lower()), None)
            
            if lat_lng_col:
                # O SPOT junta as coordenadas (ex: "-12.972090, -38.515840"). Quebramos na vírgula.
                df[['Latitude', 'Longitude']] = df[lat_lng_col].astype(str).str.split(',', n=1, expand=True)
                df = df.drop(columns=[lat_lng_col])
                
                # Força a conversão para numérico puro, limpando espaços em branco
                df['Latitude'] = pd.to_numeric(df['Latitude'].str.strip(), errors='coerce')
                df['Longitude'] = pd.to_numeric(df['Longitude'].str.strip(), errors='coerce')

            # 3. PADRONIZAÇÃO FINAL DE NOMES
            colunas_map = {str(col).strip().lower(): col for col in df.columns}
            
            lat_col = colunas_map.get('lat', colunas_map.get('latitude', colunas_map.get('y', None)))
            lon_col = colunas_map.get('lon', colunas_map.get('longitude', colunas_map.get('x', None)))
            
            if lat_col and lon_col:
                df.rename(columns={lat_col: 'Latitude', lon_col: 'Longitude'}, inplace=True)
                
            lista_dfs.append(df)
            
        except Exception as e:
            st.error(f"Falha ao ler {arquivo.name}: {e}")
            return None
            
    if not lista_dfs:
        return None
        
    df_final = pd.concat(lista_dfs, ignore_index=True)
    
    # 4. LIMPEZA DE REDUNDÂNCIAS HISTÓRICAS
    colunas_tempo = ['Time Range', 'DataHora', 'timestamp', 'Entry timestamp', 'Data', 'Time', 'Date']
    colunas_referencia = ['Latitude', 'Longitude']
    
    for col in colunas_tempo:
        if col in df_final.columns:
            colunas_referencia.append(col)
            break
            
    try:
        if len(colunas_referencia) > 2:
            df_final = df_final.drop_duplicates(subset=colunas_referencia, keep='last')
        else:
            df_final = df_final.drop_duplicates()
    except Exception as e:
        st.warning(f"Aviso de limpeza de duplicatas: {e}")
        
    return df_final

# ==========================================
# GERAÇÃO DE OUTPUTS GEOSPACIAIS (NATIVO)
# ==========================================
def gerar_download(df, formato, software):
    if software == "ArcGIS Pro (3.5.0+)":
        # Remove espaços e caracteres especiais dos cabeçalhos para o ArcGIS não dar erro de Field Name
        df.columns = df.columns.str.replace(' ', '_', regex=False).str.replace(r'[^\w\s]', '', regex=True)
        
    tem_coord = 'Latitude' in df.columns and 'Longitude' in df.columns
    
    buffer = io.BytesIO()
    mime_type = "text/plain"
    extensao = "txt"
    
    if formato == "CSV (XY Table to Point)":
        df.to_csv(buffer, index=False, encoding='utf-8-sig')
        mime_type = "text/csv"
        extensao = "csv"
        
    elif formato == "GeoJSON" and tem_coord:
        df_geo = df.dropna(subset=['Latitude', 'Longitude']).copy()
        
        # Garante a conversão caso algo tenha passado
        df_geo['Latitude'] = pd.to_numeric(df_geo['Latitude'], errors='coerce')
        df_geo['Longitude'] = pd.to_numeric(df_geo['Longitude'], errors='coerce')
        df_geo = df_geo.dropna(subset=['Latitude', 'Longitude'])
        
        features = []
        for _, row in df_geo.iterrows():
            try:
                lat = float(row['Latitude'])
                lon = float(row['Longitude'])
                propriedades = row.to_dict()
                
                features.append({
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [lon, lat]
                    },
                    "properties": propriedades
                })
            except:
                continue 
                
        geojson_dict = {
            "type": "FeatureCollection", 
            "features": features
        }
        
        buffer.write(json.dumps(geojson_dict).encode('utf-8'))
        mime_type = "application/geo+json"
        extensao = "geojson"
        
    elif formato == "JSON":
        df.to_json(buffer, orient='records')
        mime_type = "application/json"
        extensao = "json"
        
    elif formato in ["KML", "GPX"]:
        df.to_csv(buffer, index=False, encoding='utf-8-sig') 
        mime_type = "text/csv"
        extensao = "csv"

    return buffer.getvalue(), extensao, mime_type

# ==========================================
# EXECUÇÃO E EXPORTAÇÃO
# ==========================================
if arquivos_upados:
    st.markdown("---")
    if st.button("🚀 INICIAR PROCESSAMENTO TÁTICO", use_container_width=True):
        with st.spinner("Decodificando atributos, localizando coordenadas e expurgando redundâncias históricas..."):
            
            df_processado = processar_arquivos(arquivos_upados, fonte_dados)
            
            if df_processado is not None and not df_processado.empty:
                st.success(f"✅ Fusão e Extração Concluídas! O arquivo mestre possui **{len(df_processado)} registros únicos**.")
                
                st.markdown("### Pré-visualização das Coordenadas Separadas")
                st.dataframe(df_processado.head(10), use_container_width=True)
                
                file_bytes, ext, mime = gerar_download(df_processado, formato_saida, software_destino)
                
                col_down1, col_down2, col_down3 = st.columns([1, 2, 1])
                with col_down2:
                    st.download_button(
                        label=f"⬇️ FAZER DOWNLOAD DO ARQUIVO FINAL (.{ext})",
                        data=file_bytes,
                        file_name=f"TrackData_Integrado_{fonte_dados}_WGS84.{ext}",
                        mime=mime,
                        use_container_width=True
                    )
            else:
                st.error("Falha ao processar os arquivos ou os arquivos estão vazios.")
