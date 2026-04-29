import pathlib
from autoq_data.pipeline import prepare_enriched_datasets

data_dir = pathlib.Path("user_data/data")
exchange = "binance"
pairs = ["BTC/USDT", "ETH/USDT"]

print("Starting enrichment for all data in user_data/data...")
manifest = prepare_enriched_datasets(
    data_dir=data_dir,
    exchange=exchange,
    pairs=pairs
)
print("Done!")
print(f"Manifest: {manifest['start']} to {manifest['end']}")
