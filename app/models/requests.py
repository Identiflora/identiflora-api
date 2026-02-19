from pydantic import BaseModel, Field
from typing import Optional

class IncorrectIdentificationRequest(BaseModel):
    """
    Request body for reporting an incorrect identification.
    """

    identification_id: int = Field(..., gt=0, description="FK to identification_submission")
    correct_species_id: int = Field(..., gt=0, description="Species that should have been returned")
    incorrect_species_id: int = Field(..., gt=0, description="Species the model predicted")

class PlantSpeciesRequest(BaseModel):
    """
    Request body for reporting a new plant species.
    """

    common_name: Optional[str] = Field("NaN", min_length=1, description="common name of plant species")
    scientific_name: str = Field(..., min_length=1, description="scientific name of plant species")
    genus: Optional[str] = Field("NaN", min_length=1, description="genus of plant species")
    img_url: str = Field(..., min_length=1, description="url to image of plant species")

# class PlantSpeciesURLRequest(BaseModel):
#     """
#     Request body for requesting a plant img url.
#     """
#     scientific_name: str = Field(..., description="Scientific (Latin) name of the plant to query.")
#     host: str = Field(..., description="image server host")
#     port: int = Field(..., description="port to access image server")
#     img_path: str = Field(..., description="path to access images (eg. /plant-images)")

class UserRegistrationRequest(BaseModel):
    """
    Request body for reporting user registration. Ensures empty strings trigger invalid requests.
    """

    user_email: str = Field(..., min_length=1, description="Email from user input")
    username: str = Field(..., min_length=1, description="Username from user input")
    password_hash: str = Field(..., min_length=1, description="Password hash created by Flutter with user input")

class UserLoginRequest(BaseModel):
    """
    Request body for reporting user login. Ensures empty strings trigger invalid requests.
    """

    user_email: str = Field(..., min_length=1, description="Email from user input")
    password_hash: str = Field(..., min_length=1, description="Password hash created by Flutter with user input")
    has_otp: bool = Field(..., default=False, description="Is user trying to access account after creating OTP?")

class User(BaseModel):
    """
    Docstring for User
    """
    user_email: str = Field(..., min_length=1, description="Email from user input")
    username: str = Field(..., min_length=1, description="Username from user input")
    user_id: int = Field(..., gt=0, description="User id from database")
    password_hash: str = Field(..., min_length=1, description="Password hash created by Flutter with user input")

class UserPointAddRequest(BaseModel):
    """
    Request body for reporting user login. Ensures empty strings trigger invalid requests.
    """

    user_token: str = Field(..., min_length=1, description="Token from user's device")
    add_points: int = Field(..., gt=0, description="Points to add to user account")

class GoogleUserRegisterRequest(BaseModel):
    """
    Request body for user google login account creation. Ensures empty strings trigger invalid requests.
    """

    username: str = Field(..., min_length=1, description="Username from user input")

class UserPasswordResetRequest(BaseModel):
    """
    Request body for user password reset. Ensures empty strings trigger invalid requests.
    """

    user_email: str = Field(..., min_length=1, description="Email from user input")
    otp_length: int = Field(..., gt=5, description="Length of generated one time password")

class UserOTPVerifyRequest(BaseModel):
    """
    Request body for user password reset when user enters OTP. Ensures empty strings trigger invalid requests.
    """

    otp: str = Field(..., min_length=1, description="Password hash created by Flutter with user input")
    user_email: str = Field(..., min_length=1, description="Email from user input")