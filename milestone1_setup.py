import database
from config import WATCHLIST, API, RISK


def _banner(t): print("\n" + "═"*58 + f"\n  {t}\n" + "═"*58)


def task_init_database():
    _banner("Task 1 — Initialise Database")
    database.init_db()
    print(f"  Config used  →  DATABASE file = '{database.DB_FILE.split('/')[-1]}'")


def task_show_watchlist():
    _banner("Task 2 — Watchlist  (config.WATCHLIST)")
    for i, cid in enumerate(WATCHLIST, 1):
        print(f"  {i}. {cid}")
    print(f"\n  API  →  {API['base_url']}")
    print(f"  Currency  →  {API['vs_currency'].upper()}")
    print(f"  Rate-limit gap  →  {API['min_gap_sec']}s")


def task_parallel_fetch():
    _banner("Task 3 — Bulk Fetch  (single API call, no rate-limit risk)")
    print(f"  Fetching {len(WATCHLIST)} coins …\n")

    results  = database.get_prices(WATCHLIST)
    ok, fail = [], []

    fetched_ids = {r["id"] for r in (results or [])}
    for cid in WATCHLIST:
        if cid not in fetched_ids:
            fail.append(cid)

    for result in (results or []):
        database.save_price(result)
        ok.append(result)
        print(f"  ✓  {result['symbol']:<8} ${result['current_price']:>14,.4f}  "
              f"24h: {result['price_change_percentage_24h']:+.2f}%")

    for cid in fail:
        print(f"  ✗  {cid}  (not returned by API)")

    print(f"\n  Stored {len(ok)} snapshots  |  {len(fail)} failed")


def task_trending():
    _banner("Task 4 — Trending Coins on CoinGecko")
    coins = database.get_trending()
    if not coins:
        print("  (Could not fetch — check internet)")
        return
    for i, c in enumerate(coins, 1):
        print(f"  {i}. {c['symbol']:<10}  {c['name']:<25}  id={c['id']}")

def run():

    task_init_database()
    input("\n  Press Enter …")
    task_show_watchlist()
    input("\n  Press Enter …")
    task_parallel_fetch()
    input("\n  Press Enter …")
    task_trending()


if __name__ == "__main__":
    run()