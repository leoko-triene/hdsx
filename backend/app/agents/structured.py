import json
import re
from typing import Any, Callable, TypeVar

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)


class GradingEvidence(StrictModel):
    point: str = ""
    source: str = ""


class GradingOutput(StrictModel):
    score: float = Field(ge=0)
    confidence: float = Field(ge=0, le=1)
    feedback: str = Field(min_length=1)
    evidence: list[GradingEvidence] = Field(default_factory=list)


class AssignmentMaterial(StrictModel):
    material_type: str = Field(pattern="^(example|exercise|thinking|extension)$")
    question_type: str = Field(pattern="^(single_choice|multiple_choice|true_false|short_answer|essay)$")
    stem: str = Field(min_length=1)
    standard_answer: str = Field(min_length=1)
    explanation: str = Field(default="")
    options: list[dict[str, str]] | None = None
    max_score: float = Field(ge=1, le=20)


class AssignmentMaterialsOutput(StrictModel):
    items: list[AssignmentMaterial] = Field(min_length=1)


class ParentReportOutput(StrictModel):
    overview: str = Field(min_length=1)
    highlights: list[str] = Field(default_factory=list)
    needs_attention: list[str] = Field(default_factory=list)
    action_plan: list[str] = Field(default_factory=list)
    encouragement: str = Field(min_length=1)
    metrics_explanation: str = Field(min_length=1)


T = TypeVar("T", bound=BaseModel)


def extract_json(raw: str) -> Any:
    value = re.sub(r"^```(?:json)?\s*|\s*```$", "", str(raw).strip(), flags=re.I)
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        starts = [i for i in (value.find("{"), value.find("[")) if i >= 0]
        if not starts:
            raise
        start = min(starts)
        end = max(value.rfind("}"), value.rfind("]"))
        if end <= start:
            raise
        return json.loads(value[start:end + 1])


def validate_or_fallback(raw: str, model: type[T], fallback: Callable[[], T], normalize: Callable[[Any], Any] | None = None) -> T:
    """Parse untrusted model text and always return a validated contract object."""
    try:
        value = extract_json(raw)
        if normalize:
            value = normalize(value)
        return model.model_validate(value)
    except (json.JSONDecodeError, TypeError, ValueError, ValidationError, AttributeError):
        return model.model_validate(fallback())
