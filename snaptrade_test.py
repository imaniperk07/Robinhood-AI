import os
from dotenv import load_dotenv
from snaptrade_client import SnapTrade

load_dotenv()

client = SnapTrade(
    client_id=os.environ.get("SNAPTRADE_CLIENT_ID"),
    consumer_key=os.environ.get("SNAPTRADE_CONSUMER_KEY"),
)


def test_connection() -> None:
    response = client.api_status.check()
    print("SnapTrade API Status:")
    print(response.body)


if __name__ == "__main__":
    test_connection()