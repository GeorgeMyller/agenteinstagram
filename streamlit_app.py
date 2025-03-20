import streamlit as st
import os
import time
import tempfile
import random
from PIL import Image
from src.services.instagram_send import InstagramSend
from src.instagram.image_validator import InstagramImageValidator
from src.utils.paths import Paths
from src.instagram.filter import FilterImage
from datetime import datetime

st.set_page_config(page_title="Instagram Agent", layout="wide")
st.title('Instagram Agent 📷')
st.caption('Agente para automação de Instagram')

# Inicialização de diretórios necessários
os.makedirs(os.path.join(Paths.ROOT_DIR, "temp_videos"), exist_ok=True)
os.makedirs(os.path.join(Paths.ROOT_DIR, "temp"), exist_ok=True)
assets_dir = os.path.join(Paths.ROOT_DIR, "assets")
os.makedirs(assets_dir, exist_ok=True)

# Define border image with full path
border_image_path = os.path.join(assets_dir, "moldura.png")
if not os.path.exists(border_image_path):
    st.warning(f"⚠️ Aviso: Imagem de borda não encontrada em {border_image_path}")
    border_image_path = None

tab1, tab2, tab3, tab4, tab5 = st.tabs(["Publicar Foto", "Publicar Reels", "Publicar Carrossel", "Monitorar Fila", "Debug"])

with tab1:
    st.header('Publicar Foto no Instagram')
    
    col1, col2 = st.columns([3, 2])
    
    with col1:
        # File uploader
        uploaded_file = st.file_uploader("Escolha uma imagem", type=['jpg', 'jpeg', 'png'], key="photo_uploader")
        
        # Caption input
        caption = st.text_area("Legenda (opcional)", 
                              placeholder="Digite uma legenda para sua foto ou deixe em branco para gerar automaticamente",
                              key="photo_caption")
        
        # Options for AI-enhanced captions
        st.subheader("Opções para legenda gerada por IA")
        col_style, col_person = st.columns(2)
        
        with col_style:
            style_options = st.selectbox(
                'Estilo da legenda',
                ('Divertido e alegre', 'Profissional e sério', 'Inspirador e motivacional', 'Informativo e educativo')
            )
            
        with col_person:
            person_options = st.selectbox(
                'Pessoa do discurso',
                ('Primeira pessoa (eu/nós)', 'Segunda pessoa (você/vocês)', 'Terceira pessoa (ele/ela/eles)')
            )
        
        col_sentiment, col_limit = st.columns(2)
        
        with col_sentiment:
            sentiment = st.select_slider(
                'Sentimento',
                options=['Muito Negativo', 'Negativo', 'Neutro', 'Positivo', 'Muito Positivo'],
                value='Positivo'
            )
            
        with col_limit:
            word_limit = st.slider('Limite de palavras', 30, 300, 150)
            
        col_emoji, col_slang = st.columns(2)
        
        with col_emoji:
            use_emojis = st.toggle('Usar emojis', value=True)
            
        with col_slang:
            use_slang = st.toggle('Usar gírias/linguagem casual', value=True)
        
    with col2:
        # Preview area
        if uploaded_file is not None:
            # Create a temporary file to store the uploaded image
            with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as temp_file:
                temp_file.write(uploaded_file.getvalue())
                image_path = temp_file.name
            
            # Display preview
            st.image(image_path, caption='Preview', use_column_width=True)
            
            # Post button
            if st.button('Post to Instagram', type='primary'):
                with st.spinner('Processing and uploading your image... This may take a while ⏳'):
                    try:
                        # Submit post
                        result = InstagramSend.send_instagram(
                            image_path=image_path,
                            caption=caption,
                            inputs={
                                "estilo": style_options,
                                "pessoa": person_options,
                                "sentimento": sentiment,
                                "tamanho": f"{word_limit} palavras",
                                "genero": "Neutro",
                                "emojs": "sim" if use_emojis else "nao",
                                "girias": "sim" if use_slang else "nao"
                            }
                        )
                        
                        if result:
                            post_id = result.get('id', 'Unknown')
                            permalink = result.get('permalink', '#')
                            
                            st.success(f'Photo posted successfully! 🎉 (ID: {post_id})')
                            if permalink:
                                st.markdown(f'[View your post on Instagram]({permalink})')
                        else:
                            st.error('Failed to post image to Instagram. Check logs for details.')
                    except Exception as e:
                        st.error(f'Error posting to Instagram: {str(e)}')
            
        else:
            st.info('Please upload an image to post')
            st.write("Your photo will appear here for preview")

with tab2:
    st.header('Publicar Reels no Instagram')
    
    col1, col2 = st.columns([3, 2])
    
    with col1:
        # File uploader
        uploaded_file = st.file_uploader("Escolha um vídeo", type=['mp4', 'mov'], key="video_uploader")
        
        # Caption input
        caption = st.text_area("Legenda (opcional)", 
                              placeholder="Digite uma legenda para seu reels ou deixe em branco para gerar automaticamente",
                              key="reels_caption")
        
        # Hashtags input
        hashtags = st.text_input("Hashtags (separadas por vírgula)", 
                                placeholder="Ex: ai, reels, instagram",
                                key="reels_hashtags")
        
        # Options for AI-enhanced captions
        st.subheader("Opções para legenda gerada por IA")
        col_style, col_person = st.columns(2)
        
        with col_style:
            style_options = st.selectbox(
                'Estilo da legenda',
                ('Divertido e alegre', 'Profissional e sério', 'Inspirador e motivacional', 'Informativo e educativo'),
                key="reels_style"
            )
            
        with col_person:
            person_options = st.selectbox(
                'Pessoa do discurso',
                ('Primeira pessoa (eu/nós)', 'Segunda pessoa (você/vocês)', 'Terceira pessoa (ele/ela/eles)'),
                key="reels_person"
            )
        
        col_sentiment, col_limit = st.columns(2)
        
        with col_sentiment:
            sentiment = st.select_slider(
                'Sentimento',
                options=['Muito Negativo', 'Negativo', 'Neutro', 'Positivo', 'Muito Positivo'],
                value='Positivo',
                key="reels_sentiment"
            )
            
        with col_limit:
            word_limit = st.slider('Limite de palavras', 30, 300, 150, key="reels_limit")
            
        col_emoji, col_slang = st.columns(2)
        
        with col_emoji:
            use_emojis = st.toggle('Usar emojis', value=True, key="reels_emoji")
            
        with col_slang:
            use_slang = st.toggle('Usar gírias/linguagem casual', value=True, key="reels_slang")
        
        share_to_feed = st.toggle('Compartilhar no Feed', value=True, key="reels_share_feed")
        
    with col2:
        # Preview area
        if uploaded_file is not None:
            # Create a temporary file to store the uploaded video
            video_path = os.path.join("temp_videos", f"temp-{int(time.time() * 1000)}.mp4")
            os.makedirs(os.path.dirname(video_path), exist_ok=True)
            
            with open(video_path, "wb") as f:
                f.write(uploaded_file.getvalue())
            
            # Display preview
            st.video(video_path)
            
            # Post button
            if st.button('Post Reels to Instagram', type='primary'):
                if uploaded_file is not None:
                    with st.spinner('Processing and uploading your reels... This may take a while ⏳'):
                        try:
                            # Prepare hashtags list
                            hashtags_list = None
                            if hashtags:
                                hashtags_list = [tag.strip() for tag in hashtags.split(',') if tag.strip()]
                            
                            # Submit reels
                            result = InstagramSend.send_reels(
                                video_path=video_path,
                                caption=caption,
                                inputs={
                                    "estilo": style_options,
                                    "pessoa": person_options,
                                    "sentimento": sentiment,
                                    "tamanho": f"{word_limit} palavras",
                                    "genero": "Neutro",
                                    "emojs": "sim" if use_emojis else "nao",
                                    "girias": "sim" if use_slang else "nao",
                                    "hashtags": hashtags_list,
                                    "share_to_feed": share_to_feed
                                }
                            )
                            
                            if result:
                                post_id = result.get('id', 'Unknown')
                                permalink = result.get('permalink', '#')
                                
                                st.success(f'Reels posted successfully! 🎉 (ID: {post_id})')
                                if permalink:
                                    st.markdown(f'[View your reels on Instagram]({permalink})')
                            else:
                                st.error('Failed to post reels to Instagram. Check logs for details.')
                            
                            # Clean up temp file - handled by the service
                        except Exception as e:
                            st.error(f'Error posting reels to Instagram: {str(e)}')
                else:
                    st.error('Please upload a video first.')
        else:
            st.info('Please upload a video to post')
            st.write("Your video will appear here for preview")

# Nova aba para carrossel
with tab3:
    st.header('Publicar Carrossel no Instagram')
    
    col1, col2 = st.columns([3, 2])
    
    with col1:
        # Múltiplos seletores de arquivos (até 10 imagens)
        st.write("Selecione de 2 a 10 imagens para o carrossel")
        
        carousel_files = []
        carousel_paths = []
        
        # Usando uma técnica com múltiplos uploaders
        uploader_cols = st.columns(2)
        for i in range(10):  # Instagram permite até 10 imagens no carrossel
            with uploader_cols[i % 2]:
                file_key = f"carousel_file_{i}"
                uploaded = st.file_uploader(f"Imagem {i+1}", type=['jpg', 'jpeg', 'png'], key=file_key)
                if uploaded:
                    carousel_files.append(uploaded)
                    # Criar arquivo temporário
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as temp_file:
                        temp_file.write(uploaded.getvalue())
                        carousel_paths.append(temp_file.name)
        
        # Caption input
        caption = st.text_area("Legenda (opcional)", 
                              placeholder="Digite uma legenda para seu carrossel ou deixe em branco para gerar automaticamente",
                              key="carousel_caption")
        
        # Options for AI-enhanced captions
        st.subheader("Opções para legenda gerada por IA")
        col_style, col_person = st.columns(2)
        
        with col_style:
            style_options = st.selectbox(
                'Estilo da legenda',
                ('Divertido e alegre', 'Profissional e sério', 'Inspirador e motivacional', 'Informativo e educativo'),
                key="carousel_style"
            )
            
        with col_person:
            person_options = st.selectbox(
                'Pessoa do discurso',
                ('Primeira pessoa (eu/nós)', 'Segunda pessoa (você/vocês)', 'Terceira pessoa (ele/ela/eles)'),
                key="carousel_person"
            )
    
    with col2:
        # Preview area
        if len(carousel_paths) >= 2:
            st.write(f"Selecionadas {len(carousel_paths)} imagens para o carrossel")
            
            # Mostrar previews (no máximo 5 para não sobrecarregar)
            preview_cols = st.columns(min(len(carousel_paths), 5))
            for i, img_path in enumerate(carousel_paths[:5]):
                with preview_cols[i % 5]:
                    st.image(img_path, caption=f'Imagem {i+1}', use_column_width=True)
            
            # Se houver mais de 5 imagens, mostrar uma mensagem
            if len(carousel_paths) > 5:
                st.info(f"+ {len(carousel_paths) - 5} imagens adicionais selecionadas")
            
            # Post button
            if st.button('Publicar Carrossel no Instagram', type='primary'):
                with st.spinner('Processando e publicando seu carrossel... Isso pode demorar um pouco ⏳'):
                    try:
                        # Submit carousel post
                        result = InstagramSend.send_carousel(
                            media_paths=carousel_paths,
                            caption=caption,
                            inputs={
                                "estilo": style_options,
                                "pessoa": person_options,
                                "tamanho": "150 palavras",  # valor padrão
                                "genero": "Neutro"
                            }
                        )
                        
                        if result and result.get("status") == "success":
                            post_id = result.get('post_id', 'Unknown')
                            
                            st.success(f'Carrossel publicado com sucesso! 🎉 (ID: {post_id})')
                        else:
                            st.error('Falha ao publicar carrossel no Instagram. Confira os logs para mais detalhes.')
                    except Exception as e:
                        st.error(f'Erro ao publicar carrossel: {str(e)}')
        else:
            if len(carousel_paths) == 1:
                st.warning('Você precisa selecionar pelo menos 2 imagens para criar um carrossel')
            else:
                st.info('Por favor, selecione pelo menos 2 imagens (máximo 10) para criar um carrossel')

with tab4:
    st.header('Status da Fila')
    
    # Adiciona filtros de data
    col_date, col_refresh = st.columns([3, 1])
    with col_date:
        start_date = st.date_input("Data inicial", datetime.now().date())
        end_date = st.date_input("Data final", datetime.now().date())
    
    with col_refresh:
        st.write("")  # Espaçamento
        if st.button('Atualizar Status', type='primary'):
            stats = InstagramSend.get_queue_stats(start_date=start_date, end_date=end_date)
            recent_jobs = InstagramSend.get_recent_posts(10)  # Aumentado para 10 posts recentes
            
            # Display stats in columns
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Jobs", stats["total_jobs"])
                st.metric("Completados", stats["completed_jobs"])
            with col2:
                st.metric("Falhas", stats["failed_jobs"])
                st.metric("Pendentes", stats["pending_jobs"])
            with col3:
                st.metric("Processando", stats["processing_jobs"])
                st.metric("Rate Limited", stats["rate_limited_posts"])
            with col4:
                processing_speed = stats.get("avg_processing_time", 120)
                remaining_jobs = stats["pending_jobs"] + stats["processing_jobs"]
                est_minutes = int((processing_speed * remaining_jobs) / 60) if remaining_jobs > 0 else 0
                
                st.metric("Tempo Estimado", f"{est_minutes} min" if est_minutes > 0 else "N/A")
                st.metric("Tempo Médio", f"{stats.get('avg_processing_time', 0):.1f}s")
            
            # Taxa de sucesso
            success_rate = (stats["completed_jobs"] / stats["total_jobs"] * 100) if stats["total_jobs"] > 0 else 0
            st.progress(success_rate / 100, text=f"Taxa de Sucesso: {success_rate:.1f}%")
            
            # Display recent jobs with more details
            st.subheader("Posts Recentes")
            if not recent_jobs:
                st.info("Nenhum post recente encontrado.")
            else:
                for job in recent_jobs:
                    with st.expander(f"Post {job.get('job_id', 'Unknown')} - {job.get('status', 'Unknown')}"):
                        col1, col2 = st.columns([1, 2])
                        with col1:
                            if job.get("media_type") == "IMAGE":
                                try:
                                    image_path = job["media_paths"][0] if isinstance(job["media_paths"], list) else job["media_paths"]
                                    if os.path.exists(image_path):
                                        st.image(image_path, width=200)
                                except:
                                    st.write("🖼️ [Imagem não disponível]")
                            elif job.get("content_type") in ["reel", "video"]:
                                st.write("🎬 [Vídeo]")
                            elif job.get("content_type") == "carousel":
                                st.write("🔄 [Carrossel]")
                        
                        with col2:
                            st.write(f"**Status:** {job.get('status', 'Unknown')}")
                            st.write(f"**Criado em:** {job.get('created_at', 'Unknown')}")
                            st.write(f"**Tipo:** {job.get('content_type', 'Unknown')}")
                            if job.get("error"):
                                st.error(f"Erro: {job['error']}")
                            if job.get("result", {}).get("permalink"):
                                st.markdown(f"[Ver no Instagram]({job['result']['permalink']})")

# Nova aba de Debug
with tab5:
    st.header("Ferramentas de Debug")
    
    # Status da API
    with st.expander("Status da API Instagram"):
        if st.button("Verificar Status da API"):
            try:
                from src.instagram.instagram_carousel_service import InstagramCarouselService
                service = InstagramCarouselService()
                usage_info = service.get_app_usage_info()
                
                if usage_info and 'app_usage' in usage_info:
                    st.json(usage_info)
                else:
                    st.error("Não foi possível obter informações de uso da API")
            except Exception as e:
                st.error(f"Erro ao verificar status da API: {str(e)}")
    
    # Verificação de Token
    with st.expander("Verificar Token Instagram"):
        if st.button("Verificar Token"):
            try:
                from src.instagram.instagram_carousel_service import InstagramCarouselService
                service = InstagramCarouselService()
                is_valid, missing_permissions = service.check_token_permissions()
                
                if is_valid:
                    st.success("Token válido! ✅")
                    token_details = service.debug_token()
                    if token_details and 'data' in token_details:
                        data = token_details['data']
                        st.write("Detalhes do Token:")
                        st.write(f"- App ID: {data.get('app_id')}")
                        st.write(f"- Expira em: {datetime.fromtimestamp(data.get('expires_at')).strftime('%Y-%m-%d %H:%M:%S') if data.get('expires_at') else 'Unknown'}")
                        st.write("- Permissões:", ', '.join(data.get('scopes', [])))
                else:
                    st.error(f"Token inválido! Permissões faltando: {', '.join(missing_permissions)}")
            except Exception as e:
                st.error(f"Erro ao verificar token: {str(e)}")
    
    # Limpeza de Cache
    with st.expander("Limpeza de Cache"):
        if st.button("Limpar Cache de Mídia"):
            try:
                # Limpar diretórios temporários
                FilterImage.clean_temp_directory(os.path.join(Paths.ROOT_DIR, "temp"))
                st.success("Cache de mídia limpo com sucesso!")
            except Exception as e:
                st.error(f"Erro ao limpar cache: {str(e)}")
    
    # Monitor de Sistema
    with st.expander("Monitor de Sistema"):
        if st.button("Verificar Status do Sistema"):
            try:
                import psutil
                
                # CPU e Memória
                cpu_percent = psutil.cpu_percent(interval=1)
                memory = psutil.virtual_memory()
                
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("CPU", f"{cpu_percent}%")
                    st.metric("Memória", f"{memory.percent}%")
                
                with col2:
                    disk = psutil.disk_usage('/')
                    st.metric("Disco", f"{disk.percent}%")
                    st.metric("Temperatura CPU", f"{psutil.sensors_temperatures().get('coretemp', [{'current': 0}])[0].current}°C" if hasattr(psutil, 'sensors_temperatures') and psutil.sensors_temperatures() else "N/A")
            except Exception as e:
                st.error(f"Erro ao monitorar sistema: {str(e)}")
