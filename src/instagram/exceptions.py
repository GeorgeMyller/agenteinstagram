"""
Este módulo contém todas as exceções personalizadas usadas na integração com o Instagram.
Todas as exceções herdam da classe base InstagramError.
"""

class InstagramError(Exception):
    """Classe base para todas as exceções relacionadas ao Instagram"""
    def __init__(self, message: str, error_code: str = None, 
                 error_subcode: str = None, fb_trace_id: str = None,
                 is_retriable: bool = False):
        self.error_code = error_code
        self.error_subcode = error_subcode
        self.fb_trace_id = fb_trace_id
        self.is_retriable = is_retriable
        super().__init__(message)

    def __str__(self):
        details = []
        if self.error_code:
            details.append(f"Code: {self.error_code}")
        if self.error_subcode:
            details.append(f"Subcode: {self.error_subcode}")
        if self.fb_trace_id:
            details.append(f"FB Trace ID: {self.fb_trace_id}")
        
        base_message = super().__str__()
        if details:
            return f"{base_message} ({', '.join(details)})"
        return base_message

class AuthenticationError(InstagramError):
    """Erro de autenticação (token expirado, inválido, etc)"""
    pass

class PermissionError(InstagramError):
    """Erro de permissões (escopos faltando, etc)"""
    pass

class RateLimitError(InstagramError):
    """Erro quando os limites de taxa são excedidos"""
    def __init__(self, *args, retry_after: int = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.retry_after = retry_after
        self.is_retriable = True

class ContentPolicyViolation(InstagramError):
    """Erro quando o conteúdo viola as políticas do Instagram"""
    pass

class MediaError(InstagramError):
    """Erro relacionado à mídia (formato, tamanho, falha no upload)"""
    pass

class ValidationError(InstagramError):
    """Erro quando a validação de mídia ou dados falha"""
    pass

class ConfigurationError(InstagramError):
    """Erro relacionado à configuração (credenciais faltando, etc)"""
    pass

class TemporaryError(InstagramError):
    """Erro temporário que pode ser tentado novamente"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.is_retriable = True