import os
import json
import time
import random
import requests
import anthropic
from pydub import AudioSegment, effects
import argparse

# Configuration
class Config:
    # Anthropic Claude settings
    CLAUDE_API_KEY = "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"  # Replace with your API key
    MODEL = "claude-3-7-sonnet-20250219"  # Options: claude-3-opus-20240229, claude-3-sonnet-20240229, claude-3-haiku-20240307
    
    # ElevenLabs settings
    ELEVENLABS_API_KEY = "sk_e016ab1ac481c8a954dd88ea249fd5cfd9f0573628c09cee"  # Replace with your ElevenLabs API key
    ELEVENLABS_VOICES = {
        "Sascha": "UgBBYS2sOqTuMpoF3BR0",  # Replace with your chosen male voice ID
        "Marina": "21m00Tcm4TlvDq8ikWAM"  # Replace with your chosen female voice ID
    }
    # Voice IDs to try: "21m00Tcm4TlvDq8ikWAM" (Rachel), "D38z5RcWu1voky8WS1ja" (Adam)
    
    # ElevenLabs model settings
    ELEVENLABS_MODEL = "eleven_turbo_v2"  # Options: eleven_turbo_v2, eleven_multilingual_v2
    
    # Voice settings
    VOICE_SETTINGS = {
        "Sascha": {
            "stability": 0.35,         # Lower stability allows more natural variation
            "similarity_boost": 0.75,   # Balance between voice consistency and natural speaking
            "style": 0.0,              # Keep neutral style
            "use_speaker_boost": True,  # Enhances voice clarity
        },
        "Marina": {
            "stability": 0.3,          # Slightly more variation for female voice
            "similarity_boost": 0.7,    # Balance between voice consistency and natural speaking
            "style": 0.0,              # Keep neutral style
            "use_speaker_boost": True,  # Enhances voice clarity
        }
    }
    
    # Conversation settings
    MAX_TURNS = 15  # Maximum conversation turns
    TEMPERATURE = 0.5  # Creativity level (higher = more creative)
    SCRIPT_ADHERENCE = 0.7  # How closely to follow script (0-1)
    
    # Audio settings
    PAUSE_BETWEEN_TURNS = 500  # milliseconds

# Initialize the Claude client
claude_client = anthropic.Anthropic(api_key=Config.CLAUDE_API_KEY)

class PodcastAgent:
    def __init__(self, name, persona, voice_id):
        self.name = name
        self.persona = persona
        self.voice_id = voice_id
        self.context = []
    
    def generate_response(self, script_point, conversation_history, opponent_last_message):
        """Generate a response based on the script point and conversation history"""
        
        # Construct prompt with personality, history, and script guidance
        system_prompt = f"""You are {self.name}, a podcast host with the following persona: {self.persona}
        
You're having a conversation with your co-host. Your responses should:
1. Stay generally on topic with the script points
2. Feel natural and conversational (use filler words occasionally)
3. Include your own thoughts and insights
4. Reference what your co-host just said
5. Keep responses between 2-4 sentences (30-100 words)
6. Never explicitly mention that you're following a script

Use a natural speaking style with occasional "um", "uh", "like", or similar filler words to sound more human. Use these sparingly to sound natural, not forced.

When you use fillers like "um" or "uh", place a space before and after them to ensure proper pronunciation, like: " um " or " uh ".

• Add occasional brief pauses using commas where you might naturally pause while thinking
• Use contractions like "don't" instead of "do not" to sound conversational
• Vary your sentence lengths - mix short and longer sentences
• Occasionally ask a follow-up question to your co-host"""

        # Format conversation history for Claude
        conversation_text = ""
        for entry in conversation_history[-6:]:  # Only use last 6 entries to conserve context
            speaker_name = entry["speaker"]
            message = entry["text"]
            conversation_text += f"{speaker_name}: {message}\n\n"
        
        # Prepare script guidance message
        script_guidance = f"""The current topic you should discuss is: {script_point}
        
You should generally follow this topic, but you can add your own thoughts and perspectives. Your co-host just said: '{opponent_last_message}'

Respond naturally to what they said while keeping the conversation moving forward. Make your response sound natural in spoken form.

Include occasional filler words like " um ", " uh ", "you know", or "I mean" where they would naturally occur in conversation, but use them sparingly."""

        # Construct the final prompt for Claude
        prompt = f"""
Here's the previous conversation:

{conversation_text}

{script_guidance}

Remember to stay in character as {self.name} and speak conversationally. What do you say next?
"""

        # Make API call to generate response
        try:
            message = claude_client.messages.create(
                model=Config.MODEL,
                max_tokens=150,
                temperature=Config.TEMPERATURE,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            return message.content[0].text
            
        except Exception as e:
            print(f"Error generating response: {e}")
            return f"Well, that's an interesting point. Let me think about that for a moment..."

def text_to_speech_elevenlabs(text, speaker_name):
    """Convert text to speech using ElevenLabs with natural voice settings"""
    
    # Create output directory if it doesn't exist
    os.makedirs("audio-files", exist_ok=True)
    
    # Get the voice ID and settings for this speaker
    voice_id = Config.ELEVENLABS_VOICES[speaker_name]
    voice_settings = Config.VOICE_SETTINGS[speaker_name]
    
    # Prepare the API endpoint
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    
    # Add some light markdown emphasis for better intonation
    # This helps with emphasis and tone without needing complex SSML
    enhanced_text = add_emphasis_markers(text)
    
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
        filename = f"audio-files/{timestamp}_{speaker_name}.mp3"
        
        # Write the response to the output file
        with open(filename, "wb") as out:
            out.write(response.content)
            
        print(f'Audio content written to file "{filename}"')
        return filename
        
    except Exception as e:
        print(f"Error synthesizing speech with ElevenLabs: {e}")
        return None

def add_emphasis_markers(text):
    """Add emphasis using ElevenLabs-compatible methods without special characters"""
    
    # Define words/phrases to emphasize
    emphasis_words = [
        "really", "very", "absolutely", "definitely", "extremely",
        "important", "critical", "essential", "crucial", "vital",
        "never", "always", "must", "need to", "have to",
        "amazing", "incredible", "fantastic", "awesome", "wonderful",
        "terrible", "horrible", "awful", "disastrous"
    ]
    
    # ElevenLabs handles natural emphasis through capitalization and punctuation
    words = text.split()
    for i, word in enumerate(words):
        # Strip punctuation for comparison
        clean_word = word.lower().strip(".,!?;:")
        
        # Add emphasis for important words using capitalization
        if clean_word in emphasis_words:
            # CAPITALIZE the word for emphasis
            words[i] = word.replace(clean_word, clean_word.upper())
            
    enhanced_text = " ".join(words)
    
    # Enhance question intonation with a space before the question mark
    enhanced_text = enhanced_text.replace("?", " ?")
    
    # Add commas for natural pauses around "um" and "uh"
    enhanced_text = enhanced_text.replace(" um ", ", um, ")
    enhanced_text = enhanced_text.replace(" uh ", ", uh, ")
    
    return enhanced_text

def merge_audio_files(filenames, output_file="podcast-eleven-labs.mp3"):
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
    print(f"Created podcast with consistent volume at {output_file}")

def extract_script_points(script_file):
    """Extract scripted conversation points from a script file"""
    script_points = []
    
    # Determine script format based on file extension
    if script_file.endswith('.json'):
        # Parse JSON script
        with open(script_file, 'r') as f:
            script_data = json.load(f)
            
        for item in script_data:
            script_points.append({
                "speaker": item["speaker"],
                "text": item["text"]
            })
            
    else:
        # Parse text script format (Sascha: line, Marina: line)
        with open(script_file, 'r') as f:
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

def run_semi_scripted_conversation(script_file, output_file="podcast-eleven-labs.mp3", use_script=0.7):
    """Run a semi-scripted conversation between two podcast agents"""
    
    # Define agent personas
    sascha_persona = """You are Sascha, an enthusiastic and knowledgeable tech podcast host. 
    You're passionate about AI, machine learning, and how technology impacts society.
    Your communication style is energetic, insightful, and occasionally you use technical terminology
    but explain it clearly. You ask thoughtful follow-up questions to your co-host."""
    
    marina_persona = """You are Marina, a thoughtful and articulate podcast co-host.
    You have a background in both technology and humanities, giving you a unique perspective.
    Your communication style is warm, inquisitive, and you often bring conversations back to 
    the human impact of technology. You're good at making complex topics accessible."""
    
    # Create the podcast agents
    sascha = PodcastAgent("Sascha", sascha_persona, Config.ELEVENLABS_VOICES["Sascha"])
    marina = PodcastAgent("Marina", marina_persona, Config.ELEVENLABS_VOICES["Marina"])
    
    # Extract script points from file
    script_points = extract_script_points(script_file)
    
    # Initialize conversation tracking
    conversation_history = []
    audio_files = []
    
    # Determine who speaks first based on script
    current_speaker = script_points[0]["speaker"] if script_points else "Sascha"
    
    # Run the conversation for a set number of turns
    for turn in range(min(Config.MAX_TURNS, len(script_points))):
        print(f"Turn {turn+1}: {current_speaker} speaking...")
        
        # Get the relevant agent
        agent = sascha if current_speaker == "Sascha" else marina
        opponent = marina if current_speaker == "Sascha" else sascha
        
        # Determine if this turn should follow script or improvise
        use_script_for_turn = turn < len(script_points) and script_points[turn]["speaker"] == current_speaker
        
        if use_script_for_turn and random.random() < use_script:
            # Use the scripted text
            response = script_points[turn]["text"]
            print(f"[SCRIPT] {current_speaker}: {response}")
        else:
            # Get script guidance (if available)
            script_guidance = ""
            for script_point in script_points:
                if script_point["speaker"] == current_speaker:
                    script_guidance = script_point["text"]
                    break
            
            # Get the last message from opponent
            opponent_last_message = ""
            for entry in reversed(conversation_history):
                if entry["speaker"] == opponent.name:
                    opponent_last_message = entry["text"]
                    break
            
            # Generate a response
            response = agent.generate_response(script_guidance, conversation_history, opponent_last_message)
            print(f"[AI] {current_speaker}: {response}")
        
        # Add to conversation history
        conversation_history.append({
            "speaker": current_speaker,
            "text": response
        })
        
        # Convert to speech
        audio_file = text_to_speech_elevenlabs(response, current_speaker)
        if audio_file:
            audio_files.append(audio_file)
        
        # Switch speakers
        current_speaker = "Marina" if current_speaker == "Sascha" else "Sascha"
        
        # Small delay to avoid rate limits
        time.sleep(1)
    
    # Merge all audio files into a single podcast
    merge_audio_files(audio_files, output_file)
    
    # Save conversation transcript
    with open("transcript.json", "w") as f:
        json.dump(conversation_history, f, indent=2)
    
    return conversation_history

def main():
    parser = argparse.ArgumentParser(description="Generate a semi-scripted AI podcast with ElevenLabs voices")
    parser.add_argument("--script", required=True, help="Path to script file (JSON or TXT)")
    parser.add_argument("--output", default="podcast-eleven-labs.mp3", help="Output podcast filename")
    parser.add_argument("--adherence", type=float, default=0.7, 
                      help="Script adherence level (0-1, where 1 means strictly follow script)")
    
    args = parser.parse_args()
    
    # Check for ElevenLabs API key
    if Config.ELEVENLABS_API_KEY == "your_elevenlabs_api_key":
        print("⚠️ Please set your ElevenLabs API key in the Config class before running")
        print("You can get your API key at https://elevenlabs.io/app (Settings > API Key)")
        return
    
    # Check for voice IDs
    if Config.ELEVENLABS_VOICES["Sascha"] == "your_male_voice_id" or Config.ELEVENLABS_VOICES["Marina"] == "your_female_voice_id":
        print("⚠️ Please set your ElevenLabs voice IDs in the Config class before running")
        print("You can find voice IDs at https://elevenlabs.io/app (Voice Library section)")
        return
    
    # Run the conversation
    conversation = run_semi_scripted_conversation(
        args.script, 
        args.output,
        args.adherence
    )
    
    print(f"Podcast generated successfully: {args.output}")
    print(f"Transcript saved to: transcript.json")

if __name__ == "__main__":
    main()
