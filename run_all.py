#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""排程入口：自動探索並執行 tasks/ 內所有任務。

每個任務 = tasks/ 下一支模組，需提供 main()。
任務可選擇性宣告 ORDER（整數，預設 100）以控制執行先後——
數字小的先跑；像報告產生這類需在最後執行的任務設較大值。
單一任務失敗不影響其他任務（各自隔離例外）。
GitHub Actions 每小時呼叫一次本檔。
"""

import importlib
import os
import pkgutil
import traceback

import tasks


def discover_tasks():
    names = []
    for mod in pkgutil.iter_modules(tasks.__path__):
        if not mod.name.startswith("_"):
            names.append(mod.name)
    return sorted(names)


def main():
    task_names = discover_tasks()
    print(f"探索到 {len(task_names)} 個任務：{', '.join(task_names) or '(無)'}")

    # 先載入模組，再依 ORDER（預設 100）+ 名稱排序決定執行順序。
    loaded = []
    for name in task_names:
        try:
            loaded.append((name, importlib.import_module(f"tasks.{name}")))
        except Exception:  # noqa: BLE001
            print(f"ERROR: 載入任務 {name} 失敗：")
            traceback.print_exc()
    loaded.sort(key=lambda it: (getattr(it[1], "ORDER", 100), it[0]))

    failures = 0
    for name, module in loaded:
        print(f"\n=== 執行任務：{name} ===")
        try:
            if hasattr(module, "main"):
                module.main()
            else:
                print(f"WARN: tasks.{name} 沒有 main()，略過")
        except Exception:  # noqa: BLE001
            failures += 1
            print(f"ERROR: 任務 {name} 例外：")
            traceback.print_exc()
    print(f"\n完成。失敗 {failures}/{len(loaded)}。")


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    main()
