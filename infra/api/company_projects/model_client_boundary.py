"""Import-safe plugin boundary installation; model/DB imports stay lazy."""
import inspect
from functools import wraps

MODEL_METHODS = {
    'invoke_llm': 'llm', 'get_llm_num_tokens': 'llm', 'start_llm_polling': 'llm', 'check_llm_polling': 'llm',
    'invoke_text_embedding': 'text-embedding', 'invoke_multimodal_embedding': 'text-embedding',
    'get_text_embedding_num_tokens': 'text-embedding', 'invoke_rerank': 'rerank',
    'invoke_multimodal_rerank': 'rerank', 'invoke_tts': 'tts', 'get_tts_model_voices': 'tts',
    'invoke_speech_to_text': 'speech2text', 'invoke_moderation': 'moderation',
    'get_model_schema': None, 'validate_model_credentials': None, 'validate_provider_credentials': None,
}


def install_client_boundary(client_type):
    for name, method in inspect.getmembers(client_type, inspect.isfunction):
        signature = inspect.signature(method)
        if 'credentials' not in signature.parameters:
            continue
        if name not in MODEL_METHODS:
            raise RuntimeError('Unguarded plugin model credential method: ' + name)
        def wrap(original, signature, name):
            def prepare(args, kwargs):
                from company_projects.personal_model_runtime import bound_credentials
                bound = signature.bind(*args, **kwargs)
                bound.apply_defaults()
                bound_credentials(name, bound.arguments)
                return bound
            if inspect.isgeneratorfunction(original):
                @wraps(original)
                def stream(*args, **kwargs):
                    bound = prepare(args, kwargs)
                    if name != 'get_model_schema':
                        from company_projects.local_rpc import model_call
                        yield from model_call(name, bound.arguments)
                        return
                    try:
                        yield from original(*bound.args, **bound.kwargs)
                    except Exception:
                        # Provider messages may echo keys; never persist them in
                        # shared workflow errors, logs or execution artifacts.
                        raise ValueError('فراخوانی مدل شخصی ناموفق بود؛ توکن، مجوز مدل، نشانی و شبکه را بررسی کنید.') from None
                return stream
            @wraps(original)
            def call(*args, **kwargs):
                bound = prepare(args, kwargs)
                if name != 'get_model_schema':
                    from company_projects.local_rpc import model_call
                    return model_call(name, bound.arguments)
                try:
                    return original(*bound.args, **bound.kwargs)
                except Exception:
                    raise ValueError('فراخوانی مدل شخصی ناموفق بود؛ توکن، مجوز مدل، نشانی و شبکه را بررسی کنید.') from None
            return call
        setattr(client_type, name, wrap(method, signature, name))
    return client_type
