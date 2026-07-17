import streamlit as st
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
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
    
    /* Títulos em Dourado */
    h1, h2, h3, h4 {
        color: #FFB81C !important; 
        font-family: 'Courier New', Courier, monospace;
    }
    
    /* Textos secundários e rótulos em Ciano */
    p, label, .stRadio > label {
        color: #00E5FF !important; 
    }
    
    /* Botões principais - Púrpura tático com texto Verde Radar */
    .stButton > button {
        background-color: #4A148C; 
        color: #00FF33 !important; 
        border: 1px solid #00E5FF;
        border-radius: 4px;
        font-weight: bold;
        transition: all 0.3s ease;
    }
    
    /* Efeito Hover dos botões */
    .stButton > button:hover {
        background-color: #00FF33;
        color: #4A148C !important;
        border: 1px solid #FFB81C;
        box-shadow: 0 0 10px #00FF33;
    }
    
    /* Caixas de seleção */
    div[data-baseweb="select"] > div {
        background-color: #0A2F60;
        color: #00E5FF;
        border-color: #00E5FF;
    }
    
    /* Upload area */
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
            if fonte == "SPOT" and ("xls" in nome_arquivo):
                # O SPOT insere metadados nas primeiras linhas. Lemos a partir da linha 4
                df = pd.read_excel(arquivo, skiprows=4, sheet_name=0)
                # Limpa colunas totalmente vazias criadas por formatação corrompida
                df = df.dropna(how='all', axis=1)
                
            elif fonte == "Global Fishing Watch (GFW)" and ("csv" in nome_arquivo):
                df = pd.read_csv(arquivo)
                
            elif "csv" in nome_arquivo:
                df = pd.read_csv(arquivo)
                
            else:
                df = pd.read_excel(arquivo)
                
            # Padronização de Colunas de Coordenadas para WGS84
            # Mapeamento dinâmico ignorando case e espaços
            colunas_map = {col.strip().lower(): col for col in df.columns}
            
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
        
    # Fusão de todas as tabelas
    df_final = pd.concat(lista_dfs, ignore_index=True)
    
    # Detecção e Exclusão de Séries Históricas Sobrepostas
    colunas_tempo = ['Time Range', 'DataHora', 'timestamp', 'Entry timestamp', 'Data', 'Time']
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
# GERAÇÃO DE OUTPUTS GEOSPACIAIS
# ==========================================
def gerar_download(df, formato, software):
    # Compatibilização ArcGis Pro (remove espaços e caracteres inválidos nos atributos)
    if software == "ArcGIS Pro (3.5.0+)":
        df.columns = df.columns.str.replace(' ', '_', regex=False).str.replace(r'[^\w\s]', '', regex=True)
        
    tem_coord = 'Latitude' in df.columns and 'Longitude' in df.columns
    
    if tem_coord and formato in ["GeoJSON"]:
        df['Latitude'] = pd.to_numeric(df['Latitude'], errors='coerce')
        df['Longitude'] = pd.to_numeric(df['Longitude'], errors='coerce')
        df = df.dropna(subset=['Latitude', 'Longitude'])
        
        geometry = [Point(xy) for xy in zip(df['Longitude'], df['Latitude'])]
        gdf = gpd.GeoDataFrame(df, geometry=geometry, crs="EPSG:4326")
    
    buffer = io.BytesIO()
    mime_type = "text/plain"
    extensao = "txt"
    
    if formato == "CSV (XY Table to Point)":
        df.to_csv(buffer, index=False, encoding='utf-8-sig')
        mime_type = "text/csv"
        extensao = "csv"
        
    elif formato == "GeoJSON" and tem_coord:
        buffer.write(gdf.to_json().encode('utf-8'))
        mime_type = "application/geo+json"
        extensao = "geojson"
        
    elif formato == "JSON":
        df.to_json(buffer, orient='records')
        mime_type = "application/json"
        extensao = "json"
        
    elif formato in ["KML", "GPX"]:
        # Exporta como CSV limpo, já que o processamento web de KML puro via Fiona exige dependências C pesadas (GDAL)
        # O CSV resultante importará perfeitamente nos módulos de conversão nativos.
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
        with st.spinner("Decodificando atributos, normalizando coordenadas e expurgando redundâncias históricas..."):
            
            df_processado = processar_arquivos(arquivos_upados, fonte_dados)
            
            if df_processado is not None and not df_processado.empty:
                st.success(f"✅ Fusão e Limpeza Concluídas! O arquivo mestre possui **{len(df_processado)} registros únicos**.")
                
                st.markdown("### Pré-visualização dos Dados Normalizados")
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