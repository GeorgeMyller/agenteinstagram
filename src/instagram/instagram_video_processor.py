import os
from moviepy.editor import VideoFileClip, clips_array, concatenate_videoclips
from moviepy.video.fx.resize import resize
from moviepy.video.tools.cuts import find_video_period
from moviepy.config import change_settings
import tempfile

# Defina um diretório temporário para o moviepy usar (opcional, mas recomendado)
# change_settings({"TEMP_DIR": "/caminho/para/seu/diretorio/temporario"}) # Linux/macOS
# change_settings({"TEMP_DIR": "C:\\caminho\\para\\seu\\diretorio\\temporario"}) # Windows

class VideoProcessor:

    @staticmethod
    def get_video_info(video_path):
        """Obtém informações sobre o vídeo usando moviepy."""
        try:
            with VideoFileClip(video_path) as clip:
                video_info = {
                    'duration': clip.duration,
                    'width': clip.size[0],
                    'height': clip.size[1],
                    'fps': clip.fps,
                    'codec': clip.codec,
                    'audio_codec': clip.audio.codec if clip.audio else None,  # Verifica se há áudio
                    'file_size': os.path.getsize(video_path),
                    'aspect_ratio': clip.size[0] / clip.size[1]
                }
            return video_info
        except Exception as e:
            print(f"Erro ao obter informações do vídeo: {e}")
            return None

    @staticmethod
    def check_duration(duration, post_type):
        """Verifica se a duração está dentro dos limites."""
        if post_type == 'reels':
            return 3 <= duration <= 90
        elif post_type == 'feed':
            return 3 <= duration <= 60 #duração máxima para feed é 60 segundos.
        elif post_type == 'story':
            return duration <= 60
        else:
            return True  # Sem limite para outros tipos (ou você pode definir um limite padrão)

    @staticmethod
    def check_resolution(width, height, post_type):
        """Verifica se a resolução está dentro dos limites."""
        min_width = 600
        min_height = 600
        #Você pode adicionar resoluções máximas, se necessitar.
        return width >= min_width and height >= min_height

    @staticmethod
    def check_codec(video_codec, audio_codec):
        """Verifica se os codecs são suportados."""
        #Instagram recomenda H.264 para video e AAC para áudio.
        return video_codec.startswith("libx264") and (audio_codec is None or audio_codec.startswith("aac")) #O audio pode não existir

    @staticmethod
    def check_aspect_ratio(width, height, post_type):
        """Verifica se a proporção está dentro dos limites."""
        aspect_ratio = width / height
        return 0.8 <= aspect_ratio <= 1.91  # Entre 4:5 e 1.91:1


    @staticmethod
    def check_file_size(file_size, post_type):
        """Verifica se o tamanho do arquivo está dentro dos limites."""
        max_size_mb = 100  # 100MB para Reels (ajuste se necessário)
        max_size_bytes = max_size_mb * 1024 * 1024
        return file_size <= max_size_bytes
    

    @staticmethod
    def _crop_to_aspect_ratio(clip, target_aspect_ratio):
        """Função auxiliar para cortar o vídeo para a proporção desejada, mantendo o centro."""
        current_aspect_ratio = clip.size[0] / clip.size[1]

        if current_aspect_ratio > target_aspect_ratio:
            # Vídeo muito largo, cortar as laterais
            new_width = int(clip.size[1] * target_aspect_ratio)
            x_center = clip.size[0] / 2
            clip = clip.crop(x1=x_center - new_width / 2, x2=x_center + new_width / 2)
        elif current_aspect_ratio < target_aspect_ratio:
            # Vídeo muito alto, cortar em cima e embaixo
            new_height = int(clip.size[0] / target_aspect_ratio)
            y_center = clip.size[1] / 2
            clip = clip.crop(y1=y_center - new_height / 2, y2=y_center + new_height / 2)
        return clip

    @staticmethod
    def optimize_for_instagram(video_path, post_type='feed'):
        """Otimiza um vídeo para o Instagram usando moviepy."""
        video_info = VideoProcessor.get_video_info(video_path)
        if not video_info:
            return None

        try:
            with VideoFileClip(video_path) as clip:
                
                # --- Verificações ---
                if not VideoProcessor.check_duration(video_info['duration'], post_type):
                    #Cortar ou estender o video
                    if post_type == 'reels':
                      max_duration = 90
                    elif post_type == 'feed':
                      max_duration = 60
                    elif post_type == 'story':
                      max_duration = 60
                    else:
                      max_duration = video_info['duration'] #Não alterar

                    if video_info['duration'] < 3:
                      print("Vídeo muito curto, impossível postar")
                      return None
                    
                    clip = clip.subclip(0, min(video_info['duration'], max_duration)) #Corta o video, caso necessário.

                if not VideoProcessor.check_resolution(video_info['width'], video_info['height'], post_type):
                    # Redimensionar (mantendo a proporção)
                    if video_info['width'] < video_info['height']:
                        clip = clip.resize(width=600) #Largura como base
                    else:
                        clip = clip.resize(height=600) #Altura como base

                if not VideoProcessor.check_codec(video_info['codec'], video_info['audio_codec']):
                    #Definir codec de audio e video
                    clip = clip.set_codec("libx264") #Codec de vídeo
                    if clip.audio:
                      clip.audio = clip.audio.set_codec("aac") #Codec de áudio

                if not VideoProcessor.check_aspect_ratio(clip.size[0], clip.size[1], post_type):
                    # Ajustar a proporção (cortando)
                    if post_type == 'reels':
                        target_aspect_ratio = 9/16
                    elif post_type == 'feed':
                        target_aspect_ratio = 1 #Exemplo, pode ser outro
                    elif post_type == 'story':
                        target_aspect_ratio = 9/16
                    else:
                        target_aspect_ratio = clip.size[0] / clip.size[1] #Manter original
                    
                    clip = VideoProcessor._crop_to_aspect_ratio(clip, target_aspect_ratio)
                

                # --- Escrita do Arquivo Otimizado ---
                # Usar um arquivo temporário
                with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as temp_file:
                    temp_filename = temp_file.name

                #Definindo Bitrate
                bitrate = "5000k" # 5Mbits/s - Você pode ajustar isso com base nos seus testes

                clip.write_videofile(
                    temp_filename,
                    codec="libx264",
                    audio_codec="aac",
                    bitrate=bitrate, # Use o bitrate definido
                    threads=4,  # Ajuste para o número de núcleos do seu processador
                    preset="fast",  # Ajuste para controlar a velocidade de codificação e a qualidade
                    verbose=False, #Mostrar informações
                    logger=None  # Desativar o logger padrão do moviepy
                )
                print(f"Vídeo otimizado salvo em: {temp_filename}")
                return temp_filename

        except Exception as e:
            print(f"Erro ao otimizar o vídeo: {e}")
            return None