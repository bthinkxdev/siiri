from __future__ import annotations

import os
import uuid

from django import forms
from django.core import signing
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

PENDING_UPLOAD_DIR = "tmp/pending-uploads/"
PENDING_UPLOAD_SALT = "dashboard.pending-upload"
PENDING_UPLOAD_MAX_AGE = 60 * 60 * 24  # a stashed file is honoured for one day


def _suffix(name: str) -> str:
    return f"{name}_pending"


class PendingUploadMixin:
    """Mix into a (Model)Form and list the file fields to preserve in ``pending_upload_fields``."""

    pending_upload_fields: tuple[str, ...] = ()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pending_paths: dict[str, str] = {}
        self.pending_urls: dict[str, str] = {}
        self.pending_names: dict[str, str] = {}
        self._used_pending_paths: list[str] = []
        for name in self.pending_upload_fields:
            if name not in self.fields:
                continue
            self.fields[_suffix(name)] = forms.CharField(
                required=False,
                widget=forms.HiddenInput(attrs={"data-pending-upload": name}),
            )
            if not self.is_bound or self.files.get(self.add_prefix(name)):
                continue  # nothing submitted yet, or a new file was chosen (it wins)
            path = self._unsign(self.data.get(self.add_prefix(_suffix(name))))
            if path:
                self._remember(name, path)
                # the stashed file satisfies "required" for this submit
                self.fields[name].required = False

    # -- helpers ---------------------------------------------------------------
    @staticmethod
    def _unsign(token: str | None) -> str | None:
        if not token:
            return None
        try:
            path = signing.loads(token, salt=PENDING_UPLOAD_SALT, max_age=PENDING_UPLOAD_MAX_AGE)
        except signing.BadSignature:  # includes SignatureExpired
            return None
        if not isinstance(path, str) or not path.startswith(PENDING_UPLOAD_DIR) or ".." in path:
            return None
        return path if default_storage.exists(path) else None

    def _remember(self, name: str, path: str) -> None:
        self.pending_paths[name] = path
        self.pending_urls[name] = default_storage.url(path)
        self.pending_names[name] = os.path.basename(path)

    # -- validation ------------------------------------------------------------
    def clean(self):
        cleaned = super().clean()
        for name, path in self.pending_paths.items():
            if name in self.errors:
                continue
            with default_storage.open(path, "rb") as fh:
                cleaned[name] = ContentFile(fh.read(), name=os.path.basename(path))
            self._used_pending_paths.append(path)
        return cleaned

    # -- called by the view ----------------------------------------------------
    def stash_pending_uploads(self) -> None:
        """After a failed save: keep each valid uploaded file and point the hidden field at it."""
        if not self.is_bound:
            return
        data = None
        for name in self.pending_upload_fields:
            if name not in self.fields or name in self.errors:
                continue
            upload = self.files.get(self.add_prefix(name))
            if not upload:
                continue
            upload.seek(0)
            filename = os.path.basename(upload.name) or "upload"
            path = default_storage.save(f"{PENDING_UPLOAD_DIR}{uuid.uuid4().hex}/{filename}", upload)
            if data is None:
                data = self.data.copy()
            data[self.add_prefix(_suffix(name))] = signing.dumps(path, salt=PENDING_UPLOAD_SALT)
            self._remember(name, path)
        if data is not None:
            self.data = data

    def discard_used_pending_uploads(self) -> None:
        """After a successful save the stashed copies have been stored for real; drop them."""
        for path in self._used_pending_paths:
            try:
                default_storage.delete(path)
            except Exception:  # best effort; the cleanup command catches leftovers
                pass
        self._used_pending_paths = []
