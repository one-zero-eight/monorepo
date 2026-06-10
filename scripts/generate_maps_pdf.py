import sys
from pathlib import Path

# add parent dir to sys.path
sys.path.append(str(Path(__file__).parents[1]))

from src.maps.pdf_generator import generate_all_maps_pdf


def main():
    print("Generating PDF from SVG files...")
    output_path = generate_all_maps_pdf()
    print(f"Successfully generated {output_path}")


if __name__ == "__main__":
    main()
