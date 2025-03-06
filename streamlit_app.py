import streamlit as st
from src.services.instagram_send import InstagramSend
from src.utils.image_decode_save import ImageDecodeSaver
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

# Main content area
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
                    InstagramSend.send_instagram(
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
                    st.success('Posted to Instagram successfully! 🎉')
                    
                    # Clean up temp file
                    if os.path.exists(image_path):
                        os.remove(image_path)
                        
                except Exception as e:
                    st.error(f'Error posting to Instagram: {str(e)}')
        else:
            st.error('Please upload an image first.')
