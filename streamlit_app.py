import streamlit as st
from src.services.instagram_send import InstagramSend
import os
from PIL import Image
import io

st.set_page_config(
    page_title="Agent Social Media - CrewAI2",
    page_icon="📱",
    layout="wide"
)

st.title('Agent Social Media - CrewAI2 📱')

# Sidebar configuration
st.sidebar.header('Post Configuration')
content_type = st.sidebar.radio(
    "Content Type",
    ["Image Post", "Reels Video"],
    index=0
)

style_options = st.sidebar.selectbox(
    'Writing Style',
    ['Divertido, Alegre, Sarcástico e descontraído', 
     'Profissional e Formal',
     'Inspirador e Motivacional',
     'Informativo e Educativo']
)

person_options = st.sidebar.selectbox(
    'Narrative Person',
    ['Terceira pessoa do singular',
     'Primeira pessoa do singular',
     'Segunda pessoa do singular']
)

sentiment = st.sidebar.selectbox(
    'Sentiment',
    ['Positivo', 'Neutro', 'Motivacional']
)

use_emojis = st.sidebar.checkbox('Use Emojis', value=True)
use_slang = st.sidebar.checkbox('Use Informal Language', value=True)

# Main content area depends on selected content type
if content_type == "Image Post":
    st.header('Create your Instagram Post')

    col1, col2 = st.columns([2, 1])

    with col1:
        # Upload image
        uploaded_file = st.file_uploader('Choose an image...', type=['png', 'jpg', 'jpeg'])

        if uploaded_file is not None:
            try:
                # Save the uploaded image
                image_data = uploaded_file.read()
                
                # Create temp directory if it doesn't exist
                os.makedirs('temp', exist_ok=True)
                
                # Save image as RGB to avoid RGBA issues
                image = Image.open(io.BytesIO(image_data))
                if image.mode in ('RGBA', 'LA'):
                    background = Image.new('RGB', image.size, (255, 255, 255))
                    background.paste(image, mask=image.split()[-1])
                    image = background
                    
                image_path = os.path.join('temp', uploaded_file.name)
                image.save(image_path, 'JPEG')
                
                # Show preview
                st.image(image_path, caption='Preview of your image', use_container_width=True)
            except Exception as e:
                st.error(f'Error processing image: {str(e)}')

    with col2:
        # Input for caption
        st.subheader('Caption')
        caption = st.text_area('Enter your caption or leave blank for AI-generated caption', height=150)
        word_limit = st.slider('Word Limit', min_value=50, max_value=300, value=200, step=50)

        if st.button('Post to Instagram', type='primary'):
            if uploaded_file is not None:
                with st.spinner('Processing your post...'):
                    try:
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
                            st.success('Posted to Instagram successfully! 🎉')
                        else:
                            st.error('Failed to post to Instagram. Check logs for details.')
                        
                        # Clean up temp file
                        if os.path.exists(image_path):
                            os.remove(image_path)
                            
                    except Exception as e:
                        st.error(f'Error posting to Instagram: {str(e)}')
            else:
                st.error('Please upload an image first.')

else:  # Reels Video
    st.header('Create your Instagram Reels')

    col1, col2 = st.columns([2, 1])

    with col1:
        # Upload video
        uploaded_file = st.file_uploader('Choose a video...', type=['mp4', 'mov', 'avi'])

        if uploaded_file is not None:
            try:
                # Save the uploaded video
                video_data = uploaded_file.read()
                
                # Create temp directory if it doesn't exist
                os.makedirs('temp_videos', exist_ok=True)
                
                video_path = os.path.join('temp_videos', uploaded_file.name)
                with open(video_path, 'wb') as f:
                    f.write(video_data)
                
                # Show preview
                st.video(video_path)
                st.caption("Video preview")
            except Exception as e:
                st.error(f'Error processing video: {str(e)}')

    with col2:
        # Input for caption and hashtags
        st.subheader('Reels Caption')
        caption = st.text_area('Enter your caption or leave blank for AI-generated caption', height=100)
        
        st.subheader('Hashtags')
        hashtags = st.text_area('Enter hashtags (comma separated, without #)', height=68, key='hashtags')
        
        share_to_feed = st.checkbox('Share to Feed', value=True)
        word_limit = st.slider('Caption Word Limit', min_value=50, max_value=300, value=150, step=50)

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

# Queue monitoring section
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
        st.metric("Rate Limited", stats["rate_limited_posts"])
    with col3:
        st.metric("Image Jobs", stats["image_processing_jobs"])
        st.metric("Video Jobs", stats["video_processing_jobs"])
    with col4:
        st.metric("Queue Size", stats["queue_size"])
        avg_time = round(stats["avg_processing_time"], 2)
        st.metric("Avg. Processing Time", f"{avg_time}s")
    
    # Display recent jobs
    if recent_jobs:
        st.subheader('Recent Jobs')
        for job in recent_jobs:
            job_type = job.get("content_type", "unknown")
            status = job.get("status", "unknown")
            created = job.get("created_at", 0)
            
            # Format timestamp
            import datetime
            created_str = datetime.datetime.fromtimestamp(created).strftime('%Y-%m-%d %H:%M:%S')
            
            # Color based on status
            color = {
                "completed": "green",
                "failed": "red",
                "rate_limited": "orange",
                "processing": "blue",
                "pending": "gray"
            }.get(status, "gray")
            
            st.markdown(f"**Job {job['id'][:8]}...**: {job_type.upper()} - "
                       f"<span style='color:{color}'>{status}</span> - {created_str}", unsafe_allow_html=True)
