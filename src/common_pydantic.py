"""
We use attribute docstrings to propagate documentation to the OpenAPI schema.

See Pydantic documentation:
https://pydantic.dev/docs/validation/latest/api/pydantic/config/#pydantic.config.ConfigDict.use_attribute_docstrings
"""

from pydantic import BaseModel, ConfigDict


class BaseSchema(BaseModel):
    model_config = ConfigDict(use_attribute_docstrings=True, extra="forbid")
