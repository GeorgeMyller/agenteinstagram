import streamlit as st
import os
import tempfile
from dotenv import load_dotenv
from src.instagram.instagram_facade import InstagramFacade
from src.utils.paths import Paths

# Carregar variáveis de ambiente
load_dotenv()

# Configurar o Facade do Instagram
instagram = InstagramFacade(
    access_token=os.getenv('INSTAGRAM_ACCESS_TOKEN'),
    ig_user_id=os.getenv('INSTAGRAM_USER_ID')
)

# Configurar página
st.set_page_config(page_title="Instagram Post Manager", layout="wide")
st.title("Instagram Post Manager")

# Criar tabs
tab1, tab2, tab3, tab4 = st.tabs([
    "Postar Foto", "Postar Reels", 
    "Postar Carrossel", "Status da Fila"
])

# Tab 1: Postar Foto
with tab1:
    st.header("Postar Foto")
    
    # Upload de imagem
    uploaded_file = st.file_uploader("Escolha uma imagem", type=['jpg', 'jpeg', 'png'])
    
    if uploaded_file:
        # Mostrar preview
        st.image(uploaded_file)
        
        # Campo de legenda
        caption = st.text_area(
            "Legenda (opcional)",
            placeholder="Digite uma legenda para sua foto"
        )
        
        # Botão de publicar
        if st.button("Publicar Foto"):
            with st.spinner("Publicando foto..."):
                try:
                    # Salvar arquivo temporariamente
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as temp_file:
                        temp_file.write(uploaded_file.getvalue())
                        temp_path = temp_file.name

                    result = instagram.post_single_photo(temp_path, caption)
                    
                    if result['status'] == 'success':
                        st.success(f"Foto publicada com sucesso! ID: {result['id']}")
                    else:
                        st.error(f"Erro ao publicar foto: {result['message']}")
                finally:
                    # Limpar arquivo temporário
                    if 'temp_path' in locals():
                        os.unlink(temp_path)

# Tab 2: Postar Reels
with tab2:
    st.header("Postar Reels")
    st.info("Funcionalidade em desenvolvimento")

# Tab 3: Postar Carrossel
with tab3:
    st.header("Postar Carrossel")
    
    col1, col2 = st.columns(2)
    carousel_paths = []
    carousel_files = []
    
    with col1:
        # Upload múltiplo
        for i in range(10):  # Instagram permite até 10 imagens
            file_key = f"carousel_file_{i}"
            uploaded = st.file_uploader(
                f"Imagem {i+1}" if i < 2 else f"Imagem {i+1} (opcional)", 
                type=['jpg', 'jpeg', 'png'], 
                key=file_key
            )
            if uploaded:
                carousel_files.append(uploaded)
                with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as temp_file:
                    temp_file.write(uploaded.getvalue())
                    carousel_paths.append(temp_file.name)
        
        caption = st.text_area(
            "Legenda (opcional)",
            placeholder="Digite uma legenda para seu carrossel",
            key="carousel_caption"
        )
        
        if len(carousel_paths) >= 2:
            if st.button("Publicar Carrossel"):
                with st.spinner("Publicando carrossel..."):
                    try:
                        result = instagram.post_carousel(carousel_paths, caption)
                        
                        if result['status'] == 'success':
                            st.success(f"Carrossel publicado com sucesso! (ID: {result['id']})")
                        else:
                            st.error(f"Erro ao publicar carrossel: {result['message']}")
                    finally:
                        # Limpar arquivos temporários
                        for path in carousel_paths:
                            os.unlink(path)
        else:
            st.info("Selecione pelo menos 2 imagens para criar um carrossel")

    with col2:
        # Preview area
        if carousel_paths:
            st.write(f"Selecionadas {len(carousel_paths)} imagens")
            for path in carousel_paths[:5]:  # Mostrar até 5 previews
                st.image(path, width=200)

# Tab 4: Status da Fila
with tab4:
    st.header("Status da Fila")
    
    if st.button("Atualizar Status"):
        with st.spinner("Obtendo status..."):
            status = instagram.get_account_status()
            if status:
                st.json(status)
            else:
                st.error("Erro ao obter status da API")
