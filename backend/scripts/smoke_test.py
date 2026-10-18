"""API smoke test against a running EvidenceRadar server (used in dev, not CI)."""
import httpx

c = httpx.Client(base_url="http://127.0.0.1:8000", timeout=30)

print("health   :", c.get("/api/health").json())
ov = c.get("/api/overview").json()
print("overview :", {k: ov[k] for k in (
    "cases", "unique_drugs", "unique_reactions", "trials", "reviews",
    "signals", "strong_signals", "date_range", "source")})

s = c.get("/api/signals", params={"limit": 3}).json()
print("signals total:", s["total"])
for sig in s["signals"][:3]:
    print(f"  {sig['drug']} -> {sig['reaction']}: n={sig['cases']} "
          f"ROR={sig['ror']} EB05={sig['eb05']} score={sig['evidence_score']} "
          f"labelled={sig['in_label']}")

top = s["signals"][0]["drug"]
d = c.get(f"/api/drugs/{top}").json()
print("drug     :", top, "| reactions:", len(d["reactions"]),
      "| trend pts:", len(d["trend"]), "| pairs:", len(d["pairs"]),
      "| trials:", len(d["trials"]), "| reviews:", d["reviews"]["reviews"],
      "| label:", d["label"]["has_label"])

rx = d["reactions"][0]["reaction"]
r = c.get(f"/api/reactions/{rx}").json()
print("reaction :", rx, "| drugs:", len(r["drugs"]), "| monthly:", len(r["monthly"]))

tr = c.get("/api/trials", params={"limit": 2}).json()
print("trials   :", tr["total"], "total |", tr["trials"][0]["nct_id"],
      "| countries:", tr["trials"][0]["countries"][:3])
g = c.get("/api/trials/geo").json()
print("geo pts  :", len(g["points"]), "| top:", g["points"][0]["count"],
      g["points"][0]["countries"][:2])
f = c.get("/api/trials/facets").json()
print("facets   :", len(f["statuses"]), "statuses,", len(f["phases"]), "phases,",
      len(f["conditions"]), "conditions")
rs = c.get("/api/reviews/stats", params={"limit": 2}).json()
print("reviews  :", rs["drugs"][0]["drug"], "mean rating", rs["drugs"][0]["mean_rating"])
m = c.get("/api/methodology").json()
print("method   :", len(m["disproportionality"]), "measures,",
      len(m["sources"]), "sources,", len(m["limitations"]), "limitations")
print("search   :", c.get("/api/signals", params={"q": "metformin", "limit": 5}).json()["total"], "signals for 'metformin'")
print("404 check:", c.get("/api/drugs/NOTAREALDRUG").status_code)
print("SMOKE OK")
