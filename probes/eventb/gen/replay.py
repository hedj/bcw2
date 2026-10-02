import csv, sys
rows = list(csv.reader(open(sys.argv[1])))
order = [f"{s}/{m}" for m in ("selected", "all") for s in ("Z3", "CVC3", "CVC4", "veriT")]
for limit in (10000, 5000, 3000, 2000):
    total, worst, lost = 0, (0, ""), []
    for i in range(0, len(rows), 8):
        block = {r[1]: (r[2] == "proved", int(r[3])) for r in rows[i:i + 8]}
        goal, t = rows[i][0], 0
        for cfg in order:
            ok, ms = block[cfg]
            if ok and ms <= limit:
                t += ms
                break
            t += min(ms, limit)
        else:
            lost.append(goal)
        total += t
        worst = max(worst, (t, goal))
    print(f"{limit:>6} ms: goals {len(rows)//8}, unproved {len(lost)}, total {total/1000:.1f} s, worst {worst[0]/1000:.1f} s {worst[1]}")
    for g in lost: print("   lost", g)
