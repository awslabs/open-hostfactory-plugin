from typing import Dict, Any
from datetime import datetime
import json
import os
from src.infrastructure.persistence.repository_factory import RepositoryFactory
from src.infrastructure.persistence.exceptions import StorageError

class RepositoryMigrator:
    """Handles migration between different repository types."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.collections = ['templates', 'requests', 'machines']

    def migrate(self, 
                source_type: str, 
                target_type: str, 
                create_backup: bool = True) -> Dict[str, Any]:
        """
        Migrate data between repository types.
        Returns migration statistics.
        """
        if source_type == target_type:
            return {"status": "skipped", "reason": "Source and target types are the same"}

        stats = {
            "started_at": datetime.utcnow().isoformat(),
            "source_type": source_type,
            "target_type": target_type,
            "collections": {},
            "backup_created": None
        }

        try:
            # Create configurations
            source_config = {**self.config, "REPOSITORY_TYPE": source_type}
            target_config = {**self.config, "REPOSITORY_TYPE": target_type}
            
            # Create repositories
            source_repos = RepositoryFactory.create_all_repositories(source_config)
            target_repos = RepositoryFactory.create_all_repositories(target_config)

            # Create backup if requested
            if create_backup:
                backup_path = self._create_backup(target_repos)
                stats["backup_created"] = backup_path

            # Perform migration
            for collection in self.collections:
                collection_stats = self._migrate_collection(
                    collection,
                    source_repos[collection],
                    target_repos[collection]
                )
                stats["collections"][collection] = collection_stats

            stats["status"] = "success"
            stats["completed_at"] = datetime.utcnow().isoformat()

        except Exception as e:
            stats["status"] = "error"
            stats["error"] = str(e)
            stats["completed_at"] = datetime.utcnow().isoformat()

        return stats

    def _create_backup(self, repos: Dict[str, Any]) -> str:
        """Create backup of current data."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_dir = os.path.join(
            os.environ.get('HF_PROVIDER_WORKDIR', ''),
            'backups',
            f'repository_backup_{timestamp}'
        )
        os.makedirs(backup_dir, exist_ok=True)

        for collection in self.collections:
            items = repos[collection].find_all()
            if items:
                backup_file = os.path.join(backup_dir, f"{collection}.json")
                with open(backup_file, 'w') as f:
                    json.dump(items, f, indent=2)

        return backup_dir

    def _migrate_collection(self, 
                          collection_name: str, 
                          source_repo: Any, 
                          target_repo: Any) -> Dict[str, Any]:
        """Migrate a single collection."""
        stats = {
            "total_items": 0,
            "migrated": 0,
            "failed": 0,
            "errors": []
        }

        try:
            items = source_repo.find_all()
            stats["total_items"] = len(items)

            for item in items:
                try:
                    item_id = (
                        item.get('id') or 
                        item.get('templateId') or 
                        item.get('requestId') or 
                        item.get('machineId')
                    )
                    if not item_id:
                        raise ValueError(f"Item without ID found in {collection_name}")

                    target_repo.save(item_id, item)
                    stats["migrated"] += 1

                except Exception as e:
                    stats["failed"] += 1
                    stats["errors"].append({
                        "item_id": item_id if 'item_id' in locals() else "unknown",
                        "error": str(e)
                    })

        except Exception as e:
            stats["failed"] = stats["total_items"]
            stats["errors"].append({
                "collection": collection_name,
                "error": str(e)
            })

        return stats
