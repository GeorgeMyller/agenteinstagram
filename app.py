from flask import Flask, request, jsonify
from dotenv import load_dotenv
import os
import logging
from src.instagram.instagram_facade import InstagramFacade
from src.services.message_factory import MessageFactory
from src.services.send import MessageSender

# Configurar logger
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Carregar variáveis de ambiente
load_dotenv()

# Definir o ID do grupo autorizado
AUTHORIZED_GROUP_ID = os.getenv('AUTHORIZED_GROUP_ID')  # ID do grupo autorizado

try:
    # Inicializar os serviços
    instagram = InstagramFacade(
        access_token=os.getenv('INSTAGRAM_API_KEY'),
        ig_user_id=os.getenv('INSTAGRAM_ACCOUNT_ID'),
        skip_token_validation=False
    )
    logger.info("Instagram service initialized successfully")
except Exception as e:
    logger.error(f"Error initializing Instagram service: {e}")
    raise

message_sender = MessageSender()

@app.route('/messages-upsert', methods=['POST'])
def handle_message():
    """Endpoint principal para processar mensagens recebidas"""
    try:
        data = request.json
        logger.info(f"Mensagem recebida: {data}")
        
        # Criar objeto de mensagem
        message = MessageFactory.create_message(data)
        
        # Verificar se a mensagem é do grupo autorizado
        if message.remote_jid != AUTHORIZED_GROUP_ID:
            logger.info(f"Mensagem ignorada - origem não autorizada: {message.remote_jid}")
            return jsonify({
                "status": "ignored", 
                "message": "Mensagem de origem não autorizada"
            }), 200
        
        # A partir daqui, sabemos que a mensagem é do grupo autorizado
        logger.info(f"Processando mensagem do grupo autorizado: {message.remote_jid}")
        
        # Processar a mensagem com base no tipo
        if message.message_type == message.TYPE_TEXT:
            # Responder mensagem de texto com informações sobre funcionalidades
            response = message_sender.send_text(
                number=message.remote_jid,
                msg="Recebi sua mensagem. Estou pronto para ajudar com suas postagens do Instagram!"
            )
            logger.info(f"Resposta enviada para mensagem de texto: {response}")
            
        elif message.message_type == message.TYPE_IMAGE:
            # Se recebeu uma imagem, postar no Instagram
            logger.info("Imagem recebida, tentando postar no Instagram")
            
            # Salvar imagem temporariamente
            import tempfile
            import os
            from datetime import datetime
            
            # Criar diretório para imagens temporárias se não existir
            temp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'temp')
            os.makedirs(temp_dir, exist_ok=True)
            
            # Salvar a imagem recebida
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            temp_image_path = os.path.join(temp_dir, f"whatsapp_image_{timestamp}.jpg")
            
            with open(temp_image_path, "wb") as f:
                f.write(message.image_base64_bytes)
            
            # Postar a imagem no Instagram
            caption = message.image_caption or "Imagem compartilhada via WhatsApp"
            post_result = instagram.post_single_photo(temp_image_path, caption)
            
            # Informar resultado ao usuário
            if post_result and post_result.get('status') == 'success':
                response_text = f"Sua imagem foi postada com sucesso no Instagram! ID: {post_result.get('id')}"
            else:
                response_text = f"Não foi possível postar sua imagem: {post_result.get('message', 'Erro desconhecido')}"
            
            response = message_sender.send_text(number=message.remote_jid, msg=response_text)
            logger.info(f"Resposta enviada para mensagem de imagem: {response}")
            
        elif message.message_type == message.TYPE_VIDEO:
            # Responder que não podemos processar vídeos no momento
            response = message_sender.send_text(
                number=message.remote_jid,
                msg="Recebi seu vídeo, mas ainda não consigo postar vídeos automaticamente no Instagram."
            )
            logger.info(f"Resposta enviada para mensagem de vídeo: {response}")
            
        else:
            # Responder outros tipos de mensagem
            response = message_sender.send_text(
                number=message.remote_jid,
                msg="Recebi sua mensagem, mas ainda não sei processar esse tipo de conteúdo. Por favor, envie texto ou imagens."
            )
            logger.info(f"Resposta enviada para mensagem de tipo desconhecido: {response}")
        
        return jsonify({
            "status": "success", 
            "message": "Mensagem processada com sucesso",
            "response": response
        }), 200
        
    except Exception as e:
        logger.error(f"Erro ao processar mensagem: {str(e)}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/debug/instagram-status', methods=['GET'])
def instagram_status():
    """Endpoint para verificar status da conta do Instagram"""
    try:
        status = instagram.get_account_status()
        return jsonify(status), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)