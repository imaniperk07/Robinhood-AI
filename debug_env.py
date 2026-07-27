import os
from dotenv import load_dotenv

load_dotenv()

client_id = os.environ.get("SNAPTRADE_CLIENT_ID")
consumer_key = os.environ.get("SNAPTRADE_CONSUMER_KEY")

def describe(name: str, value: str | None) -> None:
    if value is None:
        print(f"{name}: NOT FOUND (this is the problem)")
    else:
        print(f"{name}: found, length={len(value)}, starts with '{value[:4]}', ends with '{value[-4:]}'")

describe("SNAPTRADE_CLIENT_ID", client_id)
describe("SNAPTRADE_CONSUMER_KEY", consumer_key)