from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import requests


DEFAULT_GRAPH_HOST = "https://graph.facebook.com"
DEFAULT_API_VERSION = "v25.0"


class InstagramApiError(RuntimeError):
    pass


@dataclass(frozen=True)
class InstagramConfig:
    ig_user_id: str
    access_token: str
    api_version: str = DEFAULT_API_VERSION
    graph_host: str = DEFAULT_GRAPH_HOST

    @property
    def base_url(self) -> str:
        host = self.graph_host.rstrip("/")
        version = self.api_version.strip().lstrip("/")
        return f"{host}/{version}"


@dataclass(frozen=True)
class PublishResult:
    container_id: str
    instagram_post_id: str
    final_status: str


LogCallback = Callable[[str], None]


class InstagramClient:
    def __init__(self, config: InstagramConfig) -> None:
        self.config = config

    def test_connection(self) -> dict[str, object]:
        data = self._request_json(
            "GET",
            f"{self.config.base_url}/{self.config.ig_user_id}",
            params={
                "fields": "id,name,account_type",
                "access_token": self.config.access_token,
            },
        )
        return data

    def publish_local_video(
        self,
        video_path: Path,
        caption: str,
        *,
        media_type: str = "REELS",
        share_to_feed: bool = True,
        log_callback: LogCallback | None = None,
    ) -> PublishResult:
        if not video_path.is_file():
            raise InstagramApiError("O vídeo selecionado não foi encontrado.")

        self._log(log_callback, "Criando container de mídia no Instagram.")
        container = self.create_media_container(
            caption=caption,
            media_type=media_type,
            share_to_feed=share_to_feed,
        )
        container_id = str(container.get("id") or "")
        if not container_id:
            raise InstagramApiError("A API não retornou o ID do container.")

        upload_uri = str(container.get("uri") or "")
        self._log(log_callback, "Enviando vídeo local para o container.")
        self.upload_video(container_id, video_path, upload_uri=upload_uri or None)

        self._log(log_callback, "Aguardando processamento do vídeo.")
        final_status = self.wait_until_container_ready(container_id, log_callback=log_callback)

        self._log(log_callback, "Publicando no Instagram.")
        published = self.publish_container(container_id)
        instagram_post_id = str(published.get("id") or "")
        if not instagram_post_id:
            raise InstagramApiError("A API não retornou o ID da publicação.")

        return PublishResult(
            container_id=container_id,
            instagram_post_id=instagram_post_id,
            final_status=final_status,
        )

    def create_media_container(
        self,
        *,
        caption: str,
        media_type: str = "REELS",
        share_to_feed: bool = True,
    ) -> dict[str, object]:
        payload: dict[str, object] = {
            "media_type": media_type,
            "upload_type": "resumable",
            "caption": caption,
            "access_token": self.config.access_token,
        }
        if media_type.upper() == "REELS":
            payload["share_to_feed"] = str(share_to_feed).lower()

        return self._request_json(
            "POST",
            f"{self.config.base_url}/{self.config.ig_user_id}/media",
            data=payload,
            timeout=(30, 120),
        )

    def upload_video(self, container_id: str, video_path: Path, *, upload_uri: str | None = None) -> dict[str, object]:
        file_size = video_path.stat().st_size
        url = upload_uri or f"https://rupload.facebook.com/ig-api-upload/{self.config.api_version}/{container_id}"
        headers = {
            "Authorization": f"OAuth {self.config.access_token}",
            "offset": "0",
            "file_size": str(file_size),
            "Content-Type": "application/octet-stream",
        }

        with video_path.open("rb") as video_file:
            return self._request_json(
                "POST",
                url,
                headers=headers,
                data=video_file,
                timeout=(30, 900),
            )

    def get_container_status(self, container_id: str) -> dict[str, object]:
        return self._request_json(
            "GET",
            f"{self.config.base_url}/{container_id}",
            params={
                "fields": "status_code,status",
                "access_token": self.config.access_token,
            },
        )

    def wait_until_container_ready(
        self,
        container_id: str,
        *,
        log_callback: LogCallback | None = None,
        timeout_seconds: int = 600,
        interval_seconds: int = 10,
    ) -> str:
        deadline = time.monotonic() + timeout_seconds
        last_status = ""

        while time.monotonic() < deadline:
            status = self.get_container_status(container_id)
            status_code = str(status.get("status_code") or status.get("status") or "")
            if status_code and status_code != last_status:
                self._log(log_callback, f"Status do container: {status_code}")
                last_status = status_code

            if status_code.upper() in {"FINISHED", "PUBLISHED"}:
                return status_code

            if status_code.upper() in {"ERROR", "EXPIRED"}:
                raise InstagramApiError(f"O processamento do container falhou: {status_code}")

            time.sleep(interval_seconds)

        raise InstagramApiError("Tempo limite excedido aguardando o processamento do vídeo.")

    def publish_container(self, container_id: str) -> dict[str, object]:
        return self._request_json(
            "POST",
            f"{self.config.base_url}/{self.config.ig_user_id}/media_publish",
            data={
                "creation_id": container_id,
                "access_token": self.config.access_token,
            },
            timeout=(30, 120),
        )

    def _request_json(self, method: str, url: str, **kwargs) -> dict[str, object]:
        try:
            response = requests.request(method, url, **kwargs)
        except requests.RequestException as exc:
            raise InstagramApiError(f"Falha de conexão com a API: {exc}") from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise InstagramApiError(f"A API retornou uma resposta inválida. HTTP {response.status_code}") from exc

        if response.status_code >= 400 or (isinstance(data, dict) and data.get("error")):
            error = data.get("error") if isinstance(data, dict) else None
            if isinstance(error, dict):
                message = str(error.get("message") or error)
            else:
                message = str(data)
            raise InstagramApiError(f"Erro da API. HTTP {response.status_code}: {message}")

        if not isinstance(data, dict):
            raise InstagramApiError("A API retornou um formato inesperado.")

        return data

    def _log(self, callback: LogCallback | None, message: str) -> None:
        if callback:
            callback(message)
