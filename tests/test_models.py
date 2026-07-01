import pytest
from pydantic import ValidationError

from gazette.models import Technique, Parameter, RawRecord


def test_technique_defaults():
    t = Technique(title="t", summary="s", body="b", domain="LoRA training",
                  dedup_key="k", confidence=0.8)
    assert t.status == "published"
    assert t.is_actionable is True
    assert t.tags == []
    assert t.domain_meta == {}


def test_confidence_is_bounded():
    with pytest.raises(ValidationError):
        Technique(title="t", summary="s", body="b", domain="d",
                  dedup_key="k", confidence=1.5)


def test_parameter_and_rawrecord():
    p = Parameter(key="network_dim", value="32")
    assert p.unit is None
    r = RawRecord(external_id="pr-2379", url=None, author="kohya",
                  raw_text="use --fused_backward_pass")
    assert r.metadata == {}
    assert r.score is None
