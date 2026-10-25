"""Import-safe native generator integration; callers cannot supply server extras."""
import inspect
from collections.abc import Mapping
from functools import wraps


def install_generator_boundary(generator):
    for name in ('generate', 'single_iteration_generate', 'single_loop_generate'):
        original = getattr(generator, name, None)
        if original is None:
            continue
        signature = inspect.signature(original)
        def wrap(method, signature):
            @wraps(method)
            def call(*args, **kwargs):
                from company_projects.runtime_models import prepare
                bound = signature.bind(*args, **kwargs)
                supplied = bound.arguments['args']
                inputs = supplied.get('inputs', {}) if isinstance(supplied, Mapping) else supplied.inputs
                workflow, clean, selection = prepare(bound.arguments['workflow'], bound.arguments['user'], inputs)
                if isinstance(supplied, Mapping):
                    supplied = dict(supplied, inputs=clean, _kara_runtime_selection=selection)
                else:
                    supplied = supplied.model_copy(update={'inputs': clean})
                    object.__setattr__(supplied, '_kara_runtime_selection', selection)
                bound.arguments.update(workflow=workflow, args=supplied)
                return method(*bound.args, **bound.kwargs)
            return call
        setattr(generator, name, wrap(original, signature))
    return generator
