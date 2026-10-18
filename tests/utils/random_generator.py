import random
from uuid import uuid4

CNPJ_WEIGHTS = ([5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2], [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])


class RandomGenerator:
    @staticmethod
    def uuid() -> str:
        return str(uuid4())

    @staticmethod
    def transaction_id() -> str:
        return f"pix-{uuid4().hex}"

    @staticmethod
    def device_id() -> str:
        return f"dvc-{uuid4().hex[:16]}"

    @staticmethod
    def account_number() -> str:
        return str(uuid4().int)[:15]

    @staticmethod
    def cpf() -> str:
        digits = [random.randint(0, 9) for _ in range(9)]
        for weight_start in (10, 11):
            total = sum(digit * weight for digit, weight in zip(digits, range(weight_start, 1, -1)))
            digits.append(total * 10 % 11 % 10)
        number = "".join(map(str, digits))
        return f"{number[:3]}.{number[3:6]}.{number[6:9]}-{number[9:]}"

    @staticmethod
    def cnpj() -> str:
        digits = [random.randint(0, 9) for _ in range(12)]
        for weights in CNPJ_WEIGHTS:
            remainder = sum(digit * weight for digit, weight in zip(digits, weights)) % 11
            digits.append(0 if remainder < 2 else 11 - remainder)
        number = "".join(map(str, digits))
        return f"{number[:2]}.{number[2:5]}.{number[5:8]}/{number[8:12]}-{number[12:]}"
