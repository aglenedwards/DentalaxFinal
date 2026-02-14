import csv
import time
from utils.geocode import get_coordinates_from_address

input_file = "neue_zahnaerzte.csv"
output_file = "neue_zahnaerzte_mit_koordinaten.csv"

updated_rows = []
count_updated = 0

with open(input_file, newline='', encoding="utf-8") as infile:
    reader = csv.DictReader(infile)
    fieldnames = reader.fieldnames

    for row in reader:
        lat = row.get("lat", "").strip()
        lng = row.get("lng", "").strip()

        # Prüfe, ob Koordinaten bereits vorhanden und gültig sind
        try:
            if 45 <= float(lat) <= 55 and 5 <= float(lng) <= 15:
                updated_rows.append(row)
                continue
        except:
            pass

        # Wenn leer oder ungültig → Geocoding durchführen
        address = f'{row["straße"]}, {row["plz"]} {row["stadt"]}'
        print(f"🌍 Geokodiere: {address}")
        new_lat, new_lng = get_coordinates_from_address(address)

        if new_lat and new_lng:
            row["lat"] = str(new_lat)
            row["lng"] = str(new_lng)
            count_updated += 1
        else:
            row["lat"] = ""
            row["lng"] = ""

        updated_rows.append(row)
        time.sleep(0.2)  # Verzögerung zur Einhaltung der Google API Rate Limits

# Schreibe aktualisierte Datei
with open(output_file, "w", newline='', encoding="utf-8") as outfile:
    writer = csv.DictWriter(outfile, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(updated_rows)

print(f"✅ {count_updated} Koordinaten ergänzt.")
print(f"📄 Datei gespeichert als: {output_file}")
