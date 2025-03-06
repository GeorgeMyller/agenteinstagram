import os
import time
import requests

from src.instagram.crew_post_instagram import InstagramPostCrew
from src.instagram.describe_image_tool import ImageDescriber
from src.instagram.instagram_post_service import InstagramPostService
from src.instagram.border import ImageWithBorder
from src.instagram.filter import FilterImage
from src.utils.paths import Paths
from src.instagram.image_uploader import ImageUploader

# Import new queue system
from src.services.post_queue import post_queue, RateLimitExceeded, ContentPolicyViolation

class InstagramSend:
    # Keep track of rate limits
    last_rate_limit_time = 0
    rate_limit_window = 3600  # 1 hour window for rate limiting
    max_rate_limit_hits = 5  # Maximum number of rate limit hits before enforcing longer delays
    
    @staticmethod
    def queue_post(image_path, caption, inputs=None) -> str:
        """
        Queue an image to be posted to Instagram asynchronously
        
        Args:
            image_path (str): Path to the image file
            caption (str): Caption text
            inputs (dict): Optional configuration for post generation
            
        Returns:
            str: Job ID for tracking the post status
        """
        # Validate inputs before queuing
        if not caption or caption.lower() == "none":
            caption = "A Acesso IA está transformando processos com IA! 🚀"
            print(f"Caption vazia ou 'None'. Usando caption padrão: '{caption}'")

        # Validate image path
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Arquivo de imagem não encontrado: {image_path}")
            
        # Add to queue and return job ID
        job_id = post_queue.add_job(image_path, caption, inputs)
        return job_id
    
    @staticmethod
    def check_post_status(job_id):
        """
        Check the status of a queued post
        
        Args:
            job_id (str): Job ID returned when queuing the post
            
        Returns:
            dict: Job status information
        """
        return post_queue.get_job_status(job_id)
    
    @staticmethod
    def get_queue_stats():
        """
        Get statistics about the current queue
        
        Returns:
            dict: Queue statistics
        """
        return post_queue.get_queue_stats()
    
    @staticmethod
    def get_recent_posts(limit=10):
        """
        Get recent post history
        
        Args:
            limit (int): Maximum number of posts to return
            
        Returns:
            list: Recent post history
        """
        return post_queue.get_job_history(limit)
    
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
            
            # Generate caption
            print("Gerando legenda...")
            try:
                crew = InstagramPostCrew()
                # Pass inputs as a dictionary instead of XML string
                inputs_dict = {
                    'genero': inputs.get('genero', 'Neutro'),
                    'caption': caption,
                    'describe': describe,
                    'estilo': inputs.get('estilo', 'Divertido, Alegre, Sarcástico e descontraído'),
                    'pessoa': inputs.get('pessoa', 'Terceira pessoa do singular'),
                    'sentimento': inputs.get('sentimento', 'Positivo'),
                    'tamanho': inputs.get('tamanho', '200 palavras'),
                    'emojs': inputs.get('emojs', 'sim'),
                    'girias': inputs.get('girias', 'sim')
                }
                final_caption = crew.kickoff(inputs=inputs_dict)
            except Exception as e:
                print(f"Erro ao gerar legenda: {str(e)}")
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
            
            # Post to Instagram with enhanced rate limit handling
            print("Iniciando processo de publicação no Instagram...")
            try:
                insta_post = InstagramPostService()
                
                # Check for severe rate limiting
                stats = post_queue.get_queue_stats()
                current_time = time.time()
                
                if stats["rate_limited_posts"] > InstagramSend.max_rate_limit_hits:
                    # Check if we're still within the rate limit window
                    if (current_time - InstagramSend.last_rate_limit_time) < InstagramSend.rate_limit_window:
                        remaining_time = InstagramSend.rate_limit_window - (current_time - InstagramSend.last_rate_limit_time)
                        raise RateLimitExceeded(
                            f"Taxa de requisições severamente excedida. "
                            f"Aguarde {int(remaining_time/60)} minutos antes de tentar novamente."
                        )
                    else:
                        # Reset rate limit tracking if window has passed
                        InstagramSend.last_rate_limit_time = 0
                        stats["rate_limited_posts"] = 0

                result = insta_post.post_image(final_image['url'], final_caption)
                
                if not result:
                    print("Falha ao publicar no Instagram. Verificando status...")
                    raise Exception("Falha na publicação")
                    
                print("Post processado e enviado ao Instagram com sucesso!")
                return result
                
            except Exception as e:
                error_str = str(e).lower()
                if "rate" in error_str and "limit" in error_str:
                    InstagramSend.last_rate_limit_time = current_time
                    raise RateLimitExceeded(f"Taxa de requisições excedida: {str(e)}")
                print(f"Erro no processo de publicação no Instagram: {str(e)}")
                raise

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
