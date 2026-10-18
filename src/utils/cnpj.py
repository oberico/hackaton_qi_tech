FIRST_DIGIT_WEIGHTS = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
SECOND_DIGIT_WEIGHTS = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]


def is_valid_cnpj(cnpj: str) -> bool:
    digits = [int(char) for char in cnpj if char.isdigit()]
    if len(digits) != 14 or len(set(digits)) == 1:
        return False

    for position, weights in ((12, FIRST_DIGIT_WEIGHTS), (13, SECOND_DIGIT_WEIGHTS)):
        remainder = sum(digit * weight for digit, weight in zip(digits, weights)) % 11
        if (0 if remainder < 2 else 11 - remainder) != digits[position]:
            return False
    return True
