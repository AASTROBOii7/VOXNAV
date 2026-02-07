# VoxNav 🎙️

A **voice-activated web navigation assistant** for Indian users, supporting **Hindi**, **Hinglish**, and **12 regional languages**.

## Features

- 🎤 **Speech Recognition** - IndicWhisper for accurate Hindi/Indian language ASR
- 🧠 **Intent Classification** - Gemini 1.5 Flash for understanding user commands
- 💬 **Slot Filling** - Multi-turn conversations to gather booking details
- 🌐 **Dynamic Prompts** - Context-aware assistance based on current website
- 🗣️ **Multilingual** - Hindi, Hinglish, Tamil, Telugu, Bengali, and more

## Quick Start

### 1. Installation

```bash
# Clone the repository
cd VoxNav

# Install dependencies
pip install -r requirements.txt
```

### 2. Set API Key

```bash
# Set your Gemini API key
export GEMINI_API_KEY="your-api-key-here"
```

### 3. Download IndicWhisper Model

Download the Hindi model from [AI4Bharat](https://indicwhisper.objectstore.e2enetworks.net/hindi_models.zip):

```bash
mkdir -p hindi_models
# Download and extract the model to hindi_models/whisper-medium-hi_alldata_multigpu
```

### 4. Run Examples

```bash
python examples.py
```

## Usage

### Basic Text Processing

```python
from core import VoxNavOrchestrator

# Initialize
voxnav = VoxNavOrchestrator(
    asr_model_path="hindi_models/whisper-medium-hi_alldata_multigpu",
    gemini_api_key="your-api-key"
)

# Process Hinglish input
response = voxnav.process_text(
    text_input="Mujhe Delhi se Mumbai ki train book karni hai",
    user_id="user123",
    current_url="https://www.irctc.co.in"
)

print(response.message)  # "Aap kab travel karna chahte ho?"
print(response.slots)    # {"source": "Delhi", "destination": "Mumbai"}
```

### Audio Processing

```python
# Process audio file
response = voxnav.process_audio(
    audio_input="recording.mp3",
    user_id="user123",
    language="hi"
)

print(response.transcription)  # "दिल्ली से मुंबई की ट्रेन बुक करो"
print(response.intent)         # "BOOKING"
```

### Individual Components

```python
# Intent Classification
from core import IntentDispatcher

dispatcher = IntentDispatcher()
result = dispatcher.classify("Amazon pe iPhone search karo")
# → Intent: SEARCH, sub_intent: product, language: hinglish

# Language Detection
from core import MultilingualHandler

handler = MultilingualHandler()
lang = handler.detect_language("Mujhe help chahiye")
# → Language: hinglish, confidence: 0.85

# Slot Filling
from core import SlotFiller

filler = SlotFiller()
result = filler.extract_slots(
    user_id="user123",
    user_input="Delhi se Mumbai",
    intent="BOOKING",
    sub_intent="train_ticket"
)
# → slots: {"source": "Delhi", "destination": "Mumbai"}, missing: ["date"]
```

## Architecture

```
VoxNav/
├── config.py              # Configuration settings
├── core/
│   ├── asr.py             # IndicWhisper ASR wrapper
│   ├── intent_dispatcher.py   # Gemini-based intent classification
│   ├── slot_filler.py     # Multi-turn slot extraction
│   ├── dynamic_prompts.py # Website-aware prompt generation
│   ├── multilingual.py    # Language detection & response
│   └── orchestrator.py    # Main coordinator
├── vistaar/               # IndicWhisper training tools
├── examples.py            # Usage examples
└── requirements.txt
```

## Supported Intents

| Intent | Sub-Intents | Example |
|--------|-------------|---------|
| BOOKING | train_ticket, flight, hotel, cab | "Book a train to Mumbai" |
| SEARCH | weather, product, general | "Amazon pe iPhone search karo" |
| NAVIGATION | go_to_page, scroll, click | "Settings page pe jao" |
| FORM_FILL | login, signup, payment | "Form fill karo" |
| CANCEL | cancel_booking, abort | "Cancel kar do" |
| HELP | how_to, what_can_you_do | "Tum kya kar sakte ho?" |

## Supported Languages

| Language | Code | Script | Detection |
|----------|------|--------|-----------|
| English | en | Latin | ✅ |
| Hindi | hi | Devanagari | ✅ |
| Hinglish | hinglish | Latin (romanized) | ✅ |
| Bengali | bn | Bengali | ✅ |
| Tamil | ta | Tamil | ✅ |
| Telugu | te | Telugu | ✅ |
| Marathi | mr | Devanagari | ✅ |
| Gujarati | gu | Gujarati | ✅ |
| Kannada | kn | Kannada | ✅ |
| Malayalam | ml | Malayalam | ✅ |
| Punjabi | pa | Gurmukhi | ✅ |
| Odia | or | Odia | ✅ |
| Urdu | ur | Arabic | ✅ |

## Supported Websites

Pre-configured with context for:
- **Travel**: IRCTC, MakeMyTrip, Ola, Uber
- **Shopping**: Amazon, Flipkart
- **Food**: Zomato, Swiggy
- **Entertainment**: BookMyShow
- **Search**: Google

## License

MIT License - see [LICENSE](LICENSE)
