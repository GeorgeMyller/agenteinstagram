import os
import google.generativeai as genai
from dotenv import load_dotenv
import requests  # Added for fetching image data
import base64    # Added for base64 encoding

class ImageDescriber:
    @staticmethod
    def describe(image_url: str) -> str:
        """
        Gera uma descrição detalhada para a imagem fornecida.

        Args:
            image_url (str): URL da imagem a ser analisada.

        Returns:
            str: Descrição gerada para a imagem.
        """
        load_dotenv()  # Carregar variáveis de ambiente do arquivo .env

        # Configurar o cliente Gemini
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        model = genai.GenerativeModel('gemini-2.0-flash-thinking-exp-01-21')  # Updated model name

        # Fazer a solicitação à API do Gemini
        try:
            # Fetch and encode the image from the URL with custom headers
            headers = {'User-Agent': 'Mozilla/5.0'}
            image_response = requests.get(image_url, headers=headers)
            image_response.raise_for_status()
            encoded_image = base64.b64encode(image_response.content).decode('utf-8')
        except Exception as e:
            return f"Erro ao obter a imagem: {e}"

        prompt_text = """
                Me dê uma ideia do contexto do ambiente da imagem e do que está ocorrendo na imagem.
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
                            "mime_type": "image/jpeg",
                            "data": encoded_image  # Updated to use base64 encoded image content
                        }
                    }
                ]
            })

            # Extraindo a descrição da resposta
            try:
                return describe.text.strip()
            except (AttributeError, IndexError) as e:
                return f"Erro ao processar a descrição da imagem: {e}"

        except Exception as e:
            print(f"Erro detalhado: {str(e)}")  # Debug print
            return f"Erro ao processar a descrição da imagem: {e}"