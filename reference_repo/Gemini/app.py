import os
import sys
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, project_root)
from flask import Flask, request, jsonify
from src.services.message import Message
from src.services.instagram_send import InstagramSend
from src.utils.image_decode_save import ImageDecodeSaver
from src.utils.video_decode_save import VideoDecodeSaver
from src.services.post_queue import RateLimitExceeded, ContentPolicyViolation
import logging

logger = logging.getLogger(__name__)

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
        logger.info(f"Received webhook data: {data}")  # Log incoming data
        msg = Message(data)
        texto = msg.get_text()

        if msg.scope == Message.SCOPE_GROUP:
            logger.info(f"Grupo: {msg.group_id}")  # Consistent logging
            if str(msg.group_id) == "120363383673368986":
                if msg.message_type == msg.TYPE_IMAGE:
                    image_path = ImageDecodeSaver.process(msg.image_base64)
                    try:
                        job_id = InstagramSend.queue_post(image_path, texto) # Use the queue
                        return jsonify({"status": "enqueued", "job_id": job_id}), 202 # Return job_id
                    except (RateLimitExceeded, ContentPolicyViolation, FileNotFoundError) as e:
                        logger.error(f"Error queueing image post: {e}")
                        return jsonify({"status": "error", "message": str(e)}), 400
                    except Exception as e:
                        logger.exception(f"Error queueing image post: {e}")  # Use logger.exception
                        return jsonify({"status": "error", "message": str(e)}), 500
                    finally:
                        if os.path.exists(image_path):
                            try:
                                os.remove(image_path)
                                logger.info(f"A imagem {image_path} foi apagada com sucesso.")
                            except Exception as e:
                                logger.warning(f"Erro ao apagar imagem temporária: {str(e)}")

                elif msg.message_type == msg.TYPE_VIDEO:
                    try:
                        video_path = VideoDecodeSaver.process(msg.video_base64)
                        share_to_feed = True
                        hashtags = None
                        caption = texto
                        if "#tags:" in texto.lower():
                            parts = texto.split("#tags:", 1)
                            caption = parts[0].strip()
                            hashtags_text = parts[1].strip()
                            hashtags = [tag.strip() for tag in hashtags_text.split(',')]
                        if "#nofeed" in texto.lower():
                            share_to_feed = False
                            caption = caption.replace("#nofeed", "").strip()

                        job_id = InstagramSend.queue_reels(video_path, caption, inputs={ # Use the queue
                            "hashtags": hashtags,
                            "share_to_feed": share_to_feed,
                            "content_type": "reel"
                        })
                        return jsonify({"status": "enqueued", "job_id": job_id}), 202

                    except (RateLimitExceeded, ContentPolicyViolation, FileNotFoundError) as e:
                        logger.error(f"Error queueing reels post: {e}")
                        return jsonify({"status": "error", "message": str(e)}), 400
                    except Exception as e:
                        logger.exception(f"Error queueing reels: {e}")  # Use logger.exception
                        return jsonify({"status": "error", "message": str(e)}), 500
                    finally:
                        if 'video_path' in locals() and os.path.exists(video_path):
                            try:
                                os.remove(video_path)
                                logger.info(f"O vídeo {video_path} foi apagado com sucesso.")  # Consistent logging
                            except Exception as e:
                                logger.warning(f"Erro ao apagar vídeo temporário: {str(e)}")
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        logger.exception(f"Erro no webhook: {str(e)}")  # Use logger.exception
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/queue-stats", methods=['GET'])
def queue_stats():
    """Endpoint para monitoramento de estatísticas da fila"""
    try:
        stats = InstagramSend.get_queue_stats()
        return jsonify(stats), 200
    except Exception as e:
        logger.exception(f"Erro ao obter status da fila: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/job-status/<job_id>", methods=['GET'])
def job_status(job_id):
    """Endpoint para verificar status de um job específico"""
    try:
        status = InstagramSend.check_post_status(job_id)
        return jsonify(status), 200
    except Exception as e:
        logger.exception(f"Error getting job status for {job_id}: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/job-history", methods=['GET'])
def job_history():
    """Endpoint para obter histórico de jobs"""
    try:
        limit = request.args.get('limit', default=10, type=int)
        history = InstagramSend.get_recent_posts(limit)
        return jsonify(history), 200
    except Exception as e:
        logger.exception(f"Error retrieving job history: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/post-reels", methods=['POST'])
def post_reels_api():
    """Endpoint para postar reels via API REST"""
    try:
        data = request.get_json()
        if not data.get('video_base64'):
            return jsonify({"error": "Campo video_base64 é obrigatório"}), 400
        caption = data.get('caption', 'Novo video postado pelo agente de IA! 🚀')
        video_path = VideoDecodeSaver.process(data['video_base64'])
        inputs = {
            "content_type": "reel",
            "hashtags": data.get('hashtags'),
            "share_to_feed": data.get('share_to_feed', True)
        }
        for field in ['estilo', 'pessoa', 'sentimento', 'emojs', 'girias', 'tamanho', 'genero']:
            if field in data:
                inputs[field] = data[field]

        async_process = data.get('async', False)  # Check for async flag

        if async_process:
            job_id = InstagramSend.queue_reels(video_path, caption, inputs)
            return jsonify({
                "job_id": job_id,
                "status": "queued",
                "message": "Reels enfileirado para processamento"
            }), 202
        else:
            #  Process immediately (not recommended for production)
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
        logger.exception(f"Error posting reels via API: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=3000)