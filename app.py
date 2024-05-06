import tkinter as tk
from tkinter import messagebox
from tts_with_rvc_with_lipsync import Text2RVCLipSync
import json
from PIL import Image, ImageTk
from moviepy.editor import VideoFileClip
from simpleaudio import WaveObject
from color_transfer import color_transfer
import numpy
import threading
import tempfile
import time

# big_file = "pupsik.mp4"
big_file = "images/big_pups_2.png"
face_file = "pupsik_face.mp4"
# face_file = "images/pups_2.png"


class VideoWindow(tk.Toplevel):
    def __init__(self, master=None):
        super().__init__(master)
        self.title("Video Output")
        self.video_canvas = tk.Canvas(self, width=1080, height=1080)
        self.video_canvas.pack()
        self.audio_path = None

        self.big_vid = False
        self.face_vid = False

        if big_file.split(".")[-1] == "mp4":
            self.big_vid = True
            self.background_video = VideoFileClip(big_file)
            self.background_frames = [Image.fromarray(self.background_video.get_frame(i*(1/self.background_video.fps))) for i in range(int(self.background_video.duration * self.background_video.fps))]
        elif big_file.split(".")[-1] == "png":
            big_pups_image = Image.open(big_file)
            self.big_photo = ImageTk.PhotoImage(big_pups_image)
            self.video_canvas.create_image(0, 0, anchor=tk.NW, image=self.big_photo)

        self.current_frame_index = 0

        self.audio_path = None

        if face_file.split(".")[-1] == "mp4":
            self.face_vid = True

        self.video_canvas.bind("<Configure>", self.on_canvas_resize)

    def update_background_frame(self, frame_number, corrected_frames, fps):
        if frame_number < len(corrected_frames):
            image = corrected_frames[frame_number]
            x = (self.canvas_width - image.width) // 2
            y = (self.canvas_height - image.height) // 2
            self.video_image = ImageTk.PhotoImage(image)
            threading.Thread(target=self.create_img, args=(self.video_image, x, y,)).start()

            self.current_frame_index += 1
            if self.current_frame_index >= len(corrected_frames) - 1: self.current_frame_index = 0

            self.master.after(int(1000 // fps), self.update_background_frame, self.current_frame_index, corrected_frames, fps)

    def on_canvas_resize(self, event):
        self.canvas_width = self.video_canvas.winfo_width()
        self.canvas_height = self.video_canvas.winfo_height()

        if not self.big_vid:
            image_width = self.big_photo.width()
            image_height = self.big_photo.height()

            x = (self.canvas_width - image_width) // 2
            y = (self.canvas_height - image_height) // 2
            
            self.video_canvas.delete("all")
            self.video_canvas.create_image(x, y, anchor=tk.NW, image=self.big_photo)
        else: threading.Thread(target=self.update_background_frame, args=(self.current_frame_index, self.background_frames, self.background_video.fps)).start()

    def adjust_colors(self):
        corrected_frames = []
        for frame_number in range(int(self.video.duration * self.video.fps)):
            frame = self.video.get_frame(frame_number * (1/self.video.fps))
            image = Image.fromarray(frame)

            if self.face_vid:
                self.face_video = VideoFileClip(face_file)
                self.reference_image = self.face_video.get_frame(0)
            else:
                self.reference_image = Image.open(face_file)

            self.reference_image = numpy.array(self.reference_image)

            corrected_frame = Image.fromarray(color_transfer(self.reference_image, numpy.array(image)))
            corrected_frames.append(corrected_frame)
        return corrected_frames

    def display_video(self, video_path):
        self.video = VideoFileClip(video_path)
        audio = self.video.audio
        audio_path = tempfile.NamedTemporaryFile(suffix='.wav').name
        audio.write_audiofile(audio_path)
        frame = self.video.get_frame(0)
        image = Image.fromarray(frame)
        
        self.video_image = ImageTk.PhotoImage(image)
        image_width = self.video_image.width()
        image_height = self.video_image.height()
        self.x = (self.canvas_width - image_width) // 2
        self.y = (self.canvas_height - image_height) // 2

        corrected_frames = self.adjust_colors()

        threading.Thread(target=self.play_audio, args=(audio_path,)).start()
        threading.Thread(target=self.update_frame, args=(0, corrected_frames)).start()

    def play_audio(self, audio_file):
        wave_obj = WaveObject.from_wave_file(audio_file)
        play_obj = wave_obj.play()
        play_obj.wait_done()

    def update_frame(self, frame_number, corrected_frames):
        if frame_number < len(corrected_frames):
            image = corrected_frames[frame_number]
            self.video_image = ImageTk.PhotoImage(image)
            threading.Thread(target=self.create_img, args=(self.video_image, self.x, self.y,)).start()

            self.master.after(int(1000 // self.video.fps), self.update_frame, frame_number + 1, corrected_frames)

    def create_img(self, video_image, x, y):
        self.video_canvas.create_image(x, y, anchor=tk.NW, image=video_image)

class App:
    def __init__(self, master):
        self.master = master
        self.master.title("TTS with RVC with Lipsync App")
        self.video_window = VideoWindow()

        with open('secrets.json', 'r') as f:
            secrets = json.load(f)

        api_key = secrets["lip_api_key"]
        rvc_path = "venv/src/rvclib"
        model_path = "models/denvot.pth"

        self.text2lip = Text2RVCLipSync(lip_api_key=api_key, rvc_path=rvc_path, model_path=model_path, lip_crop=True)

        self.video_frame = tk.Frame(self.master)
        self.video_frame.pack()

        self.player_queue = []
        self.queue_running = True
        self.queue_thread = threading.Thread(target=self.queue)
        self.queue_thread.start()

        self.text_frame = tk.Frame(self.master)
        self.text_frame.pack()

        tk.Label(self.text_frame, text="Enter text:").pack(side=tk.LEFT)
        self.text_entry = tk.Entry(self.text_frame, width=50)
        self.text_entry.pack(side=tk.LEFT)

        self.copy_button = tk.Button(self.text_frame, text="Copy", command=self.copy_text)
        self.copy_button.pack(side=tk.LEFT)

        self.paste_button = tk.Button(self.text_frame, text="Paste", command=self.paste_text)
        self.paste_button.pack(side=tk.LEFT)

        self.generate_button = tk.Button(self.text_frame, text="Generate Video", command=self.generate_video)
        self.generate_button.pack(side=tk.LEFT)

        self.process_label = tk.Label(self.master, text="")
        self.process_label.pack()

        self.master.protocol("WM_DELETE_WINDOW", self.on_closing)

    def copy_text(self):
        self.master.clipboard_clear()
        self.master.clipboard_append(self.text_entry.get())

    def paste_text(self):
        self.text_entry.insert(tk.INSERT, self.master.clipboard_get())

    def on_closing(self):
        self.queue_running = False
        self.queue_thread.join()
        self.master.destroy()

    def queue(self):
        while self.queue_running:
            if self.player_queue:
                video_path = self.player_queue.pop(0)
                self.video_window.display_video(video_path)
                self.generate_button.config(state=tk.NORMAL)
                self.process_label.config(text="")
                self.text_entry.config(state=tk.NORMAL)
                self.text_entry.delete(0, tk.END)
            time.sleep(1)

    def generate_video(self):
        text = self.text_entry.get()

        if text:
            self.generate_button.config(state=tk.DISABLED)
            self.process_label.config(text="Processing...")
            self.text_entry.config(state=tk.DISABLED)

            threading.Thread(target=self.generate_video_thread, args=(text,)).start()
        else:
            messagebox.showerror("Error", "Please enter some text.")

    def generate_video_thread(self, text):
        video_path = self.text2lip(text=text, file_path=face_file, rvc_pitch=6)
        self.player_queue.append(video_path)

def main():
    root = tk.Tk()
    app = App(root)
    root.mainloop()

if __name__ == "__main__":
    main()
