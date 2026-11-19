import sqlite3


def main():
    con = sqlite3.connect("github_google.db")
    cur = con.cursor()

    # 1. Total count
    cur.execute("SELECT COUNT(*) FROM repositories;")
    total = cur.fetchone()[0]
    print(f"総リポジトリ数: {total} 件\n")

    # 2. Top 10 most starred repositories
    print("=== スター数ランキング TOP 10 ===")
    print(f"{'順位':<4} | {'リポジトリ名':<35} | {'主要な言語':<18} | {'スター数':>8}")
    print("-" * 76)
    cur.execute(
        "SELECT name, language, stars FROM repositories ORDER BY stars DESC LIMIT 10;"
    )
    for rank, (name, language, stars) in enumerate(cur.fetchall(), start=1):
        print(f"{rank:<4} | {name:<35} | {language:<18} | {stars:>8}")

    # 3. Full SELECT * output (as explicitly required by the assignment)
    print("\n=== 全件データ (SELECT * FROM repositories) ===")
    print(f"{'ID':<5} | {'リポジトリ名':<35} | {'主要な言語':<18} | {'スター数':>8}")
    print("-" * 76)
    cur.execute("SELECT * FROM repositories;")
    for row in cur.fetchall():
        print(f"{row[0]:<5} | {row[1]:<35} | {row[2]:<18} | {row[3]:>8}")

    con.close()


if __name__ == "__main__":
    main()