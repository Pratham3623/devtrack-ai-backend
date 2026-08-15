import pytest
import os
import uuid
from pathlib import Path
from unittest.mock import patch
from app.core.config import settings
from app.core.storage import LocalStorageBackend, get_storage
from app.repositories.file_repository import FileRepository

@pytest.mark.asyncio
async def test_storage_factory_local_and_s3():
    # Test local backend default
    with patch.object(settings, "USE_S3", False):
        storage = get_storage()
        assert isinstance(storage, LocalStorageBackend)

@pytest.mark.asyncio
async def test_local_storage_upload_download_delete(tmp_path):
    backend = LocalStorageBackend()
    backend.upload_dir = Path(tmp_path)
    
    test_content = b"DevTrack AI Test File Storage Content"
    key = "test_file.txt"
    
    # Upload (key: str, data: bytes, content_type: str)
    res_key = await backend.upload(key, test_content, "text/plain")
    assert res_key == key
    assert (Path(tmp_path) / key).exists()

    # Download
    downloaded = await backend.download(key)
    assert downloaded == test_content

    # Get signed URL (file_id)
    fake_file_id = str(uuid.uuid4())
    url = await backend.get_signed_url(fake_file_id)
    assert "/files/serve/" in url

    # Delete
    await backend.delete(key)
    assert not (Path(tmp_path) / key).exists()

def test_config_settings_defaults():
    assert settings.APP_NAME == "DevTrack AI Engine"
    assert settings.SECRET_KEY != ""
    assert settings.ALGORITHM == "HS256"

@pytest.mark.asyncio
async def test_file_repository_edge_cases(db_session):
    repo = FileRepository(db_session)
    dummy_file_id = str(uuid.uuid4())
    dummy_org_id = str(uuid.uuid4())
    
    # Test getting non-existent file
    file_obj = await repo.get_file_by_id(file_id=dummy_file_id, org_id=dummy_org_id)
    assert file_obj is None

    # Test listing files on empty DB
    files, total = await repo.list_files(org_id=dummy_org_id)
    assert files == []
    assert total == 0
