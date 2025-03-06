import os
import sys

# Add the project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, project_root)

# Now you can import from src
from flask import Flask, request, jsonify
from src.services.message import Message
from src.services.instagram_send import InstagramSend
from src.utils.image_decode_save import ImageDecodeSaver
from src.utils.video_decode_save import VideoDecodeSaver

app = Flask(__name__)

@app.route("/", methods=['GET'])
def index():
    return "Agent Social Media API is running!", 200

@app.route("/health", methods=['GET'])
def health():
    return jsonify({"status": "ok"}), 200

@app.route("/messages-upsert", methods=['POST'])
def webhook():
    try:
        data = request.get_json()  
        
        print(data)
                
        msg = Message(data)
        texto = msg.get_text()
        
        if msg.scope == Message.SCOPE_GROUP:    
            print(f"Grupo: {msg.group_id}")
            
            if str(msg.group_id) == "120363383673368986":
                 
                if msg.message_type == msg.TYPE_IMAGE:
                    image_path = ImageDecodeSaver.process(msg.image_base64)
                    
                    try:
                        result = InstagramSend.send_instagram(image_path, texto)
                        if result:
                            print("Post processado e enviado ao Instagram.")
                        else:
                            print("Não foi possível confirmar o status do post.")
                    except Exception as e:
                        print(f"Erro durante o envio para o Instagram: {str(e)}")
                    finally:
                        # Cleanup temp file
                        if os.path.exists(image_path):
                            try:
                                os.remove(image_path)
                                print(f"A imagem {image_path} foi apagada com sucesso.")
                            except Exception as e:
                                print(f"Erro ao apagar imagem temporária: {str(e)}")
                
                elif msg.message_type == msg.TYPE_VIDEO:
                    try:
                        # Processar vídeo recebido em base64
                        video_path = VideoDecodeSaver.process(msg.video_base64)
                        
                        # Verificar se o texto contém comandos específicos para reels
                        share_to_feed = True
                        hashtags = None
                        caption = texto
                        
                        # Verificar se há hashtags específicas no texto
                        if "#tags:" in texto.lower():
                            # Extrair hashtags do texto
                            parts = texto.split("#tags:", 1)
                            caption = parts[0].strip()
                            hashtags_text = parts[1].strip()
                            hashtags = [tag.strip() for tag in hashtags_text.split(',')]
                        
                        # Verificar se há comando para não compartilhar no feed
                        if "#nofeed" in texto.lower():
                            share_to_feed = False
                            caption = caption.replace("#nofeed", "").strip()
                        
                        # Enviar como reels
                        result = InstagramSend.send_reels(
                            video_path=video_path,
                            caption=caption,
                            inputs={
                                "hashtags": hashtags,
                                "share_to_feed": share_to_feed,
                                "content_type": "reel"
                            }
                        )
                        
                        if result:
                            print(f"Reels processado e enviado ao Instagram. ID: {result.get('id')}")
                            # O arquivo temporário é limpo pelo serviço
                        else:
                            print("Não foi possível confirmar o status do reels.")
                            
                    except Exception as e:
                        print(f"Erro durante o envio do reels para o Instagram: {str(e)}")
                        import traceback
                        print(traceback.format_exc())
                        
                    finally:
                        # Cleanup será feito pelo sistema de filas, mas garantir limpeza em caso de falha
                        if 'video_path' in locals() and os.path.exists(video_path):
                            try:
                                os.remove(video_path)
                                print(f"O vídeo {video_path} foi apagado com sucesso.")
                            except Exception as e:
                                print(f"Erro ao apagar vídeo temporário: {str(e)}")
                                
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        print(f"Erro no webhook: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/queue-stats", methods=['GET'])
def queue_stats():
    """Endpoint para monitoramento de estatísticas da fila"""
    try:
        stats = InstagramSend.get_queue_stats()
        return jsonify(stats), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/job-status/<job_id>", methods=['GET'])
def job_status(job_id):
    """Endpoint para verificar status de um job específico"""
    try:
        status = InstagramSend.check_post_status(job_id)
        return jsonify(status), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
        
@app.route("/job-history", methods=['GET'])
def job_history():
    """Endpoint para obter histórico de jobs"""
    try:
        limit = request.args.get('limit', default=10, type=int)
        history = InstagramSend.get_recent_posts(limit)
        return jsonify(history), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/post-reels", methods=['POST'])
def post_reels_api():
    """Endpoint para postar reels via API REST"""
    try:
        data = request.get_json()
        
        # Verificar campos obrigatórios
        if not data.get('video_base64'):
            return jsonify({"error": "Campo video_base64 é obrigatório"}), 400
            
        caption = data.get('caption', 'Novo video postado pelo agente de IA! 🚀')
        
        # Processar vídeo
        video_path = VideoDecodeSaver.process(data['video_base64'])
        
        # Configurar parâmetros do reels
        inputs = {
            "content_type": "reel",
            "hashtags": data.get('hashtags'),
            "share_to_feed": data.get('share_to_feed', True)
        }
        
        # Adicionar outros campos se fornecidos
        for field in ['estilo', 'pessoa', 'sentimento', 'emojs', 'girias', 'tamanho', 'genero']:
            if field in data:
                inputs[field] = data[field]
                
        # Opção de processamento assíncrono
        async_process = data.get('async', False)
        
        if async_process:
            # Modo assíncrono: usar sistema de filas
            job_id = InstagramSend.queue_reels(video_path, caption, inputs)
            return jsonify({
                "job_id": job_id,
                "status": "queued",
                "message": "Reels enfileirado para processamento"
            }), 202
        else:
            # Modo síncrono: processar imediatamente
            result = InstagramSend.send_reels(video_path, caption, inputs)
            
            if result:
                return jsonify({
                    "success": True,
                    "post_id": result.get('id'),
                    "permalink": result.get('permalink')
                }), 200
            else:
                return jsonify({
                    "success": False,
                    "error": "Falha ao publicar reels"
                }), 500
                
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=3000)