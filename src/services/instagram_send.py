import os

from src.instagram.crew_post_instagram import InstagramPostCrew
from src.instagram.describe_image_tool import ImageDescriber
from src.instagram.instagram_post_service import InstagramPostService
from src.instagram.border import ImageWithBorder
from src.instagram.filter import FilterImage
from src.utils.paths import Paths
from src.instagram.image_uploader import ImageUploader

class InstagramSend:
    
    @staticmethod
    def send_instagram(image_path, caption, inputs=None):
        """
        Send an image to Instagram with a caption.
        
        Args:
            image_path (str): Path to the image file
            caption (str): Caption text
            inputs (dict): Optional configuration for post generation
        """
        if inputs is None:
            inputs = {
                "estilo": "Divertido, Alegre, Sarcástico e descontraído",
                "pessoa": "Terceira pessoa do singular",
                "sentimento": "Positivo",
                "tamanho": "200 palavras",
                "genero": "Neutro",
                "emojs": "sim",
                "girias": "sim"
            }
        
        border_image = os.path.join(Paths.SRC_DIR, "instagram", "moldura.png")
        
        # Process image with filter
        image_path = FilterImage.process(image_path)
        
        # First upload to get image description
        image = ImageUploader().upload_from_path(image_path)
        describe = ImageDescriber.describe(image['url'])
        ImageUploader().delete_image(image["deletehash"])
        
        # Add border and prepare final image
        image = ImageWithBorder.create_bordered_image(
            border_path=border_image,
            image_path=image_path,
            output_path=image_path                
        )
        
        # Upload final image
        image = ImageUploader().upload_from_path(image_path)
        
        # Generate or use provided caption
        crew = InstagramPostCrew()
        inputs.update({
            "caption": caption,
            "describe": describe,
        })
        
        final_caption = crew.kickoff(inputs=inputs)
        
        final_caption = final_caption + "\n\n-------------------"
        final_caption = final_caption + "\n\n Essa postagem foi toda realizada por um agente inteligente"
        final_caption = final_caption + "\n O agente desempenhou as seguintes ações:"
        final_caption = final_caption + "\n 1 - Idenficação e reconhecimento do ambiente da fotografia"
        final_caption = final_caption + "\n 2 - Aplicação de Filtros de contraste e autocorreção da imagem"
        final_caption = final_caption + "\n 3 - Aplicação de moldura azul específica"
        final_caption = final_caption + "\n 4 - Definição de uma persona específica com base nas preferências"
        final_caption = final_caption + "\n 5 - Criação da legenda com base na imagem e na persona"
        final_caption = final_caption + "\n 6 - Postagem no feed do instagram"
        final_caption = final_caption + "\n\n-------------------"
        
        # Post to Instagram
        insta_post = InstagramPostService()
        insta_post.post_image(image['url'], final_caption)
        
        # Clean up
        ImageUploader().delete_image(image["deletehash"])
        if os.path.exists(image['image_path']):
            os.remove(image['image_path'])
            print(f"A imagem {image['image_path']} foi apagada com sucesso.")
