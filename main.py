import tkinter as tk
from ui import ImageDeduplicatorUI
from calculation import HashCalculator, DuplicateAnalyzer

if __name__ == "__main__":
    root = tk.Tk()
    hash_calculator = HashCalculator()
    duplicate_analyzer = DuplicateAnalyzer()
    app = ImageDeduplicatorUI(root, hash_calculator, duplicate_analyzer)
    root.mainloop()