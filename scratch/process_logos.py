from PIL import Image
import os

def remove_white_bg_and_crop(input_path, output_path, tolerance=220):
    if not os.path.exists(input_path):
        print(f"File not found: {input_path}")
        return

    # Open image and convert to RGBA
    img = Image.open(input_path).convert("RGBA")
    data = img.getdata()

    new_data = []
    for item in data:
        # Check if the pixel is near white
        if item[0] > tolerance and item[1] > tolerance and item[2] > tolerance:
            # Change near-white pixels to transparent
            new_data.append((255, 255, 255, 0))
        else:
            new_data.append(item)

    # Use the non-deprecated method
    img.putdata(new_data)
    
    # Get bounding box of non-transparent pixels
    bbox = img.getbbox()
    if bbox:
        img = img.crop(bbox)
        
    img.save(output_path, "PNG")
    print(f"Processed and saved: {output_path}")

grindlays_src = r"C:\Users\M S I\.gemini\antigravity-ide\brain\c1001867-85b1-445c-a2f4-cb434b8c9cd4\.user_uploaded\media_1787037226887.jpg"
grindlays_dest = r"D:\Projects\Everbolt-Food-ERP\website\static\images\clients\grindlays.png"
if os.path.exists(grindlays_src):
    remove_white_bg_and_crop(grindlays_src, grindlays_dest, tolerance=220)
else:
    print(f"Could not find grindlays source: {grindlays_src}")
