# -*- coding: utf-8 -*-
"""將監控狀態同步到 Cloud Firestore，並建立商品異動事件。"""

import os
import sys
from datetime import datetime, timezone

ORDER = 800

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from lib.catalog import RETIRED_SOURCE_IDS, collect_catalog  # noqa: E402

BATCH_SIZE = 400


def _commit_operations(database, operations):
    for offset in range(0, len(operations), BATCH_SIZE):
        batch = database.batch()
        for operation, reference, data in operations[offset : offset + BATCH_SIZE]:
            if operation == "set":
                batch.set(reference, data, merge=True)
            elif operation == "update":
                batch.update(reference, data)
            else:
                batch.delete(reference)
        batch.commit()


def _event_data(event_type, product, occurred_at, old_prices=None):
    return {
        "type": event_type,
        "productKey": product["id"],
        "productId": product["productId"],
        "productName": product["name"],
        "sourceId": product["sourceId"],
        "sourceLabel": product["sourceLabel"],
        "category": product["category"],
        "url": product["url"],
        "oldPrices": old_prices or [],
        "newPrices": product.get("prices", []),
        "occurredAt": occurred_at,
    }


def main():
    project_id = os.environ.get("FIREBASE_PROJECT_ID", "").strip()
    if not project_id:
        print("未設定 FIREBASE_PROJECT_ID，略過 Firestore 同步")
        return True

    try:
        import firebase_admin
        from firebase_admin import firestore
    except ImportError:
        print("ERROR: 已設定 Firebase，但尚未安裝 firebase-admin")
        return False

    try:
        firebase_admin.get_app()
    except ValueError:
        firebase_admin.initialize_app(options={"projectId": project_id})

    database = firestore.client()
    now = datetime.now(timezone.utc)
    products, sources = collect_catalog(REPO_ROOT)
    current = {product["id"]: product for product in products}
    source_ids = {source["id"] for source in sources}

    existing = {
        snapshot.id: snapshot.to_dict()
        for snapshot in database.collection("products").stream()
    }
    known_sources = {
        snapshot.id for snapshot in database.collection("sources").stream()
    }
    sync_reference = database.collection("meta").document("sync")
    first_sync = not sync_reference.get().exists

    operations = []
    event_counts = {"new": 0, "price_changed": 0, "removed": 0, "restocked": 0}

    for product_key, product in current.items():
        previous = existing.get(product_key)
        reference = database.collection("products").document(product_key)
        if previous is None:
            document = {**product, "firstSeenAt": now, "updatedAt": now}
            operations.append(("set", reference, document))
            if not first_sync and product["sourceId"] in known_sources:
                event_reference = database.collection("events").document()
                operations.append(("set", event_reference, _event_data("new", product, now)))
                event_counts["new"] += 1
            continue

        changes = {}
        event_type = None
        old_prices = previous.get("prices", [])
        if not previous.get("active", True):
            event_type = "restocked"
            changes["active"] = True
        elif old_prices and old_prices != product["prices"]:
            event_type = "price_changed"

        for field in ("name", "url", "prices", "sourceLabel", "category"):
            if previous.get(field) != product[field]:
                changes[field] = product[field]

        if changes:
            changes["updatedAt"] = now
            operations.append(("update", reference, changes))
        if event_type:
            event_reference = database.collection("events").document()
            operations.append(
                ("set", event_reference, _event_data(event_type, product, now, old_prices))
            )
            event_counts[event_type] += 1

    for product_key, previous in existing.items():
        if previous.get("sourceId") in RETIRED_SOURCE_IDS:
            reference = database.collection("products").document(product_key)
            operations.append(("delete", reference, None))
            continue
        if product_key in current or previous.get("sourceId") not in source_ids:
            continue
        if not previous.get("active", True):
            continue
        reference = database.collection("products").document(product_key)
        operations.append(("update", reference, {"active": False, "updatedAt": now}))
        removed_product = {
            "id": product_key,
            "productId": previous.get("productId", ""),
            "name": previous.get("name", ""),
            "sourceId": previous.get("sourceId", ""),
            "sourceLabel": previous.get("sourceLabel", ""),
            "category": previous.get(
                "category",
                "deck" if previous.get("sourceId", "").endswith("_deck") else "product",
            ),
            "url": previous.get("url", ""),
            "prices": [],
        }
        event_reference = database.collection("events").document()
        operations.append(
            (
                "set",
                event_reference,
                _event_data("removed", removed_product, now, previous.get("prices", [])),
            )
        )
        event_counts["removed"] += 1

    for source in sources:
        source_reference = database.collection("sources").document(source["id"])
        operations.append(("set", source_reference, {**source, "lastSyncAt": now}))
    for source_id in RETIRED_SOURCE_IDS:
        source_reference = database.collection("sources").document(source_id)
        operations.append(("delete", source_reference, None))

    run_reference = database.collection("runs").document()
    operations.append(
        (
            "set",
            run_reference,
            {
                "completedAt": now,
                "productCount": len(products),
                "sourceCount": len(sources),
                "changes": event_counts,
                "status": "ok",
            },
        )
    )
    operations.append(
        (
            "set",
            sync_reference,
            {
                "initialized": True,
                "lastSyncAt": now,
                "productCount": len(products),
                "sourceCount": len(sources),
            },
        )
    )

    _commit_operations(database, operations)
    print(
        "Firestore 同步完成："
        f"{len(products)} 件商品、{len(sources)} 個來源、"
        f"{sum(event_counts.values())} 筆異動"
    )
    return True


if __name__ == "__main__":
    main()
