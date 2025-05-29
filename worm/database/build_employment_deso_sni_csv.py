import pandas as pd

# Läs filen
df_sni = pd.read_csv("data/Sysselsatta 15-74 år region, näringsgren SNI 2007 och år.csv", sep=";", skiprows=1, encoding="cp1252")
# Byt namn på kolumner (justera om din fil skiljer sig!)
df_sni = df_sni.rename(columns={
    "region": "deso_code",
    "år": "year",
    "näringsgren SNI 2007": "sni_code",
    "ålder": "age_group",
    "sysselsatta": "employed",
    "arbetsställen": "workplaces"
})
# Rensa/konvertera
for col in ["employed", "workplaces"]:
    if col in df_sni.columns:
        df_sni[col] = pd.to_numeric(df_sni[col], errors="coerce")

df_sni = df_sni[["deso_code", "year", "sni_code", "age_group", "employed", "workplaces"]]
df_sni.to_csv("data/employment_deso_sni.csv", index=False, encoding="utf-8")
