"""GitLab Downloader."""

import re
from typing import Self
from urllib.parse import quote, urlparse

import requests
from loguru import logger

from src.app import APP
from src.config import RevancedConfig
from src.downloader.download import Downloader
from src.exceptions import DownloadError
from src.utils import handle_request_response, request_timeout


class GitLab(Downloader):
    """Files downloader from GitLab."""

    MIN_PATH_SEGMENTS = 2

    def latest_version(self: Self, app: APP, **kwargs: dict[str, str]) -> tuple[str, str]:
        """Not implemented for GitLab APK downloads."""
        msg = "GitLab downloader only supports patch resources."
        raise DownloadError(msg)

    @staticmethod
    def _extract_repo_info(url: str) -> tuple[str, str]:
        """Extract owner and repo name from GitLab URL."""
        parsed_url = urlparse(url)
        path_segments = parsed_url.path.strip("/").split("/")
        if len(path_segments) < GitLab.MIN_PATH_SEGMENTS:
            msg = f"Invalid GitLab URL format: {url}"
            raise DownloadError(msg)
        return path_segments[0], path_segments[1]

    @staticmethod
    def patch_resource(repo_url: str, assets_filter: str, config: RevancedConfig) -> tuple[str, str]:
        """Fetch latest patch resource from a GitLab repo URL."""
        owner, repo_name = GitLab._extract_repo_info(repo_url)
        encoded_path = quote(f"{owner}/{repo_name}", safe="")
        api_url = f"https://gitlab.com/api/v4/projects/{encoded_path}/releases"

        headers: dict[str, str] = {}
        if config.personal_access_token:
            logger.debug("Using personal access token for GitLab")
            headers["PRIVATE-TOKEN"] = config.personal_access_token

        response = requests.get(api_url, headers=headers, timeout=request_timeout)
        handle_request_response(response, api_url)

        releases = response.json()
        if not releases:
            msg = f"No releases found for {owner}/{repo_name} on GitLab"
            raise DownloadError(msg, url=api_url)

        latest_release = releases[0]
        tag_name = latest_release["tag_name"]

        try:
            filter_pattern = re.compile(assets_filter)
        except re.error as e:
            msg = f"Invalid regex {assets_filter} pattern provided."
            raise DownloadError(msg) from e

        links = latest_release.get("assets", {}).get("links", [])
        for link in links:
            link_url = link.get("url", "")
            link_name = link.get("name", "")
            if filter_pattern.search(link_url) or filter_pattern.search(link_name):
                logger.debug(f"Found {link_name} to be downloaded from {link_url}")
                return tag_name, link_url

        msg = f"No asset matching '{assets_filter}' in {owner}/{repo_name} release {tag_name}"
        raise DownloadError(msg, url=api_url)
