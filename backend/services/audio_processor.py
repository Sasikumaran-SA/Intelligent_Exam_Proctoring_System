import os
import json
import logging
from vosk import Model, KaldiRecognizer

class AudioProcessor:
    def __init__(self):
        model_path = os.path.join(os.path.dirname(__file__), '..', 'model')
        if not os.path.exists(model_path):
            logging.error(f"Vosk model not found at {model_path}. Speech detection will be disabled.")
            self.model = None
        else:
            self.model = Model(model_path)
        
        self.recognizers = {} # Dictionary to hold recognizers per session

    def get_recognizer(self, session_id: int):
        if not self.model:
            return None
        if session_id not in self.recognizers:
            self.recognizers[session_id] = KaldiRecognizer(self.model, 16000)
        return self.recognizers[session_id]

    def process_chunk(self, session_id: int, audio_data: bytes) -> str:
        """
        Processes a chunk of raw PCM 16-bit 16kHz mono audio.
        Returns recognized text if a full sentence is formed, else empty string.
        """
        rec = self.get_recognizer(session_id)
        if not rec:
            return ""

        if rec.AcceptWaveform(audio_data):
            result = json.loads(rec.Result())
            return result.get("text", "")
        else:
            # Partial results could be extracted here if needed
            # partial = json.loads(rec.PartialResult())
            return ""

    def cleanup_session(self, session_id: int):
        if session_id in self.recognizers:
            del self.recognizers[session_id]
