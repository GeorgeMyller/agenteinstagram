import os
import sys
import json
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.instagram_send import InstagramSend

def check_job_status(job_id):
    """
    Verifica o status detalhado de um job específico
    """
    print(f"Verificando status do job: {job_id}")
    
    # Obter status do job
    job = InstagramSend.check_post_status(job_id)
    
    if not job:
        print("Job não encontrado")
        return
    
    # Mostrar detalhes do job de forma formatada
    print("\n--- DETALHES DO JOB ---")
    print(f"ID: {job.get('id', 'N/A')}")
    print(f"Status: {job.get('status', 'N/A')}")
    print(f"Tipo de conteúdo: {job.get('content_type', 'N/A')}")
    
    # Datas formatadas
    created_at = job.get('created_at', 'N/A')
    updated_at = job.get('updated_at', 'N/A')
    print(f"Criado em: {created_at}")
    print(f"Atualizado em: {updated_at}")
    
    # Detalhes do resultado ou erro
    if job.get('result'):
        print("\nResultado:")
        print(json.dumps(job.get('result'), indent=2))
    
    if job.get('error'):
        print("\nErro:")
        print(job.get('error'))
    
    # Caminhos de mídia
    if 'media_paths' in job:
        print("\nCaminhos de mídia:")
        for path in job.get('media_paths', []):
            exists = "✓" if os.path.exists(path) else "✗"
            print(f"- {path} {exists}")
    
    # Dados adicionais
    print("\nMetadados adicionais:")
    for key, value in job.items():
        if key not in ['id', 'status', 'content_type', 'created_at', 'updated_at', 'result', 'error', 'media_paths']:
            if isinstance(value, dict) or isinstance(value, list):
                print(f"{key}: {json.dumps(value, indent=2)}")
            else:
                print(f"{key}: {value}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python check_job_status.py <job_id>")
        sys.exit(1)
        
    job_id = sys.argv[1]
    check_job_status(job_id)