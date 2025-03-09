import os
import google.generativeai as genai
from dotenv import load_dotenv
import requests  # Added for fetching video data
import base64    # Added for base64 encoding

class VideoDescriber:
    @staticmethod
    def describe(video_url: str) -> str:
        """
        Gera uma descrição detalhada para o vídeo fornecido.

        Args:
            video_url (str): URL do vídeo a ser analisado.

        Returns:
            str: Descrição gerada para o vídeo.
        """
        load_dotenv()  # Carregar variáveis de ambiente do arquivo .env

        # Configurar o cliente Gemini
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        model = genai.GenerativeModel('gemini-2.0-flash-exp')  # Updated model name

        # Fazer a solicitação à API do Gemini
        try:
            # Fetch and encode the video from the URL with custom headers
            headers = {'User-Agent': 'Mozilla/5.0'}
            video_response = requests.get(video_url, headers=headers)
            video_response.raise_for_status()
            encoded_video = base64.b64encode(video_response.content).decode('utf-8')
        except Exception as e:
            return f"Erro ao obter o vídeo: {e}"

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
                            "data": encoded_video  # Updated to use base64 encoded video content
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