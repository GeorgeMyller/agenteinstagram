import streamlit as st
import os
from src.instagram.instagram_facade import InstagramFacade
from src.instagram.instagram_media_service import InstagramMediaService
import asyncio
from datetime import datetime
import tempfile
from pathlib import Path

# Initialize services
instagram = InstagramFacade()
media_service = InstagramMediaService()

st.title("Instagram Content Manager")

def save_uploaded_file(uploaded_file):
    """Save uploaded file to temp directory and return path"""
    if uploaded_file is None:
        return None
    
    temp_dir = Path("temp")
    temp_dir.mkdir(exist_ok=True)
    
    file_path = temp_dir / f"upload_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uploaded_file.name}"
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return str(file_path)

def display_media_requirements(media_type):
    """Display Instagram requirements for different media types"""
    st.info("Instagram Requirements:")
    
    if media_type == "image":
        st.write("- Format: JPEG/PNG")
        st.write("- Aspect ratio: 4:5 to 1.91:1")
        st.write("- Minimum resolution: 320x320 pixels")
        st.write("- Maximum file size: 8MB")
    elif media_type == "carousel":
        st.write("- 2-10 images per carousel")
        st.write("- All images must meet single image requirements")
        st.write("- Consistent aspect ratio recommended")
    elif media_type == "video":
        st.write("- Format: MP4 (H.264 codec)")
        st.write("- Aspect ratio: 4:5 to 1.91:1")
        st.write("- Resolution: Minimum 500 pixels wide")
        st.write("- Duration: 3-60 seconds")
        st.write("- Maximum file size: 100MB")
    elif media_type == "reel":
        st.write("- Format: MP4 (H.264 codec)")
        st.write("- Aspect ratio: 9:16 (vertical)")
        st.write("- Resolution: 1080x1920 recommended")
        st.write("- Duration: 3-90 seconds")
        st.write("- Maximum file size: 100MB")

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Single Image", 
    "Carousel", 
    "Video", 
    "Reels",
    "Status"
])

with tab1:
    st.header("Post Single Image")
    display_media_requirements("image")
    
    image_file = st.file_uploader("Choose an image", type=["jpg", "jpeg", "png"], key="single_image")
    caption = st.text_area("Caption", key="single_image_caption")
    
    if image_file:
        st.image(image_file)
        
        if st.button("Validate Image", key="validate_single"):
            temp_path = save_uploaded_file(image_file)
            is_valid, message = media_service.validate_media(temp_path)
            
            if is_valid:
                st.success("✅ Image validation successful!")
            else:
                st.error(f"❌ Validation failed: {message}")
        
        if st.button("Post Image", key="post_single"):
            with st.spinner("Posting image..."):
                temp_path = save_uploaded_file(image_file)
                result = asyncio.run(instagram.post_single_image(temp_path, caption))
                
                if result['status'] == 'success':
                    st.success(f"✅ Posted successfully! ID: {result['id']}")
                else:
                    st.error(f"❌ Failed to post: {result['message']}")

with tab2:
    st.header("Post Image Carousel")
    display_media_requirements("carousel")
    
    uploaded_files = st.file_uploader(
        "Choose 2-10 images", 
        type=["jpg", "jpeg", "png"], 
        accept_multiple_files=True,
        key="carousel_images"
    )
    carousel_caption = st.text_area("Caption", key="carousel_caption")
    
    if uploaded_files:
        cols = st.columns(min(5, len(uploaded_files)))
        for idx, image in enumerate(uploaded_files):
            cols[idx % 5].image(image, caption=f"Image {idx + 1}")
        
        if st.button("Validate Images", key="validate_carousel"):
            temp_paths = []
            validation_failed = False
            
            for idx, file in enumerate(uploaded_files):
                temp_path = save_uploaded_file(file)
                temp_paths.append(temp_path)
                is_valid, message = media_service.validate_media(temp_path)
                
                if is_valid:
                    st.success(f"✅ Image {idx + 1} validation successful!")
                else:
                    st.error(f"❌ Image {idx + 1} validation failed: {message}")
                    validation_failed = True
            
            if len(uploaded_files) < 2:
                st.error("❌ At least 2 images required for carousel")
                validation_failed = True
            elif len(uploaded_files) > 10:
                st.error("❌ Maximum 10 images allowed for carousel")
                validation_failed = True
            
            if not validation_failed:
                st.success("✅ All images validated successfully!")
        
        if st.button("Post Carousel", key="post_carousel"):
            if len(uploaded_files) < 2 or len(uploaded_files) > 10:
                st.error("Please select 2-10 images for the carousel")
            else:
                with st.spinner("Posting carousel..."):
                    temp_paths = [save_uploaded_file(f) for f in uploaded_files]
                    result = asyncio.run(instagram.post_carousel(temp_paths, carousel_caption))
                    
                    if result['status'] == 'success':
                        st.success(f"✅ Carousel posted successfully! ID: {result['id']}")
                    else:
                        st.error(f"❌ Failed to post carousel: {result['message']}")

with tab3:
    st.header("Post Video")
    display_media_requirements("video")
    
    video_file = st.file_uploader("Choose a video", type=["mp4"], key="video")
    video_caption = st.text_area("Caption", key="video_caption")
    
    if video_file:
        temp_path = save_uploaded_file(video_file)
        st.video(temp_path)
        
        if st.button("Validate Video", key="validate_video"):
            is_valid, message = media_service.validate_media(temp_path)
            
            if is_valid:
                st.success("✅ Video validation successful!")
            else:
                st.error(f"❌ Validation failed: {message}")
        
        if st.button("Post Video", key="post_video"):
            with st.spinner("Processing and posting video..."):
                result = asyncio.run(instagram.post_video(temp_path, video_caption))
                
                if result['status'] == 'success':
                    st.success(f"✅ Video posted successfully! ID: {result['id']}")
                else:
                    st.error(f"❌ Failed to post video: {result['message']}")

with tab4:
    st.header("Post Reels")
    display_media_requirements("reel")
    
    reel_file = st.file_uploader("Choose a video for Reels", type=["mp4"], key="reel")
    reel_caption = st.text_area("Caption", key="reel_caption")
    hashtags = st.text_input("Hashtags (comma-separated)", key="reel_hashtags")
    share_to_feed = st.checkbox("Share to feed", value=True, key="reel_share")
    
    if reel_file:
        temp_path = save_uploaded_file(reel_file)
        st.video(temp_path)
        
        if st.button("Validate Reel", key="validate_reel"):
            is_valid, message = media_service.validate_media(temp_path)
            
            if is_valid:
                st.success("✅ Video validation successful!")
            else:
                st.error(f"❌ Validation failed: {message}")
        
        if st.button("Post Reel", key="post_reel"):
            with st.spinner("Processing and posting reel..."):
                hashtag_list = [tag.strip() for tag in hashtags.split(",") if tag.strip()]
                result = asyncio.run(instagram.post_video(
                    temp_path,
                    reel_caption,
                    hashtags=hashtag_list,
                    is_reel=True,
                    share_to_feed=share_to_feed
                ))
                
                if result['status'] == 'success':
                    st.success(f"✅ Reel posted successfully! ID: {result['id']}")
                    if result.get('permalink'):
                        st.markdown(f"[View on Instagram]({result['permalink']})")
                else:
                    st.error(f"❌ Failed to post reel: {result['message']}")

with tab5:
    st.header("Account Status")
    
    if st.button("Refresh Status"):
        status = instagram.get_account_status()
        
        if status['status'] == 'success':
            data = status['data']
            
            # Rate Limits
            st.subheader("API Rate Limits")
            rate_limits = data['rate_limits']
            st.metric("Remaining API Calls", rate_limits['remaining_calls'])
            reset_time = datetime.fromtimestamp(rate_limits['window_reset'])
            st.write(f"Rate limit window resets at: {reset_time.strftime('%Y-%m-%d %H:%M:%S')}")
            
            # Post Statistics
            st.subheader("Post Statistics")
            stats = data['stats']
            col1, col2, col3 = st.columns(3)
            col1.metric("Successful Posts", stats['successful_posts'])
            col2.metric("Failed Posts", stats['failed_posts'])
            col3.metric("Rate Limited Posts", stats['rate_limited_posts'])
            
            # Pending Posts
            st.subheader("Pending Posts")
            st.metric("Queued Posts", data['pending_posts'])
        else:
            st.error(f"Failed to fetch status: {status['message']}")

# Cleanup old temporary files
def cleanup_temp_files():
    temp_dir = Path("temp")
    if temp_dir.exists():
        current_time = datetime.now().timestamp()
        for file in temp_dir.glob("*"):
            # Remove files older than 24 hours
            if current_time - file.stat().st_mtime > 86400:
                try:
                    file.unlink()
                except Exception as e:
                    st.warning(f"Could not remove old temp file {file}: {e}")

cleanup_temp_files()
