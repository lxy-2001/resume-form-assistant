from pathlib import Path

from resume_agent.profile.models import ProfileSnapshot
from resume_agent.storage.base import AtomicWriter, ProfileStore
from resume_agent.storage.key_provider import KeyProvider


class FakeStore:
    def __init__(self): self.written=[]; self.deleted=False
    def read(self): return self.written[-1] if self.written else None
    def write(self, snapshot): self.written.append(snapshot)
    def delete(self): self.deleted=True
class FakeKeys:
    def get_key(self): return None
    def provision_key(self): return b"synthetic"
    def destroy_key(self): return True
class FakeWriter:
    def __init__(self): self.calls=[]
    def write_atomic(self, destination, payload): self.calls.append((destination,payload))
def test_representative_fakes_satisfy_protocols_without_io():
    store,keys,writer=FakeStore(),FakeKeys(),FakeWriter()
    assert isinstance(store,ProfileStore); assert isinstance(keys,KeyProvider); assert isinstance(writer,AtomicWriter)
    assert store.read() is None
    marker=object.__new__(ProfileSnapshot); store.write(marker)
    assert store.read() is marker; store.delete(); assert store.deleted
    assert keys.get_key() is None; assert keys.provision_key()==b"synthetic"; assert keys.destroy_key()
    destination=Path("synthetic-profile.bin"); writer.write_atomic(destination,b"ciphertext")
    assert writer.calls==[(destination,b"ciphertext")]; assert not destination.exists()
