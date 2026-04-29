import json

with open("config.json", "r") as f:
    cfg = json.load(f)

cfg"exchange""pair_whitelist" = "BTC/USDT"

with open("config.json", "w") as f:
    json.dump(cfg, f, indent=2)

print("Done:", cfg"exchange""pair_whitelist")
