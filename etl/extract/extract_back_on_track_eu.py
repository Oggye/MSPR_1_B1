# =========================================================
# etl/extract/extract_back_on_track_eu.py
# =========================================================

import requests
import pandas as pd
from pathlib import Path

RAW_DIR = Path("data/raw/back_on_track")
RAW_DIR.mkdir(parents=True, exist_ok=True)

# URLs redirigées directement vers le JSON final
BACK_ON_TRACK_URLS = {
    "view_ontd_list": "https://script.googleusercontent.com/macros/echo?user_content_key=AehSKLhGoaDOe-baTlQ1N3ADnqatpJDZKNuVRqrBFjCGf2rKxC0IYxysizUMXd85pkHHeq0ygsT1FniDv2KZyiagKwMd9EA_OavD_xILtDsRMYl87W8ii0NZ3pCU6pwlPZ9RRb-kDMF5imu-abvhsMzSveSZJPRoL3vH1TYWUF2c8eCa6WkWOI8r1Cqe6QYZz_cKglKc_V4UiBXLayz6siK-1w27FBkziSEfluHGQe2ZgHNdfO2kfxzyu-5wnKurlI2q66-VLtUVDTJodRQM4ATP-v5vB4XgZp5ykcSDIGfze7CwYp3__yE16vJbEDR2Ow&lib=MCICvOpqIJICUYFjSVlDgThOYJJtpaZp0",
    "view_ontd_cities": "https://script.googleusercontent.com/macros/echo?user_content_key=AehSKLhetSIXcc2yAo4AR2v34yxvtwWMiDu_HLpnG9TsT77mEckhxKLiVH8OjxrT_aSFP5aGxwtyDY91gD52O7rW6VmRLIVZSkBXFTnzZsnFbvhzJp_DZ3BuoyuE8ZYUuZV7Gy5G65653jLhKJgev-odUjg9gDY3G3jK4braML5sS4Fi6wevYkWglL-X8gFXmGCY54X33qoBWAQ2SvkhubaI0zvJIljRaTRYFCXi80BWRmOI5Pi3egyo-DJ29SVdYpvAI8mTzWZIaamowN1h_jTBSt-EcLgeQ2q7TzTFZ4IZQl2Y-INjT2hTT1rfykXNtA&lib=MCICvOpqIJICUYFjSVlDgThOYJJtpaZp0"
}

def extract_back_on_track():
    for table_name, url in BACK_ON_TRACK_URLS.items():
        print(f"Téléchargement {table_name}…")
        response = requests.get(url)
        response.raise_for_status()
        # On récupère le JSON final
        data = response.json()
        # Conversion en DataFrame
        df = pd.DataFrame.from_dict(data, orient='index')
        # Nettoyage éventuel des valeurs inutiles (#REF!)
        df = df[df.index != "#REF!"]
        # Sauvegarde
        out_file = RAW_DIR / f"{table_name}.csv"
        df.to_csv(out_file, index=False)
        print(f"{table_name} extrait et sauvegardé → {out_file}")
