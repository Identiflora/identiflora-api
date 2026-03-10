from passlib.hash import bcrypt, argon2

password = "jackson"
correct_check = "jackson"
incorrect_check = "jackson1"

hashed_password = argon2.hash(password)
print(hashed_password)

correct = argon2.verify(correct_check, hashed_password)
print(correct)

incorrect = argon2.verify(incorrect_check, hashed_password)
print(incorrect)