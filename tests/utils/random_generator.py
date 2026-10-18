import random
from uuid import uuid4

BUREAU_REJECTED_SUFFIX = "-00"


class RandomGenerator:
    @staticmethod
    def uuid() -> str:
        return str(uuid4())

    @staticmethod
    def amount_minor(minimum: int = 100, maximum: int = 1_000_000) -> int:
        return random.randint(minimum, maximum)

    @staticmethod
    def cpf() -> str:
        digits = [random.randint(0, 9) for _ in range(9)]
        for weight_start in (10, 11):
            total = sum(d * w for d, w in zip(digits, range(weight_start, 1, -1)))
            digits.append(total * 10 % 11 % 10)
        d = "".join(map(str, digits))
        return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"

    @staticmethod
    def email() -> str:
        return f"{uuid4().hex}@teste.com"

    @staticmethod
    def cnpj() -> str:
        while True:
            cnpj = RandomGenerator._any_cnpj()
            if not cnpj.endswith(BUREAU_REJECTED_SUFFIX):
                return cnpj

    @staticmethod
    def cnpj_rejected_by_bureau() -> str:
        while True:
            cnpj = RandomGenerator._any_cnpj()
            if cnpj.endswith(BUREAU_REJECTED_SUFFIX):
                return cnpj

    @staticmethod
    def _any_cnpj() -> str:
        digits = [random.randint(0, 9) for _ in range(12)]
        for weights in ([5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2], [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]):
            remainder = sum(d * w for d, w in zip(digits, weights)) % 11
            digits.append(0 if remainder < 2 else 11 - remainder)
        d = "".join(map(str, digits))
        return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"
