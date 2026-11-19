import csv

total = 0
count = 0
with open("sales.csv", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        try:
            total += float(row["amount"])
        except ValueError:
            pass
        count += 1

print("average:", round(total / count, 2))
