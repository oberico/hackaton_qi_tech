def is_valid_cpf(cpf: str) -> bool:
    digits = [int(char) for char in cpf if char.isdigit()]
    if len(digits) != 11 or len(set(digits)) == 1:
        return False

    for position in (9, 10):
        total = sum(digit * weight for digit, weight in zip(digits, range(position + 1, 1, -1)))
        if total * 10 % 11 % 10 != digits[position]:
            return False
    return True
