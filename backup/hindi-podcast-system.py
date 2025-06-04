import os
import json
import time
import random
import requests
from pydub import AudioSegment, effects
import argparse

# Configuration
class Config:
    # ElevenLabs settings
    ELEVENLABS_API_KEY = "sk_e016ab1ac481c8a954dd88ea249fd5cfd9f0573628c09cee"  # Replace with your API key
    
    # Hindi voice options from ElevenLabs
    # You should browse their voice library and choose Hindi voices
    ELEVENLABS_VOICES = {
        "Male": "m5qndnI7u4OAdXhH0Mr5",    # Replace with a Hindi male voice ID
        "Female": "FFmp1h1BMl0iVHA0JxrI" # Replace with a Hindi female voice ID
    }
    
    # You can use their multilingual model for Hindi
    ELEVENLABS_MODEL = "eleven_multilingual_v2"
    
    # Voice settings
    VOICE_SETTINGS = {
        "Male": {
            "stability": 0.4,           # Slightly higher for Hindi to maintain clarity
            "similarity_boost": 0.75,    # Balance between voice consistency and natural speaking
            "style": 0.0,              # Keep neutral style
            "use_speaker_boost": True,  # Enhances voice clarity
        },
        "Female": {
            "stability": 0.35,          # More variation for female voice
            "similarity_boost": 0.7,     # Balance between voice consistency and natural speaking
            "style": 0.0,              # Keep neutral style
            "use_speaker_boost": True,  # Enhances voice clarity
        }
    }
    
    # Audio settings
    PAUSE_BETWEEN_TURNS = 700  # milliseconds (slightly longer for Hindi)

def text_to_speech_elevenlabs(text, speaker_type):
    """Convert Hindi text to speech using ElevenLabs multilingual"""
    
    # Create output directory if it doesn't exist
    os.makedirs("audio-files", exist_ok=True)
    
    # Get the voice ID and settings for this speaker
    voice_id = Config.ELEVENLABS_VOICES[speaker_type]
    voice_settings = Config.VOICE_SETTINGS[speaker_type]
    
    # Prepare the API endpoint
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    
    # Add some light enhancement for better Hindi pronunciation
    enhanced_text = enhance_hindi_text(text)
    
    # Create the request data
    data = {
        "text": enhanced_text,
        "model_id": Config.ELEVENLABS_MODEL,
        "voice_settings": {
            "stability": voice_settings["stability"],
            "similarity_boost": voice_settings["similarity_boost"],
            "style": voice_settings["style"],
            "use_speaker_boost": voice_settings["use_speaker_boost"]
        }
    }
    
    # Set up headers with API key
    headers = {
        "Accept": "audio/mpeg",
        "xi-api-key": Config.ELEVENLABS_API_KEY,
        "Content-Type": "application/json"
    }
    
    # Generate the speech
    try:
        response = requests.post(url, json=data, headers=headers)
        
        if response.status_code != 200:
            print(f"Error from ElevenLabs API: {response.text}")
            return None
        
        # Generate a unique filename
        timestamp = int(time.time())
        filename = f"audio-files/{timestamp}_{speaker_type}.mp3"
        
        # Write the response to the output file
        with open(filename, "wb") as out:
            out.write(response.content)
            
        print(f'Audio content written to file "{filename}"')
        return filename
        
    except Exception as e:
        print(f"Error synthesizing speech with ElevenLabs: {e}")
        return None

def enhance_hindi_text(text):
    """Enhance Hindi text for better TTS pronunciation"""
    
    # Add appropriate pauses with commas for Hindi
    # Hindi often has different pausing patterns than English
    enhanced_text = text
    
    # Add pause after certain Hindi particles if they don't already have one
    particles = ["और", "लेकिन", "फिर", "क्योंकि", "तो"]
    for particle in particles:
        enhanced_text = enhanced_text.replace(f"{particle} ", f"{particle}, ")
    
    # Ensure proper spacing between Hindi words
    # (Sometimes Hindi text can have spacing issues)
    enhanced_text = enhanced_text.replace("।", "। ")
    
    return enhanced_text

def merge_audio_files(filenames, output_file="hindi_podcast.mp3"):
    """Merge audio files with volume normalization"""
    
    if not filenames:
        print("No audio files to merge")
        return
    
    # Start with the first file
    combined = AudioSegment.from_mp3(filenames[0])
    
    # Apply normalization to first segment
    combined = effects.normalize(combined)
    
    # Add a pause between turns
    pause = AudioSegment.silent(duration=Config.PAUSE_BETWEEN_TURNS)
    
    # Add each subsequent file with a pause
    for file in filenames[1:]:
        # Load and normalize this segment
        segment = AudioSegment.from_mp3(file)
        segment = effects.normalize(segment)
        
        # Add to combined audio
        combined += pause
        combined += segment
    
    # Final normalization pass to ensure consistency
    combined = effects.normalize(combined)
    
    # Export the combined audio
    combined.export(output_file, format="mp3")
    print(f"Created Hindi podcast with consistent volume at {output_file}")

def extract_script_points(script_file):
    """Extract scripted conversation points from a Hindi script file"""
    script_points = []
    
    # Determine script format based on file extension
    if script_file.endswith('.json'):
        # Parse JSON script
        with open(script_file, 'r', encoding='utf-8') as f:
            script_data = json.load(f)
            
        for item in script_data:
            script_points.append({
                "speaker": item["speaker"],
                "text": item["text"]
            })
            
    else:
        # Parse text script format (Host1: line, Host2: line)
        with open(script_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                    
                if ":" in line:
                    parts = line.split(":", 1)
                    speaker = parts[0].strip()
                    text = parts[1].strip()
                    script_points.append({
                        "speaker": speaker,
                        "text": text
                    })
    
    return script_points

def run_hindi_podcast(script_file, output_file="hindi_podcast.mp3"):
    """Run Hindi podcast from script file without Claude generation"""
    
    # Extract script points from file
    script_points = extract_script_points(script_file)
    
    # Initialize audio files list
    audio_files = []
    
    # Process each line in the script
    for i, point in enumerate(script_points):
        print(f"Processing line {i+1}: {point['speaker']} speaking...")
        
        # Determine speaker type (Male/Female)
        # This assumes your script specifies "Male" and "Female" as speakers
        # If your script uses different names, you'll need to map them
        speaker_type = point['speaker']
        if speaker_type not in Config.ELEVENLABS_VOICES:
            if speaker_type.lower() in ["पुरुष", "पुरूष", "अध्यक्ष", "संचालक", "Rohan"]:
                speaker_type = "Male"
            elif speaker_type.lower() in ["महिला", "संचालिका", "Asha"]:
                speaker_type = "Female"
            else:
                # Default fallback
                speaker_type = "Male" if i % 2 == 0 else "Female"
        
        # Convert to speech
        audio_file = text_to_speech_elevenlabs(point['text'], speaker_type)
        if audio_file:
            audio_files.append(audio_file)
        
        # Small delay to avoid rate limits
        time.sleep(1)
    
    # Merge all audio files into a single podcast
    merge_audio_files(audio_files, output_file)
    
    return audio_files

def main():
    parser = argparse.ArgumentParser(description="Generate a Hindi podcast with ElevenLabs voices")
    parser.add_argument("--script", required=True, help="Path to Hindi script file (JSON or TXT)")
    parser.add_argument("--output", default="hindi_podcast.mp3", help="Output podcast filename")
    
    args = parser.parse_args()
    
    # Check for ElevenLabs API key
    if Config.ELEVENLABS_API_KEY == "your_elevenlabs_api_key":
        print("⚠️ Please set your ElevenLabs API key in the Config class before running")
        print("You can get your API key at https://elevenlabs.io/app (Settings > API Key)")
        return
    
    # Check for voice IDs
    if Config.ELEVENLABS_VOICES["Male"] == "your_hindi_male_voice_id" or Config.ELEVENLABS_VOICES["Female"] == "your_hindi_female_voice_id":
        print("⚠️ Please set your ElevenLabs Hindi voice IDs in the Config class before running")
        print("You can find voice IDs at https://elevenlabs.io/app (Voice Library section)")
        return
    
    # Run the Hindi podcast generation
    run_hindi_podcast(args.script, args.output)
    
    print(f"Hindi podcast generated successfully: {args.output}")

if __name__ == "__main__":
    main()
