from jose import jwt
from datetime import datetime, timedelta, timezone

token_input = {
                "sub": "test_user_id",
                "exp": datetime.now(tz=timezone.utc) + timedelta(minutes=15),
                "iat": datetime.now(tz=timezone.utc),
            }

test_token = jwt.encode(token_input, "supersecretkey", algorithm="HS256")
print(test_token)

decoded_output = jwt.decode("yoooo", "supersecretkey", algorithms=["HS256"])
print(decoded_output)