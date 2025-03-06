import os
from src.instagram.instagram_post_service import InstagramPostService
from src.instagram.image_uploader import ImageUploader

script_dir = os.path.dirname(os.path.abspath(__file__))

# Alterado: nome de arquivo e caption genérico
image = os.path.join(script_dir, 'default.png')

upload = ImageUploader()
image_cloud = upload.upload_from_path(image)

caption = "default"

instagram = InstagramPostService()

url = image_cloud['url']

response = instagram.post_image(url, caption)

i = 0
