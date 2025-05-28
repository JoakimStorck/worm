from worm.database import schema, loader

schema.create_schema()
loader.load_municipalities("data/scb_municipalities.csv")
loader.load_deso("data/scb_deso.csv")
loader.load_employment("data/scb_employment.csv")
