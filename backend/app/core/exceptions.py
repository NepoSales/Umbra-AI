class ServiceError(Exception):
    """Erro de regra de negócio. O main.py converte cada subclasse em uma resposta HTTP."""

class ConflictError(ServiceError):
    pass

class AuthenticationError(ServiceError):
    pass
