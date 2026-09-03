from pathlib import Path

from resume_agent.profile.models import ProfileSnapshot
from resume_agent.storage.base import AtomicWriter, ProfileStore
from resume_agent.storage.key_provider import KeyProvider


class FakeStore:
    def read(self) -> ProfileSnapshot | None: return None
    def write(self, snapshot: ProfileSnapshot) -> None: pass
    def delete(self) -> None: pass


class FakeKeys:
    def get_key(self) -> bytes | None: return None
    def provision_key(self) -> bytes | None: return b"synthetic"
    def destroy_key(self) -> bool: return True


class FakeWriter:
    def write_atomic(self, destination: Path, payload: bytes) -> None: pass


def test_representative_fakes_satisfy_protocols_without_io() -> None:
    assert isinstance(FakeStore(), ProfileStore)
    assert isinstance(FakeKeys(), KeyProvider)
    assert isinstance(FakeWriter(), AtomicWriter)

