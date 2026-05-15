from openpyxl.formula import Tokenizer
tok = Tokenizer('=SUM(A1:A10)')
for i in tok.items:
    print(f"Type: {i.type}, Value: {i.value}")
