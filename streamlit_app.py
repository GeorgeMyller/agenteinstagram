import streamlit as st
import os
import time
import tempfile
import random
from PIL import Image
from src.services.instagram_send import InstagramSend

st.set_page_config(page_title="Instagram Agent", layout="wide")

st.title('Instagram Agent 📷')
st.caption('Agente para automação de Instagram')

tab1, tab2, tab3, tab4 = st.tabs(["Publicar Foto", "Publicar Reels", "Publicar Carrossel", "Monitorar Fila"])

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

# Queue monitoring section
with tab4:
    st.header('Queue Status')
    if st.button('Refresh Queue Status'):
        stats = InstagramSend.get_queue_stats()
        recent_jobs = InstagramSend.get_recent_posts(5)
        
        # Display stats in columns
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Jobs", stats["total_jobs"])
            st.metric("Completed", stats["completed_jobs"])
        with col2:
            st.metric("Failed", stats["failed_jobs"])
            st.metric("Pending", stats["pending_jobs"])
        with col3:
            st.metric("Processing", stats["processing_jobs"])
            st.metric("Rate Limited", stats["rate_limited_posts"])
        with col4:
            # Calculate estimated completion time based on processing speed
            processing_speed = stats.get("avg_processing_time", 120)  # seconds per job
            remaining_jobs = stats["pending_jobs"] + stats["processing_jobs"]
            est_minutes = int((processing_speed * remaining_jobs) / 60) if remaining_jobs > 0 else 0
            
            st.metric("Est. Completion", f"{est_minutes} min" if est_minutes > 0 else "N/A")
            st.metric("Avg. Process Time", f"{stats.get('avg_processing_time', 0):.1f}s")
            
        # Display recent jobs
        st.subheader("Recent Posts")
        
        if not recent_jobs:
            st.info("No recent posts found.")
        else:
            for job in recent_jobs:
                col1, col2 = st.columns([1, 3])
                with col1:
                    # Try to load preview image if available
                    if job.get("media_type") == "IMAGE" and job.get("media_paths"):
                        try:
                            if isinstance(job["media_paths"], list) and len(job["media_paths"]) > 0:
                                image_path = job["media_paths"][0]
                            else:
                                image_path = job["media_paths"]
                                
                            if os.path.exists(image_path):
                                st.image(image_path, width=100)
                            else:
                                st.write("🖼️ [Image]")
                        except:
                            st.write("🖼️ [Image]")
                    elif job.get("media_type") == "VIDEO" or job.get("content_type") == "reel":
                        st.write("🎬 [Video]")
                    elif job.get("content_type") == "carousel":
                        st.write("🔄 [Carousel]")
                    else:
                        st.write("📄 [Media]")
                        
                with col2:
                    status_color = {
                        "completed": "🟢",
                        "failed": "🔴",
                        "processing": "🟡",
                        "pending": "⚪"
                    }.get(job.get("status", ""), "⚪")
                    
                    st.write(f"{status_color} **ID:** `{job.get('job_id', 'Unknown')}`")
                    st.caption(f"Status: {job.get('status', 'Unknown')} • Time: {job.get('created_at', 'Unknown')}")
                    
                    if job.get("result") and job.get("result").get("permalink"):
                        st.markdown(f"[View on Instagram]({job['result']['permalink']})")
    else:
        st.info("Click the button to refresh queue statistics")
