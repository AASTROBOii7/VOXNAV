#!/usr/bin/env python
"""
VoxNav Voice Assistant with Push-to-Talk GUI
Press Start to begin recording, Stop to end and process.
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
import queue
import json
import re
import wave
import tempfile
import os

# Audio imports
import pyaudio
import speech_recognition as sr
import requests

# Configuration
MIC_INDEX = 2  # OnePlus Buds 3 - change if needed
SAMPLE_RATE = 16000
CHUNK_SIZE = 1024


class VoxNavGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("🎤 VoxNav Voice Assistant")
        self.root.geometry("600x500")
        self.root.configure(bg="#1a1a2e")
        
        # Recording state
        self.is_recording = False
        self.audio_frames = []
        self.audio_thread = None
        self.pyaudio = pyaudio.PyAudio()
        self.stream = None
        
        # Message queue for thread-safe UI updates
        self.msg_queue = queue.Queue()
        
        # Check Ollama
        self.ollama_model = self._check_ollama()
        
        self._create_ui()
        self._process_queue()
    
    def _check_ollama(self):
        """Check if Ollama is available."""
        try:
            resp = requests.get("http://localhost:11434/api/tags", timeout=2)
            if resp.status_code == 200:
                models = [m.get("name") for m in resp.json().get("models", [])]
                return "llama3.2:3b" if "llama3.2:3b" in models else models[0] if models else None
        except:
            pass
        return None
    
    def _create_ui(self):
        """Create the UI elements."""
        # Title
        title = tk.Label(
            self.root,
            text="🎤 VoxNav Voice Assistant",
            font=("Segoe UI", 20, "bold"),
            bg="#1a1a2e",
            fg="#e94560"
        )
        title.pack(pady=20)
        
        # Status label
        self.status_label = tk.Label(
            self.root,
            text="Ready - Press Start to speak",
            font=("Segoe UI", 12),
            bg="#1a1a2e",
            fg="#0f3460"
        )
        self.status_label.pack(pady=10)
        
        # Ollama status
        ollama_text = f"✅ Ollama: {self.ollama_model}" if self.ollama_model else "⚠️ Ollama not available"
        ollama_label = tk.Label(
            self.root,
            text=ollama_text,
            font=("Segoe UI", 9),
            bg="#1a1a2e",
            fg="#16c79a" if self.ollama_model else "#ff6b6b"
        )
        ollama_label.pack()
        
        # Buttons frame
        btn_frame = tk.Frame(self.root, bg="#1a1a2e")
        btn_frame.pack(pady=20)
        
        # Start button (green)
        self.start_btn = tk.Button(
            btn_frame,
            text="🎤 START",
            font=("Segoe UI", 14, "bold"),
            bg="#16c79a",
            fg="white",
            width=12,
            height=2,
            command=self.start_recording,
            relief="flat",
            cursor="hand2"
        )
        self.start_btn.pack(side=tk.LEFT, padx=10)
        
        # Stop button (red)
        self.stop_btn = tk.Button(
            btn_frame,
            text="⏹ STOP",
            font=("Segoe UI", 14, "bold"),
            bg="#e94560",
            fg="white",
            width=12,
            height=2,
            command=self.stop_recording,
            state=tk.DISABLED,
            relief="flat",
            cursor="hand2"
        )
        self.stop_btn.pack(side=tk.LEFT, padx=10)
        
        # Recording indicator
        self.recording_indicator = tk.Label(
            self.root,
            text="",
            font=("Segoe UI", 24),
            bg="#1a1a2e",
            fg="#e94560"
        )
        self.recording_indicator.pack(pady=10)
        
        # Results frame
        results_frame = tk.Frame(self.root, bg="#1a1a2e")
        results_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Transcription label
        tk.Label(
            results_frame,
            text="📝 You said:",
            font=("Segoe UI", 11, "bold"),
            bg="#1a1a2e",
            fg="white"
        ).pack(anchor=tk.W)
        
        self.transcription_text = tk.Label(
            results_frame,
            text="(waiting for input...)",
            font=("Segoe UI", 12),
            bg="#0f3460",
            fg="white",
            wraplength=500,
            justify=tk.LEFT,
            padx=10,
            pady=10
        )
        self.transcription_text.pack(fill=tk.X, pady=5)
        
        # Intent label
        tk.Label(
            results_frame,
            text="🎯 Intent:",
            font=("Segoe UI", 11, "bold"),
            bg="#1a1a2e",
            fg="white"
        ).pack(anchor=tk.W, pady=(10, 0))
        
        self.intent_text = tk.Label(
            results_frame,
            text="(waiting...)",
            font=("Segoe UI", 12),
            bg="#0f3460",
            fg="#16c79a",
            wraplength=500,
            justify=tk.LEFT,
            padx=10,
            pady=10
        )
        self.intent_text.pack(fill=tk.X, pady=5)
        
        # Mic index selector
        mic_frame = tk.Frame(self.root, bg="#1a1a2e")
        mic_frame.pack(pady=10)
        
        tk.Label(
            mic_frame,
            text="Mic Index:",
            font=("Segoe UI", 9),
            bg="#1a1a2e",
            fg="white"
        ).pack(side=tk.LEFT)
        
        self.mic_var = tk.StringVar(value=str(MIC_INDEX))
        mic_entry = tk.Entry(mic_frame, textvariable=self.mic_var, width=5, font=("Segoe UI", 9))
        mic_entry.pack(side=tk.LEFT, padx=5)
    
    def start_recording(self):
        """Start audio recording."""
        if self.is_recording:
            return
        
        self.is_recording = True
        self.audio_frames = []
        
        # Update UI
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.status_label.config(text="🔴 Recording... Speak now!", fg="#e94560")
        self.recording_indicator.config(text="🔴")
        
        # Start recording in a separate thread
        self.audio_thread = threading.Thread(target=self._record_audio)
        self.audio_thread.start()
    
    def _record_audio(self):
        """Record audio in a separate thread."""
        try:
            mic_index = int(self.mic_var.get())
            
            self.stream = self.pyaudio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=SAMPLE_RATE,
                input=True,
                input_device_index=mic_index,
                frames_per_buffer=CHUNK_SIZE
            )
            
            while self.is_recording:
                try:
                    data = self.stream.read(CHUNK_SIZE, exception_on_overflow=False)
                    self.audio_frames.append(data)
                except:
                    break
                    
        except Exception as e:
            self.msg_queue.put(("error", f"Recording error: {e}"))
    
    def stop_recording(self):
        """Stop recording and process audio."""
        if not self.is_recording:
            return
        
        self.is_recording = False
        
        # Wait for recording thread to finish
        if self.audio_thread:
            self.audio_thread.join(timeout=1)
        
        # Close stream
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None
        
        # Update UI
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.status_label.config(text="🔄 Processing...", fg="orange")
        self.recording_indicator.config(text="")
        
        # Process in background
        threading.Thread(target=self._process_audio).start()
    
    def _process_audio(self):
        """Process recorded audio."""
        if not self.audio_frames:
            self.msg_queue.put(("status", "No audio recorded"))
            return
        
        try:
            # Save to temp WAV file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                temp_path = f.name
            
            wf = wave.open(temp_path, 'wb')
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(b''.join(self.audio_frames))
            wf.close()
            
            # Transcribe
            recognizer = sr.Recognizer()
            with sr.AudioFile(temp_path) as source:
                audio = recognizer.record(source)
            
            # Clean up
            os.unlink(temp_path)
            
            # Use Google Speech Recognition
            text = recognizer.recognize_google(audio, language="hi-IN")
            self.msg_queue.put(("transcription", text))
            
            # Classify intent
            if self.ollama_model:
                intent_result = self._classify_intent(text)
                self.msg_queue.put(("intent", intent_result))
            else:
                self.msg_queue.put(("intent", {"intent": "N/A", "note": "Ollama not available"}))
            
            self.msg_queue.put(("status", "Ready - Press Start to speak"))
            
        except sr.UnknownValueError:
            self.msg_queue.put(("error", "Could not understand audio"))
        except sr.RequestError as e:
            self.msg_queue.put(("error", f"Speech API error: {e}"))
        except Exception as e:
            self.msg_queue.put(("error", f"Error: {e}"))
    
    def _classify_intent(self, text):
        """Classify intent using Ollama."""
        prompt = f"""You are an intent classifier. Classify the input into ONE category.

Categories:
- BOOKING: book tickets, order food, reserve hotel, cab booking
- SEARCH: find information, weather, product search
- CANCEL: cancel, stop, abort, go back
- HELP: help, assistance, how to
- GENERAL_INFO: greetings, thanks

Input: "{text}"

Reply with ONLY a JSON object:
{{"intent": "CATEGORY_NAME", "confidence": 0.95, "action": "brief description"}}"""

        try:
            payload = {
                "model": self.ollama_model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.1, "num_predict": 100}
            }
            resp = requests.post("http://localhost:11434/api/generate", json=payload, timeout=30)
            response = resp.json().get("response", "")
            
            # Parse JSON
            json_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            return {"intent": "UNKNOWN", "raw": response[:100]}
        except Exception as e:
            return {"intent": "ERROR", "error": str(e)}
    
    def _process_queue(self):
        """Process messages from background threads."""
        try:
            while True:
                msg_type, msg_data = self.msg_queue.get_nowait()
                
                if msg_type == "transcription":
                    self.transcription_text.config(text=f'"{msg_data}"')
                elif msg_type == "intent":
                    intent = msg_data.get("intent", "UNKNOWN")
                    action = msg_data.get("action", "")
                    confidence = msg_data.get("confidence", 0)
                    self.intent_text.config(text=f"{intent} ({confidence:.0%})\n{action}")
                elif msg_type == "status":
                    self.status_label.config(text=msg_data, fg="#16c79a")
                elif msg_type == "error":
                    self.status_label.config(text=msg_data, fg="#e94560")
                    self.transcription_text.config(text="(error)")
                    self.start_btn.config(state=tk.NORMAL)
                    self.stop_btn.config(state=tk.DISABLED)
                    
        except queue.Empty:
            pass
        
        # Check again in 100ms
        self.root.after(100, self._process_queue)
    
    def on_closing(self):
        """Clean up on window close."""
        self.is_recording = False
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        self.pyaudio.terminate()
        self.root.destroy()


def main():
    root = tk.Tk()
    app = VoxNavGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()
