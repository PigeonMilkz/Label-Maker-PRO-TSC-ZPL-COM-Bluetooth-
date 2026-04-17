import tkinter as tk
from tkinter import ttk, filedialog
from PIL import Image, ImageDraw, ImageFont, ImageTk, ImageOps, ImageEnhance, ImageGrab
import barcode
from barcode.writer import ImageWriter
import qrcode
import serial
import serial.tools.list_ports
import time

DPI = 300
WIDTH = int((40 / 25.4) * DPI)
HEIGHT = int((14 / 25.4) * DPI)

FONTS = {
    "Arial Bold": "arialbd.ttf",
    "Arial": "arial.ttf"
}

current_image = None

def get_font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except:
        return ImageFont.load_default()

def split_text(text, mode):
    words = text.split()

    if mode == "1 Line":
        return [text]

    if mode == "2 Lines":
        mid = len(words)//2
        return [" ".join(words[:mid]), " ".join(words[mid:])]

    lines = []
    current = ""
    for w in words:
        test = current + " " + w if current else w
        if len(test) > 12:
            lines.append(current)
            current = w
        else:
            current = test
    if current:
        lines.append(current)

    return lines

def fit_text(draw, lines, max_w, max_h, font_path):
    size = 100
    while size > 6:
        font = get_font(font_path, size)

        widths = [draw.textbbox((0,0), l, font=font)[2] for l in lines]
        heights = [draw.textbbox((0,0), l, font=font)[3] for l in lines]

        if max(widths) <= max_w and sum(heights) <= max_h:
            return font
        size -= 1

    return get_font(font_path, 10)

def generate_barcode(text):
    CODE128 = barcode.get_barcode_class('code128')
    return CODE128(text, writer=ImageWriter()).render()

def generate_qr(text):
    return qrcode.make(text).convert("RGB")

# ===== IMAGE FUNCTIONS =====
def paste_image():
    global current_image
    try:
        img = ImageGrab.grabclipboard()
        if isinstance(img, Image.Image):
            current_image = img
            update_preview()
    except Exception as e:
        print("Paste failed:", e)

def load_image():
    global current_image
    path = filedialog.askopenfilename(filetypes=[("Images", "*.png;*.jpg;*.jpeg;*.bmp")])
    if path:
        current_image = Image.open(path)
        update_preview()

def clear_image():
    global current_image
    current_image = None
    update_preview()

# ===== RENDER =====
def render_layer(base, text, mode, align):
    if not text or mode == "Off":
        return

    draw = ImageDraw.Draw(base)
    font_path = FONTS.get(font_var.get(), "arial.ttf")

    if mode == "Text":
        lines = split_text(text, line_mode.get())
        font = fit_text(draw, lines, WIDTH//2, HEIGHT-10, font_path)

        total_h = sum(draw.textbbox((0,0), l, font=font)[3] for l in lines)
        y = (HEIGHT - total_h)//2

        for line in lines:
            w = draw.textbbox((0,0), line, font=font)[2]

            if align == "Left":
                x = 5
            elif align == "Right":
                x = WIDTH - w - 5
            else:
                x = (WIDTH - w)//2

            draw.text((x,y), line, fill="black", font=font)
            y += font.size

    elif mode == "Barcode":
        img = generate_barcode(text)
        img.thumbnail((WIDTH//2, HEIGHT))
        x = 0 if align=="Left" else WIDTH-img.width if align=="Right" else (WIDTH-img.width)//2
        base.paste(img, (x, (HEIGHT-img.height)//2))

    elif mode == "QR":
        img = generate_qr(text)
        img.thumbnail((HEIGHT, HEIGHT))
        x = 0 if align=="Left" else WIDTH-img.width if align=="Right" else (WIDTH-img.width)//2
        base.paste(img, (x, (HEIGHT-img.height)//2))

def generate_image():
    img = Image.new("RGB", (WIDTH, HEIGHT), "white")

    if current_image:
        temp = current_image.copy()

        if temp.mode in ("RGBA", "LA"):
            bg = Image.new("RGB", temp.size, "white")
            bg.paste(temp, mask=temp.split()[3])
            temp = bg

        temp.thumbnail((WIDTH, HEIGHT))
        img.paste(temp, ((WIDTH-temp.width)//2, (HEIGHT-temp.height)//2))

    render_layer(img, entry1.get(), mode1.get(), align1.get())
    render_layer(img, entry2.get(), mode2.get(), align2.get())

    return img

# ===== PREVIEW =====
def update_preview(event=None):
    try:
        img = generate_image()
        img = ImageOps.grayscale(img)
        img = ImageEnhance.Contrast(img).enhance(contrast.get())

        if invert.get():
            img = ImageOps.invert(img)

        img.thumbnail((220,80))
        tkimg = ImageTk.PhotoImage(img)
        preview.config(image=tkimg)
        preview.image = tkimg
    except Exception as e:
        print("Preview error:", e)

# ===== PRINT =====
def prepare_print(img):
    img = ImageOps.grayscale(img)
    img = ImageEnhance.Contrast(img).enhance(contrast.get())

    if invert.get():
        img = ImageOps.invert(img)

    img = img.rotate(90, expand=True)
    img.thumbnail((96,284))
    img = img.convert("1")

    return img.tobytes().ljust(3408, b"\xff")

def do_print():
    img = generate_image()
    data = prepare_print(img)

    cmd = b"\x1b!o\r\n"
    cmd += b"SIZE 14.0 mm,40.0 mm\r\n"
    cmd += b"GAP 5.0 mm,0 mm\r\n"
    cmd += b"DIRECTION 1,1\r\n"
    cmd += f"DENSITY {density.get()}\r\n".encode()
    cmd += b"CLS\r\n"
    cmd += b"BITMAP 0,0,12,284,1," + data
    cmd += f"\r\nPRINT {copies.get()}\r\n".encode()

    with serial.Serial(port.get(),115200,timeout=2) as ser:
        time.sleep(0.2)
        ser.write(cmd)

# ===== TEXT TOOLS =====
def to_upper(entry):
    txt = entry.get()
    entry.delete(0, tk.END)
    entry.insert(0, txt.upper())
    update_preview()

def to_title(entry):
    txt = entry.get()
    entry.delete(0, tk.END)
    entry.insert(0, txt.title())
    update_preview()

# ===== UI =====
root = tk.Tk()
root.title("Label Maker PRO FINAL")

tk.Label(root, text="Font").pack()
font_var = tk.StringVar(value="Arial Bold")
ttk.Combobox(root, textvariable=font_var, values=list(FONTS.keys())).pack()

tk.Label(root, text="Text Layout Mode").pack()
line_mode = tk.StringVar(value="Auto Wrap")
ttk.Combobox(root, textvariable=line_mode,
             values=["Auto Wrap","1 Line","2 Lines"]).pack()

# LAYER 1
f1 = tk.LabelFrame(root, text="Layer 1 - Content")
f1.pack(fill="x")

tk.Label(f1, text="Text").pack()
entry1 = tk.Entry(f1)
entry1.pack(fill="x")
entry1.bind("<KeyRelease>", update_preview)

tk.Button(f1, text="UPPER", command=lambda: to_upper(entry1)).pack(side="left")
tk.Button(f1, text="Title Case", command=lambda: to_title(entry1)).pack(side="left")

tk.Label(f1, text="Type").pack()
mode1 = tk.StringVar(value="Text")
ttk.Combobox(f1, textvariable=mode1,
             values=["Text","Barcode","QR","Off"]).pack()

tk.Label(f1, text="Alignment").pack()
align1 = tk.StringVar(value="Left")
ttk.Combobox(f1, textvariable=align1,
             values=["Left","Center","Right"]).pack()

# LAYER 2
f2 = tk.LabelFrame(root, text="Layer 2 - Content")
f2.pack(fill="x")

tk.Label(f2, text="Text").pack()
entry2 = tk.Entry(f2)
entry2.pack(fill="x")
entry2.bind("<KeyRelease>", update_preview)

tk.Button(f2, text="UPPER", command=lambda: to_upper(entry2)).pack(side="left")
tk.Button(f2, text="Title Case", command=lambda: to_title(entry2)).pack(side="left")

tk.Label(f2, text="Type").pack()
mode2 = tk.StringVar(value="Off")
ttk.Combobox(f2, textvariable=mode2,
             values=["Text","Barcode","QR","Off"]).pack()

tk.Label(f2, text="Alignment").pack()
align2 = tk.StringVar(value="Right")
ttk.Combobox(f2, textvariable=align2,
             values=["Left","Center","Right"]).pack()

# IMAGE TOOLS
img_frame = tk.LabelFrame(root, text="Image Tools")
img_frame.pack(fill="x")

tk.Button(img_frame, text="Paste Image", command=paste_image).pack(side="left")
tk.Button(img_frame, text="Load Image", command=load_image).pack(side="left")
tk.Button(img_frame, text="Clear Image", command=clear_image).pack(side="left")

# SETTINGS
fs = tk.LabelFrame(root, text="Print Settings")
fs.pack(fill="x")

tk.Label(fs, text="Printer Port").pack()
port = tk.StringVar(value="COM5")
ttk.Combobox(fs, textvariable=port,
             values=[p.device for p in serial.tools.list_ports.comports()]).pack()

tk.Label(fs, text="Copies").pack()
copies = tk.IntVar(value=1)
tk.Spinbox(fs, from_=1, to=50, textvariable=copies).pack()

density = tk.IntVar(value=15)
tk.Scale(fs, from_=5,to=15,label="Density",
         variable=density, orient="horizontal").pack(fill="x")

contrast = tk.DoubleVar(value=2.0)
tk.Scale(fs, from_=1,to=4,resolution=0.1,label="Contrast",
         variable=contrast, orient="horizontal",
         command=update_preview).pack(fill="x")

invert = tk.BooleanVar(value=True)
tk.Checkbutton(fs, text="Invert", variable=invert,
               command=update_preview).pack()

# PREVIEW
tk.Label(root, text="Preview").pack()
preview = tk.Label(root)
preview.pack(pady=10)

tk.Button(root, text="Refresh Preview", command=update_preview).pack()
tk.Button(root, text="Print", command=do_print).pack()

update_preview()
root.mainloop()