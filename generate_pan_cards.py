import sqlite3
import os
from PIL import Image, ImageDraw, ImageFont
import random
import string

# Database and Output Folder
DB_NAME = "bank_system_v3.db"
OUTPUT_FOLDER = "Demo_kyc_docs"

# Ensure output folder exists
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

def generate_random_pan():
    """Generates a random PAN number in the format ABCDE1234F."""
    alpha = "".join(random.choices(string.ascii_uppercase, k=5))
    numeric = "".join(random.choices(string.digits, k=4))
    check = random.choice(string.ascii_uppercase)
    return f"{alpha}{numeric}{check}"

def create_pan_card(customer_name, pan_number, account_number):
    """Creates a PAN card image mimicking the sample provided."""
    # Image size: 500x300 (standard proportions)
    width, height = 500, 300
    # Background color (subtle cyan/green gradient mockup)
    img = Image.new('RGB', (width, height), color=(220, 245, 230))
    draw = ImageDraw.Draw(img)

    # Drawing a header
    draw.rectangle([0, 0, width, 50], fill=(0, 100, 80))
    
    # Try to load a font, fallback to default
    try:
        # Standard Windows fonts
        font_header = ImageFont.truetype("arial.ttf", 20)
        font_label = ImageFont.truetype("arial.ttf", 10)
        font_data = ImageFont.truetype("arial.ttf", 14)
        font_pan = ImageFont.truetype("arial.ttf", 18)
    except:
        font_header = ImageFont.load_default()
        font_label = ImageFont.load_default()
        font_data = ImageFont.load_default()
        font_pan = ImageFont.load_default()

    # Header Text
    draw.text((width//2 - 100, 15), "INCOME TAX DEPARTMENT", fill="white", font=font_header)
    draw.text((width - 80, 5), "GOVT. OF INDIA", fill="white", font=font_label)

    # User Section
    # Mock Photo
    draw.rectangle([20, 70, 120, 190], outline="black", fill=(200, 200, 200))
    draw.text((45, 120), "PHOTO", fill="black", font=font_label)

    # User Details
    draw.text((150, 70), "Name", fill=(0, 50, 50), font=font_label)
    draw.text((150, 85), customer_name.upper(), fill="black", font=font_data)

    draw.text((150, 115), "Father's Name", fill=(0, 50, 50), font=font_label)
    # Generate a dummy father's name based on user name
    fathers_name = customer_name.split()[0] + " Sr."
    draw.text((150, 130), fathers_name.upper(), fill="black", font=font_data)

    draw.text((150, 160), "Date of Birth", fill=(0, 50, 50), font=font_label)
    dob = f"{random.randint(1,28):02d}/{random.randint(1,12):02d}/{random.randint(1970,2000)}"
    draw.text((150, 175), dob, fill="black", font=font_data)

    # PAN Number Section
    draw.text((150, 210), "Permanent Account Number", fill=(0, 50, 50), font=font_label)
    draw.text((150, 230), pan_number, fill="black", font=font_pan)

    # Mock Signature
    draw.line([300, 270, 480, 270], fill="black", width=2)
    draw.text((350, 275), "SIGNATURE", fill="black", font=font_label)

    # Logo/Seal Mockup
    draw.ellipse([420, 60, 480, 120], outline=(0, 100, 80), width=3)
    draw.text((435, 80), "SEAL", fill=(0, 100, 80), font=font_label)

    # Save the card
    file_path = os.path.join(OUTPUT_FOLDER, f"PAN_{account_number}.png")
    img.save(file_path)
    return file_path

def main():
    if not os.path.exists(DB_NAME):
        print(f"Error: Database {DB_NAME} not found. Run db_gen.py first.")
        return

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("SELECT name, account_number FROM customers")
    customers = cursor.fetchall()
    
    print(f"[*] Generating PAN cards for {len(customers)} customers...")
    
    for name, acc in customers:
        pan = generate_random_pan()
        path = create_pan_card(name, pan, acc)
        # We could also store the PAN back in the DB if needed, 
        # but for now we just generate the docs.
        print(f"    - Generated: {path}")

    conn.close()
    print(f"\n[SUCCESS] Generated all PAN cards in '{OUTPUT_FOLDER}/'")

if __name__ == "__main__":
    main()
