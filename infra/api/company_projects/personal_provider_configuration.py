"""Native selector/model instances backed exclusively by the caller's registry."""
from core.entities.model_entities import ModelStatus, ModelWithProviderEntity, SimpleModelProviderEntity
from core.entities.provider_configuration import ProviderConfiguration
from graphon.model_runtime.entities.model_entities import FetchFrom


class PersonalProviderConfiguration(ProviderConfiguration):
    def get_provider_models(self, model_type=None, only_active=False, model=None):
        result = []
        for item in self.custom_configuration.models:
            if (model_type and item.model_type != model_type) or (model and item.model != model):
                continue
            schema = self.get_model_schema(model_type=item.model_type, model=item.model, credentials=item.credentials)
            if schema is None:
                continue
            result.append(ModelWithProviderEntity(model=item.model, label=schema.label, model_type=item.model_type,
                features=schema.features, fetch_from=FetchFrom.CUSTOMIZABLE_MODEL, model_properties=schema.model_properties,
                deprecated=schema.deprecated, provider=SimpleModelProviderEntity(self.provider), status=ModelStatus.ACTIVE,
                load_balancing_enabled=False, has_invalid_load_balancing_configs=False))
        return result
