import json
import os
import requests

API_URL = "https://api.opendota.com/api/heroes"
CDN_BASE_URL = (
    "https://cdn.cloudflare.steamstatic.com/apps/dota2/images/dota_react/heroes/"
)

IMAGE_DIR = "images"
JSON_FILE = "heroes_data.json"

os.makedirs(IMAGE_DIR, exist_ok=True)

print("Fetching hero data from OpenDota API...")
response = requests.get(API_URL)
response.raise_for_status()
heroes = response.json()

# Sort the heroes list alphabetically (A to Z) by localized_name
heroes = sorted(heroes, key=lambda h: h["localized_name"])

heroes_dict = {}

print(f"Found {len(heroes)} heroes. Processing in A-Z order...")

for hero in heroes:
  hero_id = hero["id"]
  localized_name = hero["localized_name"]
  name_key = hero["name"].replace("npc_dota_hero_", "")

  # Define file paths
  image_filename = f"{name_key}.png"
  image_path = os.path.join(IMAGE_DIR, image_filename)

  # Download image
  image_url = f"{CDN_BASE_URL}{image_filename}"
  try:
    img_response = requests.get(image_url, timeout=10)
    if img_response.status_code == 200:
      with open(image_path, "wb") as img_file:
        img_file.write(img_response.content)
  except Exception as e:
    print(f"Error downloading {localized_name}: {e}")

  # Store structured data
  heroes_dict[name_key] = {
      "id": hero_id,
      "localized_name": localized_name,
      "image_path": f"{IMAGE_DIR}/{image_filename}",
  }

# Save sorted dictionary to JSON file (sort_keys=False preserves our A-Z order)
with open(JSON_FILE, "w", encoding="utf-8") as f:
  json.dump(heroes_dict, f, indent=4, ensure_ascii=False)

print(f"\nSuccess!")
print(f"- Sorted hero data saved to: {JSON_FILE}")
print(f"- Hero images saved to: ./{IMAGE_DIR}/")
