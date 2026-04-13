"""
Memory layer — Namespace isolation tests.

Tests that private namespaces:
  - enforce key-based access
  - cannot be read across namespace boundaries
  - persist and survive registry reload
  - support key rotation and deletion
"""

from __future__ import annotations

import numpy as np
import pytest
from pathlib import Path

from engram.miner.namespace import NamespaceRegistry
from engram.miner.store import FAISSStore, VectorRecord


# ── NamespaceRegistry ────────────────────────────────────────────────────────

@pytest.fixture
def registry(tmp_path: Path) -> NamespaceRegistry:
    return NamespaceRegistry(path=tmp_path / "namespaces.json")


def test_create_and_verify(registry: NamespaceRegistry) -> None:
    registry.create("team_alpha", "supersecretkey1234")
    assert registry.verify("team_alpha", "supersecretkey1234")


def test_wrong_key_rejected(registry: NamespaceRegistry) -> None:
    registry.create("team_alpha", "supersecretkey1234")
    assert not registry.verify("team_alpha", "wrongkey1234567890")


def test_unknown_namespace_rejected(registry: NamespaceRegistry) -> None:
    assert not registry.verify("nonexistent", "anykey1234567890")


def test_duplicate_namespace_raises(registry: NamespaceRegistry) -> None:
    registry.create("ns_one", "validkey1234567890")
    with pytest.raises(ValueError, match="already exists"):
        registry.create("ns_one", "anotherkey1234567890")


def test_invalid_name_raises(registry: NamespaceRegistry) -> None:
    with pytest.raises(ValueError, match="valid identifier"):
        registry.create("bad-name!", "validkey1234567890")


def test_short_key_raises(registry: NamespaceRegistry) -> None:
    with pytest.raises(ValueError, match="16 characters"):
        registry.create("myns", "tooshort")


def test_exists(registry: NamespaceRegistry) -> None:
    assert not registry.exists("myns")
    registry.create("myns", "validkey1234567890")
    assert registry.exists("myns")


def test_delete_with_correct_key(registry: NamespaceRegistry) -> None:
    registry.create("myns", "validkey1234567890")
    assert registry.delete("myns", "validkey1234567890")
    assert not registry.exists("myns")


def test_delete_with_wrong_key_fails(registry: NamespaceRegistry) -> None:
    registry.create("myns", "validkey1234567890")
    assert not registry.delete("myns", "wrongkeywrongkey")
    assert registry.exists("myns")


def test_rotate_key(registry: NamespaceRegistry) -> None:
    registry.create("myns", "oldkey1234567890xx")
    assert registry.rotate_key("myns", "oldkey1234567890xx", "newkey9876543210xx")
    assert not registry.verify("myns", "oldkey1234567890xx")
    assert registry.verify("myns", "newkey9876543210xx")


def test_rotate_key_wrong_old_fails(registry: NamespaceRegistry) -> None:
    registry.create("myns", "oldkey1234567890xx")
    assert not registry.rotate_key("myns", "wrongold12345678", "newkey9876543210xx")
    # Old key still works
    assert registry.verify("myns", "oldkey1234567890xx")


def test_persistence_across_reload(tmp_path: Path) -> None:
    """Registry loaded from disk should have the same namespaces."""
    path = tmp_path / "namespaces.json"
    reg1 = NamespaceRegistry(path=path)
    reg1.create("persistent_ns", "persistentkey12345")

    # Load fresh registry from same path
    reg2 = NamespaceRegistry(path=path)
    assert reg2.exists("persistent_ns")
    assert reg2.verify("persistent_ns", "persistentkey12345")


def test_list_namespaces(registry: NamespaceRegistry) -> None:
    registry.create("ns_a", "keyfornamespace_a1")
    registry.create("ns_b", "keyfornamespace_b1")
    names = registry.list_namespaces()
    assert "ns_a" in names
    assert "ns_b" in names


def test_key_not_stored_in_plaintext(tmp_path: Path) -> None:
    """The registry JSON file must never contain the plaintext key."""
    path = tmp_path / "namespaces.json"
    reg = NamespaceRegistry(path=path)
    secret = "supersecretpassword1234"
    reg.create("protected", secret)
    content = path.read_text()
    assert secret not in content


# ── Store namespace isolation ─────────────────────────────────────────────────

def _vec(values: list[float]) -> np.ndarray:
    return np.array(values, dtype=np.float32)


@pytest.fixture
def store() -> FAISSStore:
    return FAISSStore(dim=4)


def test_public_and_private_dont_mix(store: FAISSStore) -> None:
    """Records in different namespaces must not appear in each other's searches."""
    store.upsert(VectorRecord(
        cid="public_cid",
        embedding=_vec([1.0, 0.0, 0.0, 0.0]),
        namespace="__public__",
    ))
    store.upsert(VectorRecord(
        cid="private_cid",
        embedding=_vec([1.0, 0.0, 0.0, 0.0]),
        namespace="team_private",
    ))

    public_results = store.search(_vec([1.0, 0.0, 0.0, 0.0]), namespace="__public__")
    private_results = store.search(_vec([1.0, 0.0, 0.0, 0.0]), namespace="team_private")

    public_cids = {r.cid for r in public_results}
    private_cids = {r.cid for r in private_results}

    assert "public_cid" in public_cids
    assert "private_cid" not in public_cids
    assert "private_cid" in private_cids
    assert "public_cid" not in private_cids


def test_two_private_namespaces_isolated(store: FAISSStore) -> None:
    """Two private namespaces cannot read each other's records."""
    store.upsert(VectorRecord(
        cid="cid_alpha",
        embedding=_vec([1.0, 0.0, 0.0, 0.0]),
        namespace="ns_alpha",
    ))
    store.upsert(VectorRecord(
        cid="cid_beta",
        embedding=_vec([1.0, 0.0, 0.0, 0.0]),
        namespace="ns_beta",
    ))

    alpha_results = {r.cid for r in store.search(_vec([1.0, 0.0, 0.0, 0.0]), namespace="ns_alpha")}
    beta_results = {r.cid for r in store.search(_vec([1.0, 0.0, 0.0, 0.0]), namespace="ns_beta")}

    assert "cid_alpha" in alpha_results and "cid_beta" not in alpha_results
    assert "cid_beta" in beta_results and "cid_alpha" not in beta_results


def test_get_cross_namespace_returns_none(store: FAISSStore) -> None:
    """Fetching a CID from the wrong namespace must return None."""
    store.upsert(VectorRecord(
        cid="my_secret_cid",
        embedding=_vec([0.5, 0.5, 0.0, 0.0]),
        namespace="secret_ns",
    ))
    # Correct namespace works
    assert store.get("my_secret_cid", namespace="secret_ns") is not None
    # Wrong namespace returns nothing
    assert store.get("my_secret_cid", namespace="__public__") is None
    assert store.get("my_secret_cid", namespace="other_ns") is None


def test_many_records_same_vector_different_namespaces(store: FAISSStore) -> None:
    """Many records with identical vectors in N namespaces all stay separated."""
    namespaces = [f"ns_{i}" for i in range(5)]
    query = _vec([1.0, 0.0, 0.0, 0.0])

    for i, ns in enumerate(namespaces):
        store.upsert(VectorRecord(cid=f"cid_{ns}", embedding=query, namespace=ns))

    for ns in namespaces:
        results = {r.cid for r in store.search(query, namespace=ns)}
        assert f"cid_{ns}" in results
        for other in namespaces:
            if other != ns:
                assert f"cid_{other}" not in results
