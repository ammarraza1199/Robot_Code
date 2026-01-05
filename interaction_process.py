import speech_recognition as sr
import requests
import os
import logging
import time
import hashlib
from gtts import gTTS
from dotenv import load_dotenv
import re
import sys
import concurrent.futures
import multiprocessing
import random
import numpy as np
from collections import deque

# --- Full Multilingual Knowledge Base (with expanded keywords) ---
# (Knowledge base content remains the same, omitted for brevity)
DEPARTMENT_KEYWORDS = {
    "Cardiology Unit-1": ["heart", "chest pain", "chest tightness", "chest pressure", "palpitation", "angina", "bp", "blood pressure", "cardiac", "heart problem", "heart issue", "high bp", "low bp", "heartbeat", "cholesterol"], "Cardiology Unit-2": ["irregular heartbeat", "arrhythmia", "breathlessness", "breathing problem", "breath", "shortness of breath"], "Cardiology Unit-3": ["coronary artery", "echo", "ecg", "ekg", "heart test"], "Cardiology Unit-4": ["heart attack", "myocardial infarction", "heart failure"], "Cardio Thoracic Surgery Unit-1": ["bypass", "valve replacement", "open heart surgery", "cabg", "pacemaker", "heart surgery"], "Cardio Thoracic Surgery Unit-2": ["lung surgery", "thoracic", "aortic aneurysm", "chest surgery"], "Medical Gastroenterology": ["stomach pain", "indigestion", "gas", "acidity", "liver", "pancreas", "ulcer", "jaundice", "stomach", "belly pain", "abdomen pain", "stomach ache", "vomiting", "loose motion", "diarrhea"], "Surgical Gastroenterology": ["stomach surgery", "gall bladder surgery", "hernia surgery", "appendicitis", "colon surgery", "intestine surgery", "appendix", "gallstones"], "Medical Genetics": ["genetic", "dna", "inherited", "chromosome", "down syndrome", "sickle cell", "hereditary", "family history", "genetic disorder", "birth defect"], "Pulmonary Medicine": ["lungs", "asthma", "cough", "tb", "pneumonia", "respiratory", "lung problem", "breathing", "breathing difficulty", "wheezing", "tuberculosis"], "Surgical Oncology": ["cancer surgery", "tumor", "breast cancer", "colon cancer", "lung cancer", "biopsy", "cancer", "tumor removal", "cancer growth"], "Urology": ["urine", "kidney stone", "bladder", "prostate", "urinary infection", "incontinence", "kidney", "urinary problem", "urinary", "prostate gland", "burning urine"], "Vascular Surgery": ["veins", "arteries", "blood clot", "varicose veins", "circulation", "diabetic foot", "blood vessel", "leg pain", "swelling in legs"],
}
DEPARTMENT_ROOMS_TE = {
    "Cardiology Unit-1": "గ్రౌండ్ ఫ్లోర్, గది నం 2,4,6", "Cardiology Unit-2": "గ్రౌండ్ ఫ్లోర్, గది నం 3,5", "Cardiology Unit-3": "గ్రౌండ్ ఫ్లోర్, గది నం 3,5", "Cardiology Unit-4": "గ్రౌండ్ ఫ్లోర్, గది నం 2,4,6", "Cardio Thoracic Surgery Unit-1": "గ్రౌండ్ ఫ్లోర్, గది నం 10", "Cardio Thoracic Surgery Unit-2": "గ్రౌండ్ ఫ్లోర్, గది నం 10", "Medical Gastroenterology": "5వ అంతస్తు, గది నం 502", "Surgical Gastroenterology": "5వ అంతస్తు, గది నం 503", "Medical Genetics": "4వ అంతస్తు, గది నం 409", "Pulmonary Medicine": "4వ అంతస్తు, గది నం 403 మరియు 404", "Surgical Oncology": "4వ అంతస్తు, గది నం 410", "Urology": "6వ అంతస్తు, గది నం 609-611", "Vascular Surgery": "5వ అంతస్తు, గది నం 501",
}
DEPARTMENT_ROOMS_EN = {
    "Cardiology Unit-1": "Ground floor, room no 2,4,6", "Cardiology Unit-2": "Ground floor, room no 3,5", "Cardiology Unit-3": "Ground floor, room no 3,5", "Cardiology Unit-4": "Ground floor, room no 2,4,6", "Cardio Thoracic Surgery Unit-1": "Ground floor, room no 10", "Cardio Thoracic Surgery Unit-2": "Ground floor, room no 10", "Medical Gastroenterology": "5th floor, room no 502", "Surgical Gastroenterology": "5th floor, room no 503", "Medical Genetics": "4th floor, room no 409", "Pulmonary Medicine": "4th floor, room no 403 and 404", "Surgical Oncology": "4th floor, room no 410", "Urology": "6th floor, room no 609-611", "Vascular Surgery": "5th floor, room no 501",
}
DEPARTMENT_ROOMS_HI = {
    "Cardiology Unit-1": "ग्राउंड फ्लोर, कमरा नंबर 2,4,6", "Cardiology Unit-2": "ग्राउंड फ्लोर, कमरा नंबर 3,5", "Cardiology Unit-3": "ग्राउंड फ्लोर, कमरा नंबर 3,5", "Cardiology Unit-4": "ग्राउंड फ्लोर, कमरा नंबर 2,4,6", "Cardio Thoracic Surgery Unit-1": "ग्राउंड फ्लोर, कमरा नंबर 10", "Cardio Thoracic Surgery Unit-2": "ग्राउंड फ्लोर, कमरा नंबर 10", "Medical Gastroenterology": "5वीं मंजिल, कमरा नंबर 502", "Surgical Gastroenterology": "5वीं मंजिल, कमरा नंबर 503", "Medical Genetics": "4वीं मंजिल, कमरा नंबर 409", "Pulmonary Medicine": "4वीं मंजिल, कमरा नंबर 403 और 404", "Surgical Oncology": "4वीं मंजिल, कमरा नंबर 410", "Urology": "6वीं मंजिल, कमरा नंबर 609-611", "Vascular Surgery": "5वीं मंजिल, कमरा नंबर 501",
}
DEPARTMENT_DOCTORS = {
    "Cardiology Unit-1": "Dr. O. Sai Satish", "Cardiology Unit-2": "Dr. B. Srinivas", "Cardiology Unit-3": "Dr. N. Rama Kumari", "Cardiology Unit-4": "Dr. M. Jyotsna", "Cardio Thoracic Surgery Unit-1": "Dr. R. V. Kumar", "Cardio Thoracic Surgery Unit-2": "Dr. M. Amaresh Rao", "Medical Gastroenterology": "Dr. Y. Satyanarayana Raju", "Surgical Gastroenterology": "Dr. N. Bheerappa", "Medical Genetics": "Dr. Prajnya Ranganath", "Pulmonary Medicine": "Dr. G. K. Paramjyothi", "Surgical Oncology": "Dr. Rajshekar Shantappa", "Urology": "Dr. Ch. Ram Reddy", "Vascular Surgery": "Dr. Sandeep Mahapatra",
}
DEPARTMENT_NAMES_TELUGU = {
    "Cardiology Unit-1": "కార్డియాలజీ యూనిట్-1", "Cardiology Unit-2": "కార్డియాలజీ యూనిట్-2", "Cardiology Unit-3": "కార్డియాలజీ యూనిట్-3", "Cardiology Unit-4": "కార్డియాలజీ యూనిట్-4", "Cardio Thoracic Surgery Unit-1": "కార్డియో థోరాసిక్ సర్జరీ యూనిట్-1", "Cardio Thoracic Surgery Unit-2": "కార్డియో థోరాసిక్ సర్జరీ యూనిట్-2", "Medical Gastroenterology": "మెడికల్ గ్యాస్ట్రోఎంటరాలజీ", "Surgical Gastroenterology": "సర్జికల్ గ్యాస్ట్రోఎంటరాలజీ", "Medical Genetics": "మెడికల్ జెనెటిక్స్", "Pulmonary Medicine": "పల్మనరీ మెడిసిన్", "Surgical Oncology": "సర్జికల్ ఆంకాలజీ", "Urology": "యూరాలజీ", "Vascular Surgery": "వాస్కులర్ సర్జరీ",
}

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("InteractionProcess")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
AUDIO_CACHE_DIR = os.path.join(SCRIPT_DIR, "audio_cache")

if not os.path.exists(AUDIO_CACHE_DIR):
    os.makedirs(AUDIO_CACHE_DIR)

class InteractionProcess:
    def __init__(self, audio_queue, motor_queue, shutdown_flag, audio_playing_flag, device_index=None):
        self.audio_queue = audio_queue
        self.motor_queue = motor_queue
        self.shutdown_flag = shutdown_flag
        self.audio_playing_flag = audio_playing_flag
        
        logger.info("Initializing speech recognizer...")
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone(device_index=device_index, sample_rate=16000, chunk_size=1024)
        
        self.groq_api_key = os.environ.get("GROQ_API_KEY")
        if not self.groq_api_key:
            logger.error("FATAL: GROQ_API_KEY environment variable not set.")
        self.groq_url = "https://api.groq.com/openai/v1/chat/completions"
        
        # Audio monitoring settings for cough/sneeze
        self.recognizer.energy_threshold = 1000 # Default energy threshold
        self.recognizer.dynamic_energy_threshold = True
        self.SUDDEN_SOUND_THRESHOLD_MULTIPLIER = 2.5 # How much louder than ambient noise a sound must be
        self.SUDDEN_SOUND_COOLDOWN = 10
        self.last_sudden_sound_time = 0

        self.load_knowledge_base()

    def load_knowledge_base(self):
        """Loads and prepares the full multilingual knowledge base."""
        logger.info("Loading and augmenting full multilingual knowledge base...")
        # (Omitted for brevity, no changes here)
        self.department_doctors = DEPARTMENT_DOCTORS
        self.department_names_telugu = DEPARTMENT_NAMES_TELUGU
        self.department_rooms = {'te': DEPARTMENT_ROOMS_TE, 'en': DEPARTMENT_ROOMS_EN, 'hi': DEPARTMENT_ROOMS_HI}
        self.multilang_keywords = { 'en': DEPARTMENT_KEYWORDS, 'hi': { "Cardiology Unit-1": ["दिल", "छाती में दर्द", "हृदय"], "Pulmonary Medicine": ["फेफड़े", "खांसी", "सांस"], "Urology": ["मूत्र", "गुर्दे", "किडनी"], "Medical Gastroenterology": ["पेट दर्द", "पेट", "लीवर"], "Surgical Oncology": ["कैंसर", "ट्यूमर"], "Vascular Surgery": ["नसों में दर्द"] }, 'te': { "Cardiology Unit-1": ["గుండె", "ఛాతీ నొప్పి"], "Pulmonary Medicine": ["ఊపిరితిత్తులు", "దగ్గు", "ఆయాసం"], "Urology": ["మూత్ర", "కిడ్నీ"], "Medical Gastroenterology": ["కడుపు నొప్పి", "కాలేయం"], "Surgical Oncology": ["క్యాన్సర్", "కణితి"], "Vascular Surgery": ["కాళ్ళ వాపు"] } }
        self.english_anchors = ["i am", "i'm", "i have", "i've", "my", "this is", "can you", "please", "where is", "what is", "how do i", "facing", "having", "suffering", "pain", "headache", "stomach", "fever", "doctor"]
        for dept_name in self.multilang_keywords['en'].keys(): self.multilang_keywords['en'][dept_name].append(dept_name.lower())
        for dept_name_en, dept_name_te in self.department_names_telugu.items():
            if dept_name_en in self.multilang_keywords['te']: self.multilang_keywords['te'][dept_name_en].append(dept_name_te.lower())
        self.SYSTEM_PROMPTS = { 'en': "You are a hospital navigation assistant. Your ONLY job is to match user-reported symptoms to the most relevant department from the provided list. Respond ONLY with the department information in the requested format. Do not diagnose, offer advice, or have any other conversation.", 'hi': "आप एक अस्पताल नेविगेशन सहायक हैं। आपका एकमात्र काम उपयोगकर्ता द्वारा बताए गए लक्षणों को प्रदान की गई सूची से सबसे प्रासंगिक विभाग से मिलाना है। केवल अनुरोधित प्रारूप में विभाग की जानकारी के साथ प्रतिक्रिया दें। निदान, सलाह या कोई अन्य बातचीत न करें।", 'te': "మీరు హాస్పిటల్ నావిగేషన్ అసిస్టెంట్. వినియోగదారు నివేదించిన లక్షణాలను అందించిన జాబితా నుండి అత్యంత సంబంధిత విభాగానికి సరిపోల్చడం మాత్రమే మీ పని. అభ్యర్థించిన ఫార్మాట్‌లో మాత్రమే విభాగం సమాచారంతో ప్రతిస్పందించండి. నిర్ధారణ, సలహా లేదా మరే ఇతర సంభాషణ చేయవద్దు." }
        self.EXIT_COMMANDS = {'en': ["exit", "quit", "stop", "bye"], 'hi': ["बंद", "रुको", "विदा"], 'te': ["ఆపు", "వద్దు", "బై"]}
        logger.info("Knowledge base loaded and tuned.")

    def queue_audio(self, text: str, lang: str, interrupt: bool = True):
        if not text: return
        if interrupt:
            self.audio_queue.put({'command': 'stop'})
            time.sleep(0.1)

        clean_text = re.sub(r'[\*#\-]', '', text)
        hash_object = hashlib.md5((clean_text + lang).encode())
        audio_filename = f"interaction_{hash_object.hexdigest()}.mp3"
        file_path = os.path.join(AUDIO_CACHE_DIR, audio_filename)

        if not os.path.exists(file_path):
            logger.info(f"Generating new audio for '{clean_text[:30]}...' in '{lang}'")
            try:
                tts = gTTS(text=clean_text, lang=lang, slow=False)
                tts.save(file_path)
            except Exception as e:
                logger.error(f"gTTS failed: {e}")
                return
        
        audio_request = {'command': 'play', 'file': audio_filename}
        logger.info(f"Queueing audio request: {audio_request}")
        self.audio_queue.put(audio_request)

    def _calculate_db(self, audio_data):
        """Helper to calculate dB of a raw audio chunk."""
        audio_array = np.frombuffer(audio_data, dtype=np.int16)
        if len(audio_array) == 0: return 0
        rms = np.sqrt(np.mean(audio_array.astype(np.float64)**2))
        return 20 * np.log10(rms + 1e-9) if rms > 0 else 0

    def _background_callback(self, recognizer, audio_data):
        """
        This function is called in a background thread whenever audio is detected.
        It attempts to recognize speech and, if that fails, checks for loud sounds.
        """
        logger.debug("BACKGROUND_CALLBACK: Entered _background_callback.")
        # Do not process anything if the robot is currently speaking
        if self.audio_playing_flag.is_set():
            logger.debug("BACKGROUND_CALLBACK: Skipping - audio_playing_flag is SET.")
            return

        # 1. Attempt to recognize speech using a multi-lingual approach
        try:
            # Parallel recognition for multiple languages
            candidates = []
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future_to_lang = {executor.submit(recognizer.recognize_google, audio_data, language=lang): lang for lang in ['en-IN', 'hi-IN', 'te-IN']}
                for future in concurrent.futures.as_completed(future_to_lang):
                    lang_simple = future_to_lang[future].split('-')[0]
                    try:
                        text = future.result()
                        if text:
                            logger.info(f"Potential speech match in {lang_simple}: '{text}'")
                            candidates.append({'lang': lang_simple, 'text': text.lower()})
                    except sr.UnknownValueError:
                        pass # This is expected if the audio is not speech in this language
                    except Exception as e:
                        logger.error(f"Recognition error for {lang_simple}: {e}")
            
            if candidates:
                # Simple selection: pick the longest recognized text
                best_match = max(candidates, key=lambda x: len(x['text']))
                logger.info(f"Speech detected in '{best_match['lang']}': '{best_match['text']}'")
                self.process_command(best_match['text'], best_match['lang'])
                return # Stop further processing

        except Exception as e:
            logger.error(f"Error during speech recognition in callback: {e}")

        # 2. If no speech was recognized, check for sudden loud sounds (cough/sneeze)
        current_time = time.time()
        audio_db = self._calculate_db(audio_data.get_raw_data())
        dynamic_energy_threshold = recognizer.energy_threshold * self.SUDDEN_SOUND_THRESHOLD_MULTIPLIER

        if audio_db > dynamic_energy_threshold:
            if (current_time - self.last_sudden_sound_time) > self.SUDDEN_SOUND_COOLDOWN:
                if not self.audio_playing_flag.is_set():
                    self.last_sudden_sound_time = current_time
                    logger.warning(f"Sudden sound detected (Cough/Sneeze?): {audio_db:.1f} dB > {dynamic_energy_threshold:.1f} dB")
                    # Announce without interrupting
                    self.audio_queue.put({'command': 'play', 'file': 'cough_sneeze.mp3'})

    def process_command(self, command, lang):
        """Processes a recognized text command."""
        # Send motor command to turn towards the user
        self.motor_queue.put(f"turn_to:{random.randint(-45, 45)}")

        response_text = ""
        if any(cmd in command for cmd in self.EXIT_COMMANDS.get(lang, [])):
            response_text = "Goodbye!"
            self.shutdown_flag.set() # Signal all processes to shut down
        else:
            matched_dept = self.find_department(command, lang)
            if matched_dept:
                response_text = self._format_guidance_response(matched_dept, lang)
            elif self.is_medical_query(command):
                response_text = "I cannot provide medical advice. Please consult a doctor."
            else:
                response_text = self.query_llama(command, lang)
        
        if response_text:
            logger.info(f"Responding with: '{response_text}'")
            self.queue_audio(response_text, lang, interrupt=True)
        
        # After responding, turn back to center
        time.sleep(1)
        self.motor_queue.put("turn_to:0")

    def find_department(self, user_text, lang):
        if lang not in self.multilang_keywords: return None
        for dept, keywords in self.multilang_keywords[lang].items():
            if any(keyword in user_text for keyword in keywords):
                logger.info(f"Keyword match for navigation: '{dept}'")
                return dept
        return None

    def _format_guidance_response(self, dept, lang):
        """Formats the guidance response."""
        doctor = self.department_doctors.get(dept, "details not available")
        location = self.department_rooms[lang].get(dept, "details not available")
        dept_name = self.department_names_telugu.get(dept, dept) if lang == 'te' else dept
        
        if lang == 'te': return f"విభాగం పేరు {dept_name}, డాక్టర్ పేరు {doctor}, మరియు చిరునామా {location}."
        elif lang == 'hi': return f"विभाग का नाम {dept}, डॉक्टर का नाम {doctor}, और पता {location} है।"
        else: return f"The department name is {dept}, the doctor's name is {doctor}, and the address is {location}."

    def is_medical_query(self, text):
        medical_keywords = ["what is", "symptoms of", "causes of", "treatment for", "diagnose", "medicine for", "pain in", "kya hai", "lakshan", "ilaaj", "noppi", "mandhu"]
        return any(keyword in text for keyword in medical_keywords)

    def query_llama(self, user_text, lang):
        """Queries the Llama 3.1 model via Groq API."""
        logger.info("Building context-rich prompt for LLM...")
        # (Omitted for brevity, no changes here)
        context = "Here is the hospital data:\n"
        for dept_en, doc in self.department_doctors.items():
            loc = self.department_rooms[lang].get(dept_en, "N/A")
            dept_name = self.department_names_telugu.get(dept_en, dept_en) if lang == 'te' else dept_en
            context += f"- Department: {dept_name}, Doctor: {doc}, Location: {loc}\n"
        system_prompt = self.SYSTEM_PROMPTS.get(lang, self.SYSTEM_PROMPTS['en']) + context
        headers = {"Authorization": f"Bearer {self.groq_api_key}", "Content-Type": "application/json"}
        payload = {"model": "llama-3.1-8b-instant", "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_text}], "max_tokens": 150}
        try:
            response = requests.post(self.groq_url, headers=headers, json=payload, timeout=20)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
        except requests.exceptions.RequestException as e:
            logger.error(f"Groq API request failed: {e}")
            return "Sorry, I'm having trouble connecting to my brain."

    def start(self):
        """Main entry point for the interaction process."""
        if not self.groq_api_key:
            logger.error("Interaction process cannot start without GROQ_API_KEY.")
            return

        logger.info("Interaction Process running...")
        self.queue_audio("Hello, how can I help you?", "en", interrupt=False)

        # Calibrate ambient noise
        with self.microphone as source:
            logger.info("Calibrating for ambient noise...")
            self.recognizer.adjust_for_ambient_noise(source, duration=1.0)
            logger.info(f"Ambient energy threshold set to: {self.recognizer.energy_threshold:.2f}")

        # Start listening in the background
        stop_listening = self.recognizer.listen_in_background(self.microphone, self._background_callback, phrase_time_limit=15)
        logger.info("Background listener started.")

        # Keep the process alive while the background thread works
        while not self.shutdown_flag.is_set():
            time.sleep(0.5)

        logger.info("Shutting down Interaction Process...")
        stop_listening(wait_for_stop=False)
        logger.info("Background listener stopped.")

def interaction_process_func(audio_queue, motor_queue, shutdown_flag, audio_playing_flag):
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    interaction_system = InteractionProcess(audio_queue, motor_queue, shutdown_flag, audio_playing_flag)
    interaction_system.start()
