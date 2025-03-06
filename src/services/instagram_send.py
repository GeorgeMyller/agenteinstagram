import os

from src.instagram.crew_post_instagram import InstagramPostCrew
from src.instagram.describe_image_tool import ImageDescriber
from src.instagram.instagram_post_service import InstagramPostService
from src.instagram.border import ImageWithBorder
from src.instagram.filter import FilterImage
from src.utils.paths import Paths
from src.instagram.image_uploader import ImageUploader
import requests

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
        result = None
        original_image_path = image_path
        uploaded_images = []
        uploader = ImageUploader()  # Reuse the same uploader instance
        
        # Validar caption antes do processamento
        if not caption or caption.lower() == "none":
            caption = "A Acesso IA está transformando processos com IA! 🚀"
            print(f"Caption vazia ou 'None'. Usando caption padrão: '{caption}'")
        
        try:
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
            
            # Verificar se o arquivo existe
            if not os.path.exists(image_path):
                raise FileNotFoundError(f"Arquivo de imagem não encontrado: {image_path}")
                
            border_image = os.path.join(Paths.SRC_DIR, "instagram", "moldura.png")
            
            # Process image with filter
            print("Aplicando filtros à imagem...")
            image_path = FilterImage.process(image_path)
            
            # First upload to get image description
            print("Obtendo descrição da imagem...")
            try:
                temp_image = uploader.upload_from_path(image_path)
                uploaded_images.append(temp_image)
                describe = ImageDescriber.describe(temp_image['url'])
                
                # Try to delete the temporary image immediately after getting description
                if temp_image.get("deletehash"):
                    print(f"Deletando imagem temporária usada para descrição...")
                    if uploader.delete_image(temp_image["deletehash"]):
                        uploaded_images.remove(temp_image)
            except Exception as e:
                print(f"Erro ao obter descrição da imagem: {str(e)}")
                describe = "Imagem para publicação no Instagram."
                
            # Add border and prepare final image
            print("Aplicando bordas e filtros...")
            try:
                image = ImageWithBorder.create_bordered_image(
                    border_path=border_image,
                    image_path=image_path,
                    output_path=image_path                
                )
            except Exception as e:
                print(f"Erro ao aplicar borda à imagem: {str(e)}")
                # Continue with original image if border application fails
            
            # Upload final image
            print("Enviando imagem para publicação...")
            try:
                final_image = uploader.upload_from_path(image_path)
                uploaded_images.append(final_image)
            except Exception as e:
                print(f"Erro ao fazer upload da imagem final: {str(e)}")
                raise
            
            # Generate or use provided caption
            print("Gerando legenda...")
            try:
                crew = InstagramPostCrew()
                inputs.update({
                    "caption": caption,
                    "describe": describe,
                })
                
                final_caption = crew.kickoff(inputs=inputs)
            except Exception as e:
                print(f"Erro ao gerar legenda: {str(e)}")
                # Se falhar a geração da legenda, usa a original
                final_caption = caption
            
            # Adicionar texto padrão ao final da legenda
            final_caption = final_caption + "\n\n-------------------"
            final_caption = final_caption + "\n\n Essa postagem foi toda realizada por um agente inteligente"
            final_caption = final_caption + "\n O agente desempenhou as seguintes ações:"
            final_caption = final_caption + "\n 1 - Idenficação e reconhecimento do ambiente da fotografia"
            final_caption = final_caption + "\n 2 - Aplicação de Filtros de contraste e autocorreção da imagem"
            final_caption = final_caption + "\n 3 - Aplicação de moldura específica"
            final_caption = final_caption + "\n 4 - Definição de uma persona específica com base nas preferências"
            final_caption = final_caption + "\n 5 - Criação da legenda com base na imagem e na persona"
            final_caption = final_caption + "\n 6 - Postagem no feed do instagram"
            final_caption = final_caption + "\n\n-------------------"
            
            # Post to Instagram
            print("Iniciando processo de publicação no Instagram...")
            try:
                insta_post = InstagramPostService()
                result = insta_post.post_image(final_image['url'], final_caption)
            except Exception as e:
                print(f"Erro no processo de publicação no Instagram: {str(e)}")
                raise
            
            if result:
                print("Post processado e enviado ao Instagram com sucesso!")
                return result
            else:
                print("O post pode ter sido publicado, mas não foi possível confirmar o status.")
                print("Verifique manualmente o feed do Instagram.")
                return None

        except Exception as e:
            print(f"Erro durante o processo de publicação: {str(e)}")
            return None
            
        finally:
            # Clean up temporary files regardless of success/failure
            try:
                # Clean up uploaded images
                failed_deletions = []
                for img in uploaded_images:
                    try:
                        if img.get("deletehash"):
                            print(f"Tentando deletar imagem com deletehash: {img.get('deletehash')}...")
                            if not uploader.delete_image(img["deletehash"]):
                                failed_deletions.append(img["deletehash"])
                    except requests.exceptions.HTTPError as e:
                        if hasattr(e, 'response') and e.response.status_code == 404:
                            print("Imagem já removida do servidor.")
                        else:
                            print(f"Erro ao deletar imagem: {str(e)}")
                    except Exception as e:
                        print(f"Erro ao deletar imagem: {str(e)}")
                
                if failed_deletions:
                    print("Aviso: Algumas imagens não puderam ser deletadas:")
                    for failed_hash in failed_deletions:
                        print(f"- Deletehash: {failed_hash}")
                
                # Clean up local files
                if image_path and image_path != original_image_path and os.path.exists(image_path):
                    os.remove(image_path)
                    print(f"A imagem local {image_path} foi apagada com sucesso.")
                
            except Exception as cleanup_error:
                print(f"Erro ao limpar arquivos temporários: {str(cleanup_error)}")
        
        return result
