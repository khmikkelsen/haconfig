"""Repository data."""
from datetime import datetime
import json
from typing import List, Optional

import attr
from homeassistant.helpers.json import JSONEncoder


@attr.s(auto_attribs=True)
class RepositoryData:
    """RepositoryData class."""

    archived: bool = False
    authors: List[str] = []
    category: str = ""
    content_in_root: bool = False
    country: List[str] = []
    config_flow: bool = False
    default_branch: str = None
    description: str = ""
    domain: str = ""
    domains: List[str] = []
    downloads: int = 0
    etag_repository: str = None
    file_name: str = ""
    filename: str = ""
    first_install: bool = False
    fork: bool = False
    full_name: str = ""
    hacs: str = None  # Minimum HACS version
    hide: bool = False
    hide_default_branch: bool = False
    homeassistant: str = None  # Minimum Home Assistant version
    id: int = 0
    iot_class: str = None
    installed: bool = False
    installed_commit: str = None
    installed_version: str = None
    open_issues: int = 0
    last_commit: str = None
    last_version: str = None
    last_updated: str = 0
    manifest_name: str = None
    new: bool = True
    persistent_directory: str = None
    pushed_at: str = ""
    releases: bool = False
    render_readme: bool = False
    published_tags: List[str] = []
    selected_tag: str = None
    show_beta: bool = False
    stargazers_count: int = 0
    topics: List[str] = []
    zip_release: bool = False
    _storage_data: Optional[dict] = None

    @property
    def stars(self):
        """Return the stargazers count."""
        return self.stargazers_count or 0

    @property
    def name(self):
        """Return the name."""
        if self.category in ["integration", "netdaemon"]:
            return self.domain
        return self.full_name.split("/")[-1]

    def to_json(self):
        """Export to json."""
        return attr.asdict(self, filter=lambda attr, _: attr.name != "_storage_data")

    def memorize_storage(self, data) -> None:
        """Memorize the storage data."""
        self._storage_data = data

    def export_data(self) -> Optional[dict]:
        """Export to json if the data has changed.

        Returns the data to export if the data needs
        to be written.

        Returns None if the data has not changed.
        """
        export = json.loads(json.dumps(self.to_json(), cls=JSONEncoder))
        return None if self._storage_data == export else export

    @staticmethod
    def create_from_dict(source: dict):
        """Set attributes from dicts."""
        data = RepositoryData()
        for key in source:
            if key not in data.__dict__:
                continue
            if key == "pushed_at":
                if source[key] == "":
                    continue
                if "Z" in source[key]:
                    setattr(
                        data,
                        key,
                        datetime.strptime(source[key], "%Y-%m-%dT%H:%M:%SZ"),
                    )
                else:
                    setattr(
                        data,
                        key,
                        datetime.strptime(source[key], "%Y-%m-%dT%H:%M:%S"),
                    )
            elif key == "id":
                setattr(data, key, str(source[key]))
            elif key == "country":
                if isinstance(source[key], str):
                    setattr(data, key, [source[key]])
                else:
                    setattr(data, key, source[key])
            else:
                setattr(data, key, source[key])
        return data

    def update_data(self, data: dict):
        """Update data of the repository."""
        for key in data:
            if key not in self.__dict__:
                continue
            if key == "pushed_at":
                if data[key] == "":
                    continue
                if "Z" in data[key]:
                    setattr(
                        self,
                        key,
                        datetime.strptime(data[key], "%Y-%m-%dT%H:%M:%SZ"),
                    )
                else:
                    setattr(self, key, datetime.strptime(data[key], "%Y-%m-%dT%H:%M:%S"))
            elif key == "id":
                setattr(self, key, str(data[key]))
            elif key == "country":
                if isinstance(data[key], str):
                    setattr(self, key, [data[key]])
                else:
                    setattr(self, key, data[key])
            else:
                setattr(self, key, data[key])
