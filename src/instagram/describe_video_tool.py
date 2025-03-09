import os
import google.generativeai as genai
from dotenv import load_dotenv
import base64

class VideoDescriber:
    @staticmethod
    def describe(video_path: str) -> str:
        """
        Gera uma descrição detalhada para o vídeo fornecido.

        Args:
            video_path (str): Caminho local do vídeo a ser analisado.

        Returns:
            str: Descrição gerada para o vídeo.
        """
        load_dotenv()  # Carregar variáveis de ambiente do arquivo .env

        # Configurar o cliente Gemini
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        model = genai.GenerativeModel('gemini-1.5-pro')  # Usando o modelo que suporta vídeos

        # Verificar se o arquivo existe
        if not os.path.exists(video_path):
            return f"Erro: O arquivo de vídeo não existe no caminho: {video_path}"

        try:
            # Ler o arquivo de vídeo diretamente do caminho local
            with open(video_path, 'rb') as video_file:
                video_bytes = video_file.read()
                encoded_video = base64.b64encode(video_bytes).decode('utf-8')
        except Exception as e:
            return f"Erro ao ler o arquivo de vídeo: {e}"

        prompt_text = """
                Me dê uma ideia do contexto do ambiente do vídeo e do que está ocorrendo no vídeo.
                Quais são as expressões faciais predominantes (feliz, triste, neutro, etc.)?                                 
                Qual é a expressão emocional delas? 
                Além disso, descreva qualquer objeto ou elemento marcante na cena.
                Tente identificar se é dia ou noite, ambiente aberto ou fechado,
                de festa ou calmo. O que as pessoas estão fazendo?
            """

        try:
            describe = model.generate_content({
                "parts": [
                    {
                        "text": prompt_text
                    },
                    {
                        "inline_data": {
                            "mime_type": "video/mp4",
                            "data": encoded_video
                        }
                    }
                ]
            })

            # Extraindo a descrição da resposta
            try:
                return describe.text.strip()
            except (AttributeError, IndexError) as e:
                return f"Erro ao processar a descrição do vídeo: {e}"

        except Exception as e:
            print(f"Erro detalhado: {str(e)}")  # Debug print
            return f"Erro ao processar a descrição do vídeo: {e}"