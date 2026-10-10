import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from wealthos import db as dbm  # noqa: E402


@pytest.fixture()
def db(tmp_path):
    """每个测试一个全新库（含种子）。"""
    dbm.init_db(tmp_path / "t.db")
    conn = dbm.connect(tmp_path / "t.db")
    yield conn
    conn.close()


@pytest.fixture()
def seeded_holdings(db):
    """导入样例数据并灌入固定汇率（离线确定性）。"""
    from wealthos.importers.csv_import import import_csv

    import_csv(REPO / "samples" / "accounts.csv", db)
    import_csv(REPO / "samples" / "activities.csv", db)
    import_csv(REPO / "samples" / "holdings_2026-09-30.csv", db)
    import_csv(REPO / "samples" / "holdings_2026-10-02.csv", db)
    for d in ("2026-09-30", "2026-10-02"):
        for base, quote, rate in [("USD", "HKD", 7.80), ("USD", "JPY", 150.0),
                                  ("USD", "CNY", 7.10)]:
            db.execute("INSERT OR REPLACE INTO fx_rates VALUES(?,?,?,?,?)",
                       (d, base, quote, rate, "fixture"))
    # 模拟真实流程：汇率齐了之后重算估值（币种感知）
    from wealthos.engine.networth import recompute_valuations

    recompute_valuations(db)
    return db
