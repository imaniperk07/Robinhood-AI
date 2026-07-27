import os
import json
import uuid
import webbrowser
from dotenv import load_dotenv
from snaptrade_client import SnapTrade, SnapTradeAuth

load_dotenv()

# Personal SnapTrade keys (as opposed to commercial/partner keys) come with exactly
# one pre-provisioned user baked into the key itself — no separate userId/userSecret
# needed for account/position calls. Must construct via `auth=`, not raw
# client_id=/consumer_key= kwargs, or the SDK silently skips request signing and
# every authenticated call 403s.
client = SnapTrade(
    auth=SnapTradeAuth.personal_api_key(
        client_id=os.environ.get("SNAPTRADE_CLIENT_ID"),
        consumer_key=os.environ.get("SNAPTRADE_CONSUMER_KEY"),
    )
)

SNAPTRADE_USER_FILE = "snaptrade_user.json"


def register_user() -> dict:
    """Register yourself once as a SnapTrade user. This only needs to happen one time, ever."""
    user_id = str(uuid.uuid4())
    response = client.authentication.register_snap_trade_user(body={"userId": user_id})

    user_data = {
        "userId": response.body["userId"],
        "userSecret": response.body["userSecret"],
    }
    with open(SNAPTRADE_USER_FILE, "w") as f:
        json.dump(user_data, f, indent=2)

    print(f"Registered new SnapTrade user: {user_data['userId']}")
    print("Saved to snaptrade_user.json — keep this file private, never share or upload it.")
    return user_data


def load_or_register_user() -> dict:
    env_user_id = os.environ.get("SNAPTRADE_USER_ID")
    env_user_secret = os.environ.get("SNAPTRADE_USER_SECRET")
    if env_user_id and env_user_secret:
        return {"userId": env_user_id, "userSecret": env_user_secret}

    if os.path.exists(SNAPTRADE_USER_FILE):
        with open(SNAPTRADE_USER_FILE, "r") as f:
            return json.load(f)
    return register_user()


def get_connection_link() -> None:
    user = load_or_register_user()

    response = client.authentication.login_snap_trade_user(
        query_params={"userId": user["userId"], "userSecret": user["userSecret"]}
    )

    print("Raw response from SnapTrade:")
    print(response.body)
    print()

    redirect_uri = None
    if isinstance(response.body, dict):
        redirect_uri = response.body.get("redirectURI")

    if redirect_uri:
        print("Opening the SnapTrade connection portal in your browser...")
        print(redirect_uri)
        webbrowser.open(redirect_uri)
    else:
        print("Couldn't find a redirect link in the response above — paste this output back to me.")


if __name__ == "__main__":
    get_connection_link()